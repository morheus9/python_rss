# Telegram bot on python, which send rss feed to your group
Add to your channel your Bot, then create virtual env:
```
uv venv
source .venv/bin/activate
uv pip install .
```
Add env and start:
```
export BOT_TOKEN="your_telegram_bot_token"
export CHANNEL="@your_channel_name"
python script.py
```