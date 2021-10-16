#!/usr/bin/env python3

# standard library
import datetime as dt
import json
import logging
import os
import os.path
from configparser import ConfigParser
from pathlib import Path
from random import randint
from time import sleep

# third party
import click
import markovify
from hangoutsclient import HangoutsClient

# Inspired by: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/

APP_NAME = "wynbot"


def load_corpus_text(corpus_file):
    """
    Reads in Hangouts chat log data from text file or JSON file.
    Returns a list of all the messages in the file.
    """

    if corpus_file.endswith(".txt"):
        with open(corpus_file, encoding="utf-8") as f:
            text = f.read()
    elif corpus_file.endswith(".json"):
        with open(corpus_file) as f:
            messages = json.loads(f.read())
        text = "".join(messages.values())
    else:
        text = None

    return text


def load_model_json(model_file):
    if os.path.isfile(model_file):
        logging.info("Loading model from %s", model_file)
        with open(model_file) as json_file:
            try:
                markov_json = json.load(json_file)
            except json.decoder.JSONDecodeError:
                raise Exception("Chain file empty or malformed")
    else:
        # file does not exist
        markov_json = None

    return markov_json


def build_text_model(cache_path, state_size, corpus_filepath, model_filepath):
    """
    Build a new Markov chain generator model.
    Returns a markovify Text instance.
    """
    markov_json = load_model_json(model_filepath)

    logging.debug("Loading corpus from %s.", corpus_filepath)
    corpus = load_corpus_text(corpus_filepath)
    logging.debug("Creating text model with state size %s", state_size)
    if markov_json and state_size == markov_json["state_size"]:
        logging.debug("Using existing chain file from %s.", model_filepath)
        text_model = markovify.Text.from_dict(markov_json)
    elif markov_json and state_size != markov_json["state_size"]:
        logging.debug(
            "Existing chain file is of state size %s, where as requested is %s",
            state_size,
            markov_json["state_size"],
        )
        logging.debug("Creating new chain file.")
        # TODO: refactor
        text_model = markovify.Text(corpus, state_size=state_size, chain=None)
        # save our newly created Markov chain for the next time script is run
        with open(os.path.join(cache_path, "markov_chain.json"), "w") as json_file:
            json_file.write(text_model.to_json())
    else:
        logging.debug("Creating new chain file.")
        text_model = markovify.Text(corpus, state_size=state_size, chain=None)
        # save our newly created Markov chain for the next time script is run
        with open(os.path.join(cache_path, "markov_chain.json"), "w") as json_file:
            json_file.write(text_model.to_json())

    return text_model


def create_dir(ctx, param, directory):
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    return directory


@click.command()
@click.argument("recipient")
@click.option(
    "--config-path",
    type=click.Path(),
    default=os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP_NAME
    ),
    callback=create_dir,
    help=f"Path to directory containing config file. Defaults to $XDG_CONFIG_HOME/{APP_NAME}.",
)
@click.option(
    "--cache-path",
    type=click.Path(),
    default=os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), APP_NAME
    ),
    callback=create_dir,
    help=f"Path to directory to store logs and such. Defaults to $XDG_CACHE_HOME/{APP_NAME}.",
)
@click.option(
    "--num_chars",
    "-n",
    default=140,
    help="max character length for the generated message.",
)
@click.option(
    "--state_size",
    "-s",
    default=2,
    help="state size for Markov model.",
)
@click.option(
    "--print-only",
    is_flag=True,
    default=False,
    help="Print message to stdout, not Hangouts.",
)
@click.option("--prefix", default="", help="String to prefix message with.")
@click.option("--no-log", is_flag=True)
def main(
    config_path,
    cache_path,
    num_chars,
    state_size,
    print_only,
    prefix,
    recipient,
    no_log,
):
    """
    Login to Hangouts, send generated message and disconnect.
    """
    if not no_log:
        configure_logging(cache_path)

    config_file = os.path.join(config_path, "wynbot.ini")
    logging.debug("Using config file: %s.", config_file)
    config = ConfigParser()
    config.read(config_file)
    client_id = config.get("Hangouts", "client_id")
    client_secret = config.get("Hangouts", "client_secret")
    token_file = os.path.join(cache_path, "hangouts_cached_token")
    if not os.path.isfile(token_file):
        Path(token_file).touch()

    # Build the text model using markovify
    corpus_file = os.path.join(config_path, "corpus.txt")
    chain_file = os.path.join(cache_path, "markov_chain.json")
    text_model = build_text_model(cache_path, state_size, corpus_file, chain_file)
    logging.debug("Starting message generation. Max. chars: %s", num_chars)
    message = text_model.make_short_sentence(num_chars) or "failed to generate message"
    message = f"{prefix}{message}"
    logging.info('Generated message (%s chars): "%s"', len(message), message)

    if print_only:
        print(message)
    else:
        # Setup Hangouts bot instance, connect and send message
        hangouts = HangoutsClient(client_id, client_secret, token_file)
        if hangouts.connect():
            hangouts.process(block=False)
            sleep(5)  # need time for Hangouts roster to update
            logging.info("Contacts list: %s", hangouts.contacts_list)
            hangouts.send_to(
                [
                    recipient,
                ],
                message,
            )
            hangouts.disconnect(wait=True)
            logging.info("Finished sending today's message.")
        else:
            logging.error("Unable to connect to Hangouts.")


def configure_logging(log_dir):
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)

    log_folder = os.path.join(log_dir, "logs")
    if not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)

    log_filename = "wynbot_{0}.log".format(
        dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss")
    )
    log_filepath = os.path.join(log_folder, log_filename)
    log_handler = logging.FileHandler(log_filepath)

    log_format = logging.Formatter(
        fmt="%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    # Lower requests module's log level so that OAUTH2 details aren't logged
    logging.getLogger("requests").setLevel(logging.WARNING)
    # Quieten SleekXMPP output
    # logging.getLogger('sleekxmpp.xmlstream.xmlstream').setLevel(logging.INFO)


if __name__ == "__main__":
    main()
