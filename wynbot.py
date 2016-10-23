#!/usr/bin/env python3

# standard library
import datetime as dt
import json
import logging
import nltk
import os.path
import re
from argparse import ArgumentParser
from configparser import ConfigParser
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


def load_corpus(filename):
    """
    Reads in Hangouts chat log data from text file or JSON file.
    Returns a list of all the messages in the file.
    """

    if filename.endswith('.txt'):
        with open("corpus.txt", 'r', encoding="utf-8") as f:
            text = f.read()
    elif filename.endswith('.json'):
        try:
            with open(os.path.join(CWD, 'message_db.json'), 'r') as json_file:
                messages = json.loads(json_file.read())
        except IOError:
            with open(os.path.join(CWD, 'message_db.json'), 'r') as json_file:
                json_file.write('{}')
            messages = {}
        text = ''.join(messages.values())
    else:
        text = ''

    return text


def build_text_model(state_size, use_nltk, from_file='markov_chain.json'):
    """
    Build a new Markov chain generator model.
    Returns markovify Text instance.
    """
    if os.path.exists(from_file):
        logging.info('Loading chain file.')
        with open(from_file, 'r') as json_file:
            markov_json = json.load(json_file)
        if len(markov_json[0][0]) != state_size:
            logging.info('State size mismatch. Chain file: %s, requested state size: %s.', len(markov_json[0][0]),
                         state_size)
            markov_chain = None
        else:
            markov_chain = markovify.Chain.from_json(markov_json)
    else:
        markov_chain = None

    if not markov_chain:
        logging.info('Creating new chain file.')

    logging.debug('Loading corpus.')
    corpus = load_corpus('corpus.txt')
    logging.debug('Creating text model with state size %s', state_size)
    if use_nltk:
        nltk.data.path.append(os.path.join(CWD, 'nltk_data'))
        text_model = POSifiedText(corpus, state_size=state_size, chain=markov_chain)
    else:
        text_model = markovify.Text(corpus, state_size=state_size, chain=markov_chain)

    if not markov_chain:
        # save our newly created text_model for the next time script is run
        with open(os.path.join(CWD, 'markov_chain.json'), 'w') as json_file:
            json_file.write(text_model.chain.to_json())
    return text_model


def main(arguments):
    """
    Login to Hangouts, send generated message and disconnect.
    """
    args = parse_arguments(arguments)

    # Path to config file
    config_path = os.path.join(CWD, 'wynbot.ini')

    # Read in config values
    config = ConfigParser()
    config.read(config_path)
    config_path = config_path
    logging.debug('Using config file: %s', config_path)

    # Set python process to max niceness in order to use less CPU, as CPU hits
    # 100% on rPi when generating Markov model. (Don't want to slow webserver.)
    nice(20)

    if args.delay >= 0:
        delay = args.delay
    else:
        # Sleep random amount of time so messages are sent at a different time everyday
        delay = randint(1, 8 * 60 * 60)  # range of 1s to 8 hours
    delay_date = dt.datetime.now() + dt.timedelta(seconds=delay)
    logging.info('Sleeping for %s seconds, continue at %s', delay, delay_date.strftime("%Y/%m/%d %H:%M:%S"))
    sleep(delay)

    # Build the text model using markovify
    text_model = build_text_model(args.state_size, args.use_nltk)
    logging.debug('Starting message generation. Max. chars: %s', args.num_chars)
    message = text_model.make_short_sentence(args.num_chars) or "failed to generate message"
    logging.info('Generated message: "%s" of %s chars', message, len(message))

    # Setup Hangouts bot instance
    hangouts = HangoutsClient(config_path, message)

    # Connect to Hangouts and start processing XMPP stanzas.
    if hangouts.connect(address=('talk.google.com', 5222),
                        reattempt=True, use_tls=True):
        hangouts.process(block=True)
        logging.info("Finished sending today's message.")
    else:
        logging.error('Unable to connect to Hangouts.')


def parse_arguments(arguments):
    # Get command line arguments
    parser = ArgumentParser(description='Send Markov generated message.')
    parser.add_argument('-d', '--delay',
                        dest='delay',
                        type=int, default=-1,
                        help='Set delay before script enters main subroutine.')
    parser.add_argument('-c', '--characters',
                        dest='num_chars',
                        type=int, default=140,
                        help='Set the max chacter length for the generated message.')
    parser.add_argument('-n', '--natural',
                        dest='use_nltk',
                        type=int, default=0,
                        help='Set whether to use ntlk or not (much slower than standard Markov).')
    parser.add_argument('-s', '--statesize',
                        dest='state_size',
                        type=int, default=2,
                        help='Set the state size for Markov model.')
    return parser.parse_args(arguments)


def configure_logging():
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


class POSifiedText(markovify.Text):
    def word_split(self, sentence):
        words = re.split(self.word_split_pattern, sentence)
        words = ['::'.join(tag) for tag in nltk.pos_tag(words)]
        return words

    def word_join(self, words):
        sentence = ' '.join(word.split('::')[0] for word in words)
        return sentence


if __name__ == '__main__':
    from sys import argv  # pylint: disable=C0412

    configure_logging()

    main(argv[1:])
