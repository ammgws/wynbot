#!/usr/bin/env python3

# standard library
import datetime as dt
import json
import logging
import os.path
from os import nice  # Linux only
from random import randint
from sys import path
from time import sleep
# third party
import markovify
from hangoutsclient import HangoutsClient

# Inspired by: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/

# Get absolute path of the dir script is run from
CWD = path[0]  # pylint: disable=C0103


def _load_db():
    """
    Reads in Hangouts chat logs from JSON file (exported from Google Takeout).
    Returns a dictionary keyed by unique timestamps (Hangouts us timestamps).
    """
    try:
        with open(os.path.join(CWD, 'message_db.json'), 'r') as json_file:
            messages = json.loads(json_file.read())
    except IOError:
        with open(os.path.join(CWD, 'message_db.json'), 'r') as json_file:
            json_file.write('{}')
        messages = {}

    return messages


def build_text_model():
    """
    Load database script dir and build a new Markov chain generator model.
    Returns TextModel.
    """
    messages = _load_db()
    return markovify.Text(''.join(messages.values()), state_size=2)


def main():
    """
    Login to Hangouts, send generated message and disconnect.
    """

    # Set python process to max niceness in order to use less CPU, as CPU hits
    # 100% on rPi when generating Markov model. (Don't want to slow webserver.)
    nice(20)

    # Sleep random amount of time so messages are sent at a different time everyday
    delay = randint(1, 8 * 60 * 60)  # range of 1s to 8 hours
    delay_date = dt.datetime.now() + dt.timedelta(seconds=delay)
    logging.info('Sleeping for %s seconds, continue at %s', delay, delay_date.strftime("%Y/%m/%d %H:%M:%S"))
    sleep(delay)

    # Build the text model using markovify
    text_model = build_text_model()
    # markov_chain = text_model.make_sentence()
    markov_chain = text_model.make_short_sentence(140) or "failed to generate message"

    # Setup Hangouts bot instance
    hangouts = HangoutsClient(os.path.join(CWD, 'wynbot.ini'), markov_chain)

    # Connect to Hangouts and start processing XMPP stanzas.
    if hangouts.connect(address=('talk.google.com', 5222),
                        reattempt=True, use_tls=True):
        hangouts.process(block=True)
        logging.info("Finished sending today's message.")
    else:
        logging.error('Unable to connect to Hangouts.')


if __name__ == '__main__':
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)
    log_filename = 'wynbot_{0}.log'.format(dt.datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss'))
    log_handler = logging.FileHandler(os.path.join(CWD, 'logs', log_filename))
    log_format = logging.Formatter(
        fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
        datefmt='%Y-%m-%d %H:%M:%S')
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    # Lower requests module's log level so that OAUTH2 details aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)
    # Quieten SleekXMPP output
    # logging.getLogger('sleekxmpp.xmlstream.xmlstream').setLevel(logging.INFO)

    main()
