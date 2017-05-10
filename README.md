# wynbot
Hangouts chatbot that mimics your friends

##### Requirements
* GMail or Google Apps account which can use Hangouts
* Python 3.6+

##### Installation
git clone https://github.com/ammgws/wynbot.git

##### Before Use
1. Go to [Google Takeout](https://takeout.google.com/settings/takeout) and export your Hangouts chat data.
2. Go to [Google APIs](https://console.developers.google.com/apis/) and generate secret client ID/password.

##### Usage


##### Run via crontab
Example, once per day at 9am:
```
WYNBOT_DIR = /path/to/wynbot
WYNBOT_VENV = /path/to/virtualenv/bin/python
00 9 * * * /usr/bin/nice -n 20 $WYNBOT_VENV $WYNBOT_DIR/wynbot.py -s3 2>&1
```
