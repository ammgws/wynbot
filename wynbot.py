# standard library
import datetime as dt
import json
import logging
import logging.handlers
# third party
import markovify
from hangoutsclient import HangoutsClient

# Inspired by: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/

def _load_db():
    """
    Reads 'database' from a JSON file on disk.
    Returns a dictionary keyed by unique message permalinks.
    """
    try:
        with open('message_db.json', 'r') as json_file:
            messages = json.loads(json_file.read())
    except IOError:
        with open('message_db.json', 'w') as json_file:
             json_file.write('{}')
        messages = {}

    return messages


# get all messages, build a giant text corpus
def build_text_model():
    """
    Read the latest 'database' off disk and build a new markov
    chain generator model.
    Returns TextModel.
    """
    messages = _load_db()
    return markovify.Text(" ".join(messages.values()), state_size=2)


def main():
    # Build the text model using markovify
    model = build_text_model()

    # Setup Hangouts bot instance, override 'message' method
    class HangoutsBot(HangoutsClient):
        def message(self, msg):
            logging.debug('Sending standard message')
            if msg['type'] in ('groupchat', 'chat', 'normal'):
                markov_chain = model.make_sentence()
                msg.reply(markov_chain).send()

        def group_message(self, msg):
            logging.debug('Sending group message')
            if msg['type'] in ('groupchat', 'chat', 'normal'):
                markov_chain = model.make_sentence()
                msg.reply(markov_chain).send()

    hangouts = HangoutsBot('wynbot.ini')
    # Connect to Hangouts and start processing XMPP stanzas.
    if hangouts.connect(address=('talk.google.com', 5222),
                        reattempt=True, use_tls=True):
        hangouts.process(block=False)
    else:
        logging.error('Unable to connect to Hangouts.')

if __name__ == '__main__':
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)
    log_filename = 'wynbot_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
    log_handler = logging.handlers.RotatingFileHandler(log_filename,
                                                       maxBytes=5242880,
                                                       backupCount=3)
    log_format = logging.Formatter(fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
                                   datefmt='%Y-%m-%d %H:%M:%S')
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    # Lower requests module's log level so that OAUTH2 details aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)
    # Quieten SleekXMPP output
    # logging.getLogger('sleekxmpp.xmlstream.xmlstream').setLevel(logging.INFO)

    main()
