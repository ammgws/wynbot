#!/usr/bin/env python3

# standard library
import datetime as dt
import json
import logging
import os
import os.path
import re
from random import randint
from sys import path
from time import sleep
# third party
import click
import markovify
import nltk

from hangoutsclient import HangoutsClient


# Inspired by: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/

# Get absolute path of the dir script is run from
CWD = path[0]  # pylint: disable=C0103


def load_corpus_text(corpus_file):
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


def load_model_json(model_file):
    if os.path.isfile(model_file):
        logging.info('Loading model from file.')
        with open(model_file, 'r') as json_file:
            markov_json = json.load(json_file)
    else:
        # file does not exist
        markov_json = None

    return markov_json


def build_text_model(state_size, use_nltk, corpus_filepath, model_filepath):
    """
    Build a new Markov chain generator model.
    Returns a markovify Text instance.
    """
    markov_json = load_model_json(model_filepath)

    logging.debug('Loading corpus from %s.', corpus_filepath)
    corpus = load_corpus_text(corpus_filepath)
    logging.debug('Creating text model with state size %s', state_size)
    if use_nltk:
        logging.debug('Using nltk')
        nltk.data.path.append(os.path.join(CWD, 'nltk_data'))
        text_model = POSifiedText.from_json(markov_json)
    elif markov_json and state_size == markov_json["state_s＃＃ize"]:
        logging.debug('Using existing chain file from %s.', model_filepath)
        text_model = markovify.Text.from_dict(markov_json)
    elif markov_json and state_size != markov_json["state_size"]:
        logging.debug('Existing chain file is of state size %s, where as requested is %s', state_size, markov_json["state_size"])
        logging.debug('Creating new chain file.')
        # TODO: refactor
        text_model = markovify.Text(corpus, state_size=state_size, chain=None)
        # save our newly created Markov chain for the next time script is run
        with open(os.path.join(CWD, 'markov_chain.json'), 'w') as json_file:
            json_file.write(text_model.to_json())
    else:
        logging.debug('Creating new chain file.')
        text_model = markovify.Text(corpus, state_size=state_size, chain=None)
        # save our newly created Markov chain for the next time script is run
        with open(os.path.join(CWD, 'markov_chain.json'), 'w') as json_file:
            json_file.write(text_model.to_json())

    return text_model


@click.command()
@click.option('--delay', '-d', default=-1, help='delay (in secs) before script enters main subroutine. -1 for random delay.')
@click.option('--chars', '-c', default=140, help='max character length for the generated message.')
@click.option('--state_size', '-s', default=2, help='state size for Markov model.')
@click.option('--natural', '-n', default=0, help='use ntlk (much slower than standard Markov).')
def main(delay, chars, state_size, natural):
    """
    Login to Hangouts, send generated message and disconnect.
    """
    # Path to config file
    config_path = os.path.join(CWD, 'wynbot.ini')
    logging.debug('Using config file: %s', config_path)

    if delay == -1:
        # Sleep random amount of time so messages are sent at a different time everyday
        delay = randint(1, 8 * 60 * 60)  # range of 1s to 8 hours

    delay_date = dt.datetime.now() + dt.timedelta(seconds=delay)
    logging.info('Sleeping for %s seconds, continue at %s', delay, delay_date.strftime("%Y/%m/%d %H:%M:%S"))
    sleep(delay)

    # Build the text model using markovify
    corpus_file = os.path.join(CWD, 'corpus.txt')
    chain_file = os.path.join(CWD, 'markov_chain.json')
    text_model = build_text_model(state_size, natural, corpus_file, chain_file)
    logging.debug('Starting message generation. Max. chars: %s', chars)
    message = text_model.make_short_sentence(chars) or "failed to generate message"
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


def configure_logging():
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)

    log_folder = os.path.join(CWD, 'logs')
    if not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)

    log_filename = 'wynbot_{0}.log'.format(dt.datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss'))
    log_filepath = os.path.join(log_folder, log_filename)
    log_handler = logging.FileHandler(log_filepath)

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
    configure_logging()
    main()
