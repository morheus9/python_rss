import sys
import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_titles (
                title TEXT PRIMARY KEY
            )
        """)
        self.conn.commit()

    def add_title(self, title):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sent_titles (title) VALUES (?)", (title,)
        )
        self.conn.commit()

    def title_exists(self, title):
        self.cursor.execute("SELECT 1 FROM sent_titles WHERE title = ?", (title,))
        return self.cursor.fetchone() is not None

    def close(self):
        self.conn.close()


class TelegramBot:
    def __init__(self, token, channel):
        self.token = token
        self.channel = channel
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.channel,
            "text": text,
            "parse_mode": "HTML",
        }
        response = requests.post(url, json=payload)
        return response.status_code == 200


class RSSParser:
    def __init__(self, url):
        self.url = url

    def parse_feed(self):
        try:
            feed = feedparser.parse(self.url)
            if feed.bozo:
                logging.error(f"RSS parsing error: {feed.bozo_exception}")
                return None
            return feed
        except Exception as e:
            logging.error(f"Error fetching RSS feed: {str(e)}")
            return None


class Application:
    def __init__(self):
        self._validate_env()
        self.db = DatabaseManager("sent_titles.db")
        self.bot = TelegramBot(os.getenv("BOT_TOKEN"), os.getenv("CHANNEL"))
        self.parser = RSSParser("https://europeanconservative.com/feed")

    def _validate_env(self):
        required_vars = ["BOT_TOKEN", "CHANNEL"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            logging.error(f"Missing environment variables: {', '.join(missing)}")
            sys.exit(1)

    def _process_content(self, content):
        if not content:
            return ""

        if isinstance(content, list):
            content_text = content[0].value
        else:
            content_text = content

        soup = BeautifulSoup(content_text, "html.parser")
        clean_text = soup.get_text().strip()
        return clean_text.split("\n")[0] if clean_text else ""

    def process_entry(self, entry):
        title = entry.title.strip().lower()

        if self.db.title_exists(title):
            logging.info(f"Skipping existing title: {title}")
            return False

        content = self._process_content(entry.get("content", entry.get("description")))
        link = entry.link

        message = f"<b>{entry.title}</b>\n\n{content}\n\n<a href='{link}'>Read more</a>"

        if len(message) > 4096:
            message = message[:4096] + "..."

        if self.bot.send_message(message):
            self.db.add_title(title)
            logging.info(f"Successfully sent: {title}")
            return True

        logging.warning(f"Failed to send: {title}")
        return False

    def run(self):
        logging.info("Starting application")
        while True:
            try:
                feed = self.parser.parse_feed()
                if not feed:
                    logging.error("Invalid RSS feed")
                    time.sleep(600)
                    continue

                for entry in feed.entries:
                    self.process_entry(entry)

                logging.info("Cycle completed, sleeping for 1 hour")
                time.sleep(3600)

            except KeyboardInterrupt:
                logging.info("Received exit signal, shutting down")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {str(e)}")
                time.sleep(300)


if __name__ == "__main__":
    app = Application()
    app.run()
