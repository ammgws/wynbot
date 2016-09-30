# Imports from Python Standard Library
import datetime as dt
import logging
import ssl
from time import sleep
from urllib.parse import urlencode

# Third party imports
from configparser import ConfigParser
import requests
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
from sleekxmpp.xmlstream import cert


class HangoutsClient(ClientXMPP):
    '''
    Client for connecting to Hangouts, sending a message to all users in the
    roster, and then disconnecting.
    '''

    def __init__(self, config_path, message):
        # Initialise parameters
        self.message = message

        # Read in config values
        self.config = ConfigParser()
        self.config.read(config_path)
        self.config_path = config_path
        logging.debug('Using config file: %s', config_path)

        # Get Hangouts OAUTH info from config file
        self.client_id = self.config.get('General', 'client_id')
        self.client_secret = self.config.get('General', 'client_secret')
        self.refresh_token = self.config.get('General', 'refresh_token')

        # Generate access token
        self.token_expiry = None
        self.access_token = None
        self.google_authenticate()

        # Get email address for Hangouts login
        hangouts_login_email = self.google_get_email()
        logging.debug('Going to login using: %s', hangouts_login_email)

        # Setup new SleekXMPP client to connect to Hangouts.
        # Not passing in actual password since using OAUTH2 to login
        ClientXMPP.__init__(self,
                            jid=hangouts_login_email,
                            password=None,
                            sasl_mech='X-OAUTH2')
        self.auto_reconnect = True  # Restart stream in the event of an error
        #: Max time to delay between reconnection attempts (in seconds)
        self.reconnect_max_delay = 300

        # Register XMPP plugins (order does not matter.)
        # To do: remove unused plugins
        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0004')  # Data Forms
        self.register_plugin('xep_0199')  # XMPP Ping

        # The session_start event will be triggered when the XMPP client
        # establishes its connection with the server and the XML streams are
        # ready for use. We want to listen for this event so that we can
        # initialize our roster. Need threaded=True so that the session_start
        # handler doesn't block event processing while we wait for presence
        # stanzas to arrive.
        self.add_event_handler("session_start", self.start, threaded=True)

        # Triggered whenever a 'connected' XMPP event is stanza is received,
        # in particular when connection to XMPP server is established.
        # Fetches a new access token and updates the class' access_token value.
        self.add_event_handler('connected', self.reconnect_workaround)

        # When using a Google Apps custom domain, the certificate does not
        # contain the custom domain, just the Hangouts server name. So we will
        # need to process invalid certifcates ourselves and check that it
        # really is from Google.
        self.add_event_handler("ssl_invalid_cert", self.invalid_cert)

    def reconnect_workaround(self, event):  # pylint: disable=W0613
        ''' Workaround for SleekXMPP reconnect.
        If a reconnect is attempted after access token is expired, auth fails
        and the client is stopped. Get around this by updating the access
        token whenever the client establishes a connection to the server.
        '''
        self.google_authenticate()
        self.credentials['access_token'] = self.access_token

    def invalid_cert(self, pem_cert):
        ''' Verify that certificate originates from Google. '''
        der_cert = ssl.PEM_cert_to_DER_cert(pem_cert)
        try:
            cert.verify('talk.google.com', der_cert)
            logging.debug("Found Hangouts certificate")
        except cert.CertificateError as err:
            logging.error(err)
            self.disconnect(send_close=False)

    def start(self, event):  # pylint: disable=W0613
        '''
        Process the session_start event.

        Broadcast initial presence stanza, request the roster,
        and then send the message to the specified user(s).

        Args:
            event -- An empty dictionary. The session_start event does not
                     provide any additional data.
        '''

        # Broadcast initial presence stanza
        self.send_presence()

        # Request the roster
        try:
            self.get_roster()
        except IqError as err:
            logging.error('There was an error getting the roster')
            logging.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            logging.error('Server is taking too long to respond')
            self.disconnect(send_close=False)

        # Wait for presence stanzas to be received, otherwise roster will be empty
        sleep(5)
        logging.info('Wynbot JID: %s', self.boundjid)

        # Send message to each user found in the roster
        num_users = 0
        for recipient in self.client_roster:
            if recipient != self.boundjid:
                num_users = num_users + 1
                logging.info('Sending to: %s', recipient)
                self.send_message(mto=recipient, mbody=self.message, mtype='chat')
                        
        logging.info('Sent message to %s users in roster', num_users)

        # Wait for all message stanzas to be sent before disconnecting
        self.disconnect(wait=True)

    def google_authenticate(self):
        ''' Get access token for Hangouts login.
        Note that Google access token expires in 3600 seconds.
        '''
        # Authenticate with Google and get access token for Hangouts
        if not self.refresh_token:
            # If no refresh token is found in config file, then need to start
            # new authorization flow and get access token that way.
            # Note: Google has limit of 25 refresh tokens per user account per
            # client. When limit reached, creating a new token automatically
            # invalidates the oldest token without warning.
            # (Limit does not apply to service accounts.)
            # https://developers.google.com/accounts/docs/OAuth2#expiration
            logging.debug('No refresh token in config file (val = %s of type %s). '
                          'Need to generate new token.',
                          self.refresh_token,
                          type(self.refresh_token))
            # Get authorisation code from user
            auth_code = self.google_authorisation_request()
            # Request access token using authorisation code
            self.google_token_request(auth_code)
            # Save refresh token for next login attempt or application startup
            self.config.set('General', 'refresh_token', self.refresh_token)
            with open(self.config_path, 'w') as config_file:
                self.config.write(config_file)
        elif (self.access_token is None) or (dt.datetime.now() > self.token_expiry):
            # Use existing refresh token to get new access token.
            logging.debug('Using refresh token to generate new access token.')
            # Request access token using existing refresh token
            self.google_token_request()
        else:
            # Access token is still valid, no need to generate new access token.
            logging.debug('Access token is still valid - no need to regenerate.')
            return

    def google_authorisation_request(self):
        '''Start authorisation flow to get new access + refresh token.'''

        # Start by getting authorization_code for Hangouts scope.
        # Email scope is used to get email address for Hangouts login.
        oauth2_scope = ('https://www.googleapis.com/auth/googletalk '
                        'https://www.googleapis.com/auth/userinfo.email')
        oauth2_login_url = 'https://accounts.google.com/o/oauth2/v2/auth?{}'.format(
            urlencode(dict(
                client_id=self.client_id,
                scope=oauth2_scope,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob',
                response_type='code',
                access_type='offline',
            ))
        )

        # Print auth URL and wait for user to grant access and
        # input authentication code into the console.
        print(oauth2_login_url)
        auth_code = input("Enter auth code from the above link: ")
        return auth_code

    def google_token_request(self, auth_code=None):
        '''Make an access token request and get new token(s).
           If auth_code is passed then both access and refresh tokens will be
           requested, otherwise the existing refresh token is used to request
           an access token.

           Update the following class variables:
            access_token
            refresh_token
            token_expiry
           '''
        # Build request parameters. Order doesn't seem to matter, hence using dict.
        token_request_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        if auth_code is None:
            # Use existing refresh token to get new access token.
            token_request_data['refresh_token'] = self.refresh_token
            token_request_data['grant_type'] = 'refresh_token'
        else:
            # Request new access and refresh token.
            token_request_data['code'] = auth_code
            token_request_data['grant_type'] = 'authorization_code'
            # 'urn:ietf:wg:oauth:2.0:oob' signals to the Google Authorization
            # Server that the authorization code should be returned in the
            # title bar of the browser, with the page text prompting the user
            # to copy the code and paste it in the application.
            token_request_data['redirect_uri'] = 'urn:ietf:wg:oauth:2.0:oob'
            token_request_data['access_type'] = 'offline'

        # Make token request to Google.
        oauth2_token_request_url = 'https://www.googleapis.com/oauth2/v4/token'
        resp = requests.post(oauth2_token_request_url, data=token_request_data)
        # If request is successful then Google returns values as a JSON array
        values = resp.json()
        self.access_token = values['access_token']
        if auth_code:  # Need to save value of new refresh token
            self.refresh_token = values['refresh_token']
        self.token_expiry = dt.datetime.now() + dt.timedelta(seconds=int(values['expires_in']))
        logging.info('Access token expires on %s', self.token_expiry.strftime("%Y/%m/%d %H:%M"))

    def google_get_email(self):
        '''Get email address for Hangouts login.'''
        authorization_header = {"Authorization": "OAuth %s" % self.access_token}
        resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                            headers=authorization_header)
        # If request is successful then Google returns values as a JSON array
        values = resp.json()
        return values['email']
