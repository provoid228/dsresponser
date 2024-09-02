import threading
import requests
from random import randint
from time import sleep
from json import loads, load
from os import system
from ctypes import windll
from sys import stderr
from loguru import logger
from urllib3 import disable_warnings
from telebot import TeleBot, apihelper

# Setup logging and disable warnings
disable_warnings()
logger.remove()
logger.add(stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - <level>{message}</level>")
clear = lambda: system('cls')

# Configure console title and logging
print('Telegram Channel - https://t.me/n4z4v0d & https://t.me/earlyberkut\n')
windll.kernel32.SetConsoleTitleW('Discord Bot | by NAZAVOD&EARLY BERKUT')
lock = threading.Lock()

# Function to load triggers and responses from a JSON file
def load_triggers_and_responses(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = load(f)
    
    # Create a dictionary for quick lookup
    triggers_responses = {item['trigger'].lower(): item['response'] for item in data}
    
    return triggers_responses

# Load trigger phrases and responses from JSON file
TRIGGERS_AND_RESPONSES = load_triggers_and_responses('triggers_responses.json')

# Functions to load data from files
def load_tokens(tokens_file):
    with open(tokens_file, 'r', encoding='utf-8') as file:
        return [token.strip() for token in file]

# Updated function to manually input proxy settings
def input_proxy():
    proxies = []
    while True:
        proxy = input('Введите proxy (формат: тип://ip:порт или пустую строку для завершения): ')
        if not proxy:
            break
        proxies.append(proxy)
    return proxies

# Function to handle user input
def get_user_input():
    tokens_file = input('TXT файл с токенами Discord: ')
    tokens = load_tokens(tokens_file)

    if ':' not in tokens[0]:
        chat_id = int(input('Введите ChatID Discord: '))
    else:
        chat_id = 0

    use_telegram = input('Оповещать вас в Telegram при ответах на ваши сообщения и упоминании вас (y/N): ').lower() == 'y'
    
    telegram_config = {}
    if use_telegram:
        telegram_config['bot_token'] = input('Введите токен бота Telegram: ')
        telegram_config['tg_user_id'] = int(input('Введите ваш UserID TG: '))
        use_proxy_telegram = input('Использовать proxy для Telegram? (y/N): ').lower() == 'y'
        
        if use_proxy_telegram:
            proxy_type = input('Введите тип proxy для Telegram (https/socks4/socks5): ')
            proxy_str = input('Введите proxy для Telegram (ip:port or user:pass@ip:port): ')
            apihelper.proxy = {'https': f'{proxy_type}://{proxy_str}'}
    
    delete_message_after_send = input('Удалять сообщение после отправки? (y/N): ').lower() == 'y'
    sleep_before_delete_msg = int(input('Время сна перед удалением сообщения после отправки: ')) if delete_message_after_send else None
    
    use_proxy = input('Использовать proxy? (y/N): ').lower() == 'y'
    
    proxy_config = {}
    if use_proxy:
        proxy_config['proxy_type'] = input('Введите тип proxy (http/https/socks4/socks5): ')
        proxy_config['proxies'] = input_proxy()  # Manually input proxy details
    
    delay_first_msg = input('Задержка перед отправкой ПЕРВОГО сообщения (пример: 0-20, или 50): ')
    delay_every_msg = input('Задержка перед отправкой последующих сообщений (пример: 0-20, или 50): ')
    typing_delay = input('Время имитации печатания (пример: 0-20, или 50): ')
    
    return {
        'tokens': tokens,
        'chat_id': chat_id,
        'telegram': telegram_config,
        'delete_message_after_send': delete_message_after_send,
        'sleep_before_delete_msg': sleep_before_delete_msg,
        'proxy': proxy_config,
        'delay_first_msg': delay_first_msg,
        'delay_every_msg': delay_every_msg,
        'typing_delay': typing_delay
    }

def get_proxy(proxy_config):
    return proxy_config['proxies'].pop(0) if 'proxies' in proxy_config and proxy_config['proxies'] else None

def check_tags(session, chat_id, ds_user_id, bot, username, token, tg_user_id):
    last_id = None
    msg_ids, all_ids = [], []
    
    while True:
        try:
            r = session.get(f'https://discord.com/api/v9/channels/{chat_id}/messages?limit=100')
            response_data = loads(r.text)
            
            if 'retry_after' in response_data:
                sleep_time = response_data['retry_after']
                logger.error(f'Error: {response_data["message"]}, sleeping {sleep_time}')
                sleep(sleep_time)
                continue
            
            for msg in response_data:
                all_ids.append(msg['id'])
            
            if last_id not in all_ids:
                all_ids.clear()
                msg_ids.clear()
            
            for msg in response_data:
                current_id = msg['id']
                if 'referenced_message' in msg:
                    if str(ds_user_id) == str(msg['referenced_message']['author']['id']) and current_id not in msg_ids:
                        reply_content = msg['content']
                        logger.success(f'[{username}] ваше сообщение переслали в ChatID: {chat_id}')
                        msg_ids.append(current_id)
                        notify_telegram(bot, tg_user_id, chat_id, username, token, current_id, reply_content)
                
                current_message = msg['content'].replace('\n', '').replace('\r', '')
                if f'<@!{str(ds_user_id)}>' in current_message and current_id not in msg_ids:
                    logger.success(f'[{username}] вас упомянули в ChatID: {chat_id}')
                    msg_ids.append(current_id)
                    notify_telegram(bot, tg_user_id, chat_id, username, token, current_id, current_message)
                
                # Check for trigger phrases and respond if found
                reply_message = check_for_triggers(current_message)
                if reply_message:
                    send_message(session, chat_id, reply_message, 1, 0)  # Send reply immediately
                
                last_id = current_id
        except Exception as error:
            logger.error(f'[{username}] ошибка при парсе сообщений: {str(error)}')

def notify_telegram(bot, tg_user_id, chat_id, username, token, msg_id, content):
    try:
        bot.send_message(tg_user_id, f'Сообщение\nChatID: {chat_id}\nUsername: {username}\nToken: {token}\nMsg id: {msg_id}\nMsg text: {content}')
        logger.success('Сообщение в Telegram успешно отправлено')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения в Telegram: {str(error)}')

def send_message(session, chat_id, message, typing_delay, sleep_time):
    try:
        session.post(f'https://discord.com/api/v9/channels/{chat_id}/typing')
        sleep(typing_delay)
        r = session.post(f'https://discord.com/api/v9/channels/{chat_id}/messages', json={'content': message, 'tts': False})
        return loads(r.text).get('id')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {str(error)}')

def delete_message(session, chat_id, message_id, sleep_time, username):
    sleep(sleep_time)
    r = session.delete(f'https://discord.com/api/v9/channels/{chat_id}/messages/{message_id}')
    if r.status_code == 204:
        logger.success(f'Сообщение с ID {message_id} успешно удалено для {username}')
    else:
        logger.error(f'Ошибка при удалении сообщения для [{username}], статус ответа: {r.status_code}, содержимое ответа: {r.text}')

def check_for_triggers(message_content):
    """Check if the message content contains any of the trigger phrases."""
    message_content_lower = message_content.lower()
    for trigger, response in TRIGGERS_AND_RESPONSES.items():
        if trigger in message_content_lower:
            return response
    return None

def main_thread(token, config):
    session = requests.Session()
    session.headers['authorization'] = token.split(':')[0] if ':' in token else token
    
    if config['proxy']:
        session.proxies.update({'http': f'{config["proxy"]["proxy_type"]}://{get_proxy(config["proxy"])}',
                                'https': f'{config["proxy"]["proxy_type"]}://{get_proxy(config["proxy"])}'})

    try:
        user_info = loads(session.get('https://discordapp.com/api/users/@me').text)
        if 'username' not in user_info:
            raise ValueError('Invalid Token')

        username = user_info['username']
        ds_user_id = user_info['id']
        chat_id = config['chat_id'] if ':' not in token else token.split(':')[1]

        if config['telegram']:
            bot = TeleBot(config['telegram']['bot_token'])
            tg_user_id = config['telegram']['tg_user_id']
            threading.Thread(target=check_tags, args=(session, chat_id, ds_user_id, bot, username, token, tg_user_id)).start()

        first_sleep_time = randint(*map(int, config['delay_first_msg'].split('-'))) if '-' in config['delay_first_msg'] else int(config['delay_first_msg'])
        logger.info(f'Первый запуск для [{username}], сплю {first_sleep_time} секунд перед первым сообщением')
        sleep(first_sleep_time)

    except ValueError as error:
        logger.error(f'Ошибка: {str(error)}')
        return
    
    while True:
        try:
            lock.acquire()
            typing_delay = randint(*map(int, config['typing_delay'].split('-'))) if '-' in config['typing_delay'] else int(config['typing_delay'])
            lock.release()

            # Check if the message matches any trigger phrase
            reply_message = check_for_triggers(user_info['username'])  # Assuming you want to check triggers based on the username
            if reply_message:
                message_id = send_message(session, chat_id, reply_message, typing_delay, config['delay_every_msg'])
                if message_id:
                    logger.success(f'Сообщение [{reply_message}] от [{username}] успешно отправлено')

                    if config['delete_message_after_send']:
                        threading.Thread(target=delete_message, args=(session, chat_id, message_id, config['sleep_before_delete_msg'], username)).start()

            sleep_time = randint(*map(int, config['delay_every_msg'].split('-'))) if '-' in config['delay_every_msg'] else int(config['delay_every_msg'])
            logger.info(f'Сплю {sleep_time} секунд для [{username}]')
            sleep(sleep_time)

        except Exception as error:
            logger.error(f'Ошибка для [{username}]: {str(error)}')
            break

# Main execution
def main():
    clear()
    config = get_user_input()
    
    for token in config['tokens']:
        threading.Thread(target=main_thread, args=(token, config)).start()

if __name__ == '__main__':
    main()
