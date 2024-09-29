import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sqlite3

# URL RSS-ленты
rss_url = "https://europeanconservative.com/feed"

# Получаем токен вашего бота из переменной окружения
bot_token = os.getenv("BOT_TOKEN")
# Идентификатор канала
channel_id = "@European_Conservative"

# Подключение к базе данных SQLite
conn = sqlite3.connect("sent_titles.db")
cursor = conn.cursor()

# Создание таблицы для хранения заголовков, если она не существует
cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_titles (
    title TEXT PRIMARY KEY
)
""")
conn.commit()


# Функция для добавления заголовка в базу данных
def add_title_to_db(title):
    cursor.execute("INSERT OR IGNORE INTO sent_titles (title) VALUES (?)", (title,))
    conn.commit()


# Функция для проверки, был ли заголовок отправлен
def title_exists_in_db(title):
    cursor.execute("SELECT 1 FROM sent_titles WHERE title = ?", (title,))
    return cursor.fetchone() is not None


# Функция для отправки сообщения в Telegram
def send_message(text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "HTML",  # Используйте HTML для форматирования
    }
    response = requests.post(url, json=payload)
    return response


# Функция для получения заголовков сообщений из канала
def get_recent_messages():
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    response = requests.get(url)
    if response.status_code == 200:
        updates = response.json().get("result", [])
        for update in updates:
            if "message" in update and "text" in update["message"]:
                # Нормализуем заголовок
                add_title_to_db(update["message"]["text"].strip().lower())
    else:
        print("Ошибка при получении обновлений:", response.json())


# Функция для парсинга RSS-ленты и отправки новых постов
def check_and_send_posts():
    # Парсинг RSS-ленты
    feed = feedparser.parse(rss_url)

    # Проверка на наличие ошибок
    if feed.bozo:
        print("Ошибка при парсинге RSS-ленты:", feed.bozo_exception)
        return

    # Обрабатываем записи в RSS-ленте
    for entry in feed.entries:
        title = entry.title.strip().lower()  # Нормализуем заголовок

        if not title_exists_in_db(title):  # Проверяем, отправляли ли мы этот пост
            link = entry.link

            # Используем BeautifulSoup для очистки контента
            content = entry.get("content", entry.description)
            if isinstance(content, list):
                content_text = content[0].value
            else:
                content_text = content

            # Очищаем текст от HTML-тегов
            soup = BeautifulSoup(content_text, "html.parser")
            clean_text = soup.get_text().strip()

            # Извлекаем только первый параграф
            first_paragraph = clean_text.split("\n")[0]  # Получаем первый параграф

            # Формируем сообщение
            message = f"<b>{entry.title}</b>\n\n{first_paragraph}\n\n<a href='{link}'>Read more</a>"

            # Обрезаем сообщение, если оно слишком длинное
            if len(message) > 4096:
                message = message[:4096] + "..."  # Обрезаем и добавляем многоточие

            # Отправляем сообщение в Telegram
            response = send_message(message)

            # Проверяем ответ от Telegram
            if response.status_code == 200:
                print("Сообщение успешно отправлено. Ждем 1 час")
                add_title_to_db(title)  # Добавляем заголовок в базу данных
            else:
                print("Ошибка при отправке сообщения:", response.json())

            time.sleep(3600)  # Ждем 1 час (3600 секунд)


# Основной цикл
while True:
    get_recent_messages()  # Получаем последние сообщения перед проверкой новых постов
    check_and_send_posts()
    time.sleep(3600)  # Ждем 1 час перед следующей проверкой
