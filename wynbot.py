#!/usr/bin/env python3

# standard library
import datetime as dt
import json
import logging
import os.path
import re
from argparse import ArgumentParser
from random import randint
from sys import path
from time import sleep
# third party
import markovify
import nltk
from hangoutsclient import HangoutsClient

# Inspired by: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/

# Get absolute path of the dir script is run from
CWD = path[0]  # pylint: disable=C0103


def load_corpus(corpus_file):
    """
    Reads in Hangouts chat log data from text file or JSON file.
    Returns a list of all the messages in the file.
    """

    if corpus_file.endswith('.txt'):
        with open(corpus_file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif corpus_file.endswith('.json'):
        with open(corpus_file, 'r') as f:
            messages = json.loads(f.read())
        text = ''.join(messages.values())
    else:
        text = None

    return text


def build_text_model(state_size, use_nltk, corpus_file, chain_file):
    """
    Build a new Markov chain generator model.
    Returns a markovify Text instance.
    """
    if os.path.exists(chain_file):
        logging.info('Loading chain file.')
        with open(chain_file, 'r') as json_file:
            markov_json = json.load(json_file)
        if len(markov_json[0][0]) != state_size:
            logging.info('State size mismatch. Chain file: %s, requested state size: %s.', len(markov_json[0][0]),
                         state_size)
            markov_json = None
    else:
        markov_json = None

    logging.debug('Loading corpus.')
    corpus = load_corpus(corpus_file)
    logging.debug('Creating text model with state size %s', state_size)
    if use_nltk:
        logging.debug('Using nltk')
        nltk.data.path.append(os.path.join(CWD, 'nltk_data'))
        text_model = POSifiedText.from_chain(markov_json, corpus=corpus)
    elif markov_json:
        logging.debug('Using existing chain file.')
        text_model = markovify.Text.from_chain(markov_json, corpus=corpus)
    else:
        logging.debug('Creating new chain file.')
        text_model = markovify.Text(corpus, state_size=state_size, chain=None)
        # save our newly created Markov chain for the next time script is run
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
    logging.debug('Using config file: %s', config_path)

    # Sleep random amount of time so messages are sent at a different time everyday
    if args.delay >= 0:
        delay = args.delay
    else:
        delay = randint(1, 8 * 60 * 60)  # range of 1s to 8 hours
    delay_date = dt.datetime.now() + dt.timedelta(seconds=delay)
    logging.info('Sleeping for %s seconds, continue at %s', delay, delay_date.strftime("%Y/%m/%d %H:%M:%S"))
    sleep(delay)

    # Build the text model using markovify
    corpus_file = os.path.join(CWD, 'corpus.txt')
    chain_file = os.path.join(CWD, 'markov_chain.json')
    text_model = build_text_model(args.state_size, args.use_nltk, corpus_file, chain_file)
    logging.debug('Starting message generation. Max. chars: %s', args.num_chars)
    message = text_model.make_short_sentence(args.num_chars) or "failed to generate message"
    logging.info('Generated message (%s chars): "%s"', len(message), message)

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
