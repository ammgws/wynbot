# standard library
import datetime as dt
# third party
import simplejson as json


def main():
    filename = 'hangouts.json'
    friend_id = 'UgwpNx2Do2FFgMUbNFR4AaABAQ'  # wyn

    data = json.load(open(filename, 'rb'))

    chat_log_dict = {}
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
                            if conversation_id == friend_id:
                                timestamp_us = int(conversation['timestamp'])  # epoch time in microseconds
                                timestamp = dt.datetime.fromtimestamp(timestamp_us/1000000)  # convert to epoch seconds
                                timestamp_str = timestamp.strftime("%Y%m%d_%Hh%Mm%Ss.%f")
                                try:
                                    chat_log_dict[timestamp_str] = line['text'] + '.'
                                except:
                                    pass

        with open('message_db.json', 'w') as json_file:
            json_file.write(json.dumps(chat_log_dict))

if __name__ == '__main__':
    main()
