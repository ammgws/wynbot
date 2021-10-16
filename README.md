# wynbot
Sends or generates a message mimicking your friends based on your Hangouts chat history.

##### No longer maintained

Archiving this repo as no longer use Google Hangouts.

##### Requirements
* GMail or Google Apps account which can use Hangouts
* Python 3.6+

##### Installation
```sh
git clone https://github.com/ammgws/wynbot.git  
cd wynbot  
pip install -r requirements.txt
```

##### Before Use
1. Go to [Google Takeout](https://takeout.google.com/settings/takeout) and export your Hangouts chat data.
2. Go to [Google APIs](https://console.developers.google.com/apis/) and generate secret client ID/password.
3. Generate corpus for wynbot to use: `python build_db.py Hangouts.json`

##### Usage
```
Usage: wynbot.py [OPTIONS] RECIPIENT

  Login to Hangouts, send generated message and disconnect.

Options:
  --config-path PATH        Path to directory containing config file. Defaults
                            to $XDG_CONFIG_HOME/wynbot.
  --cache-path PATH         Path to directory to store logs and such. Defaults
                            to $XDG_CACHE_HOME/wynbot.
  --no-log                  Disables logging.
  -n, --num_chars INTEGER   max character length for the generated message.
  -s, --state_size INTEGER  state size for Markov model.
  --print-only              Print message to stdout, not Hangouts.
  --prefix TEXT             String to prefix message with.
  --help                    Show this message and exit.
```

Example:
`python wynbot.py --print-only --prefix="[Robot] " "recipientJID@public.talk.google.com"`
