import os
import logging
from pprint import pprint
from time import sleep
from urllib.parse import urljoin

import requests
import telegram
from dotenv import load_dotenv


class TelegramLogsHandler(logging.Handler):

    def __init__(self, tg_bot, chat_id):
        super().__init__()
        self.chat_id = chat_id
        self.tg_bot = tg_bot

    def emit(self, record):
        log_entry = self.format(record)
        self.tg_bot.send_message(chat_id=self.chat_id, text=log_entry)


def get_dvmn_api_response(timestamp):
    response = requests.get(
        'https://dvmn.org/api/long_polling/',
        headers={'Authorization': os.getenv('DVMN_API_TOKEN')},
        params={'timestamp': timestamp},
        timeout=100,
    )
    response.raise_for_status()

    dvmn_api_response = response.json()

    return dvmn_api_response


def send_telegram_notification(bot, chat_id, dvmn_api_response):
    notifications = {
        'success': '\nУ вас проверили работу "{}".\nСсылка на работу: {}\nПреподавателю все понравилось, можно приступать к следующему уроку!\n',
        'fail': '\nУ вас проверили работу "{}".\nСсылка на работу: {}\nК сожалению в работе нашлись ошибки. Исправьте их и отправьте работу на проверку снова.\n',
    }

    for attempt in dvmn_api_response['new_attempts']:
        lesson_title = attempt['lesson_title']
        lesson_url = urljoin('https://dvmn.org/', attempt['lesson_url'])

        if attempt['is_negative']:
            notification = notifications['fail'].format(lesson_title, lesson_url)
        else:
            notification = notifications['success'].format(lesson_title, lesson_url)

        bot.send_message(
            text=notification,
            chat_id=chat_id
        )


def main():
    load_dotenv()

    bot = telegram.Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
    chat_id = os.getenv('TELEGRAM_USER_ID')
    timestamp = ''

    logger = logging.getLogger('Logger')
    logger.setLevel(logging.INFO)
    logger.addHandler(TelegramLogsHandler(bot, chat_id))

    logger.info('Bot started. Waiting new lesson review...')

    while True:
        try:
            dvmn_api_response = get_dvmn_api_response(timestamp)
        except requests.exceptions.ReadTimeout as read_timeout_error:
            continue
        except requests.exceptions.ConnectionError as connection_error:
            logger.exception('Bot crushed with error:\n\n')
            sleep(100)

        if dvmn_api_response['status'] == 'timeout':
            timestamp = dvmn_api_response['timestamp_to_request']
        elif dvmn_api_response['status'] == 'found':
            timestamp = dvmn_api_response['last_attempt_timestamp']

            send_telegram_notification(bot, chat_id, dvmn_api_response)


if __name__ == '__main__':
    main()
