#!/usr/bin/env python3

# standard library
# import datetime as dt
# third party
import simplejson as json


def get_conversations(data):
    """ Return dict of unique conversation IDs and their participants. """

    convos = {}
    for conversation in data['conversation_state']:
        conversation_id = conversation["conversation_id"]["id"]
        convo_participants = []
        for participant in conversation["conversation_state"]["conversation"]["participant_data"]:
            try:
                convo_participants.append(participant["fallback_name"])
            except KeyError:
                pass
        convos[conversation_id] = convo_participants

    return convos


def generate_corpus(data, convo_id):
    """ Return list containing all of the messages for the supplied conversation ID. """
    corpus = []
    states = data['conversation_state']
    for state in states:
        conversation_state = state['conversation_state']
        if 'event' in conversation_state:
            conversations = conversation_state['event']
            for conversation in conversations:
                if 'chat_message' in conversation:
                    message_content = conversation['chat_message']['message_content']
                    if 'segment' in message_content:
                        segment = message_content['segment']
                        for line in segment:
                            conversation_id = conversation['conversation_id']['id']
                            if conversation_id == convo_id:
                                # timestamp_us = int(conversation['timestamp'])  # epoch time in microseconds
                                # timestamp = dt.datetime.fromtimestamp(timestamp_us/1000000)  # convert to epoch secs
                                # timestamp_str = timestamp.strftime("%Y%m%d_%Hh%Mm%Ss.%f")
                                if 'text' in line:
                                    message_text = line['text'].strip()
                                    # If empty message then skip this pass of the loop
                                    if not message_text:
                                        continue
                                    # Append period if sentence is not otherwise punctuated
                                    if not message_text.endswith(('.', '!', '?')):
                                        message_text += '.'
                                    # Capitalise first letter
                                    message_text = message_text[0].upper() + message_text[1:]
                                    corpus.append(message_text)
    return corpus


def main():
    filename = 'hangouts.json'  # Hangouts chat log data from Google Takeout
    with open(filename, 'rb') as file:
        data = json.load(file)

    # Get list of conversations and choose which one to use for data extraction
    convos = get_conversations(data)
    selection_choices = {}
    print('{:<3} {:<35} {:<50}'.format('No.', 'Convo ID', 'Participants'))
    for index, (key, value) in enumerate(convos.items(), start=1):
        print('{num:<3} {convo_id:<35} {participants}'.format(num=index, convo_id=key, participants=', '.join(value)))
        selection_choices[index] = key
    selection = int(input('Enter no. of conversation to use: '))
    print(selection_choices)
    selected_convo_id = selection_choices[selection]

    # Generate corpus of message text using the chosen conversation
    corpus = generate_corpus(data, selected_convo_id)

    # Output text file with each message on a new line
    with open('corpus.txt', 'w', encoding='utf-8') as file:
        for line in corpus:
            file.write('{0}\n'.format(line))

if __name__ == '__main__':
    main()
