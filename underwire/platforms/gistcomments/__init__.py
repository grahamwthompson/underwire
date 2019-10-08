from ciphers.fernet import FernetCrypt
from dateutil.parser import parse
import requests, threading, time
from requests import HTTPError
from datetime import datetime, timezone

USER_AGENT_STRING = "underwire v0.0: experimental encrypted messaging over whatever app"
POLLING_INTERVAL = 1.0

# TODO:
# 1) load the github token from elsewhere

class Message:
    def __init__(self, ciphertext, sender, recipient):
        self.sender = sender
        self.recipient = recipient
        self.ciphertext = ciphertext

class GistCommentChatClient:

    def __init__(self, msgReceivedCallback=None, cipherType=None, cipherPass=None, oauth_token=None, gist_id=None):
        print('starting gist chat client')
        print(cipherType, cipherPass)
        self.msgReceivedCallback = msgReceivedCallback
        self.gist_id = gist_id
        self.oauth_token = oauth_token
        self.comment_ids = []
        if self.verifyOauth(oauth_token):
            self.loggedIn = True
            self.oauth_token = oauth_token
        # starting the listener thread

        # verify the room actually exists before we get here too
        self.listener = threading.Thread(target=self.gistListener, daemon=True)
        self.listener.start()

        if cipherType == 'fernet':
            self.cipherClient = FernetCrypt(password=cipherPass)
        else:
            self.cipherClient = None

    def __del__(self):
        print('deleting the gist client class')
        self.listener.join()

    def verifyOauth(self, oauth_token):
        '''
        Check that our oauth_token actually works
        '''
        return True

    def commentParser(self, data):
        '''
        Utility function to parse all comments not already stored
        and return an array of (user, ciphertext) tuples
        '''
        comments = []
        for comment in data:
            # todo timestamp parsing
            id = comment.get('id', None)
            user = comment.get('user',{}).get('login')
            created_at = parse(comment.get('created_at', None))
            ciphertext = comment.get('body', None)

            if id not in self.comment_ids:
                comments.append((user, ciphertext))
                self.comment_ids.append(id)

        return comments

    def gistListener(self):
        '''
        Threaded function to listen for new messages from any of our
        target people.
        '''
        previous_timestamp = datetime.min.replace(tzinfo=timezone.utc)

        while 1:
            try:
                response = requests.get(
                    headers={"Authorization":"token {}".format(self.oauth_token),
                             "User-Agent": USER_AGENT_STRING},
                    url="https://api.github.com/gists/{}/comments".format(self.gist_id)
                    )
                response.raise_for_status()
            except HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
            except Exception as err:
                print(f'Other error occurred: {err}')

            possible_messages = self.commentParser(response.json())
            for user, ciphertext in possible_messages:
                try:
                    print('ciphertext: ', ciphertext)
                    encoded = ciphertext.encode("utf-8")
                    decrypted = self.cipherClient.decrypt(encoded)
                    print('decrypted: ', decrypted)
                except Exception as e:
                    decrypted = 'decryption failed'

                msg = Message(None,None,None)
                msg.text = decrypted
                msg.sender = user
                self.msgReceivedCallback(msg)

            previous_timestamp = datetime.now(timezone.utc)
            time.sleep(POLLING_INTERVAL)

    def sendMessage(self, txt):
        if self.loggedIn:
            ciphertext = self.cipherClient.encrypt(txt)
            encoded_ciphertext = ciphertext.decode("utf-8")

            requests.post(
                json={"body":encoded_ciphertext},
                headers={"Authorization":"token {}".format(self.oauth_token),
                         "User-Agent": USER_AGENT_STRING},
                url="https://api.github.com/gists/{}/comments".format(self.gist_id)
                )
            return 'success'
        else:
            return None

    def onReceive(self, msg):
        print('received a message')
        decrypted = self.cipherClient.decrypt(msg.ciphertext)
        print('decrypted: ', decrypted)
        msg.ciphertext = None
        msg.text = decrypted
        self.msgReceivedCallback(msg)
        return 'success'