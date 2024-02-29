import pandas as pd
import asyncio
import telebot
import os
from telebot import types
from my_config.Cfg import Config
import logging
import os.path
from Bars_graph import plot_trades
from PIL import Image
import Live_strategy
import sys
import signal

bot = telebot.TeleBot(Config.Telegram_Token)

user_data = {}

stock_codes = {
    'Сбербанк': 'SBER',
    'ВТБ': 'VTBR',
    'Газпром': 'GAZP',
    'MOEX': 'MOEX',
    'Ozon': 'OZON',
    'Тинькофф': 'TCSG',
    'Лукойл': 'LKOH',
    'РуссНЕФТЬ': 'RNFT',
    'Роснефть': 'ROSN',
    'Яндекс': 'YNDX'
}
# Базовая настройка логирования
logging.basicConfig(level=logging.INFO)

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Функция для сохранения данных пользователя в файл
async def save_user_data_to_file(message):
    user_id = message.chat.id
    try:
        file_name = os.path.join('data', 'users.txt')
        file_exists = os.path.isfile(file_name)
        print(user_data)
        if user_id in user_data:
            new_data = pd.DataFrame([user_data[user_id]])
            print(new_data)
            new_data.index = new_data['user_id']
            new_data = new_data[['client_id', 'api_key', 'share', 'trading_amount']]
            if file_exists:  # Если файл существует
                # Загружаем существующие данные из файла
                existing_data = pd.read_csv(file_name, sep='\t', index_col='user_id')
                new_data = pd.concat([existing_data, new_data]).drop_duplicates(
                    keep='last').sort_index()  # Объединяем файл с данными из Finam, убираем дубликаты, сортируем заново
            # Сохраняем обновленные данные в файл
            new_data.to_csv(file_name, sep='\t')
            bot.send_message(user_id, 'Ваши данные успешно сохранены.')
        else:
            bot.send_message(user_id, 'Произошла ошибка. Попробуйте заново.')
    except ValueError:
        bot.send_message(user_id, 'Произошла ошибка. Попробуйте заново.')


# Функция для установки суммы для торговли
def set_trading_amount(message):
    user_id = message.chat.id
    try:
        trading_amount = float(message.text)
        user_data[user_id]['trading_amount'] = trading_amount
        bot.send_message(user_id, f'Сумма для торговли установлена: {trading_amount} руб.\n')
        bot.send_message(user_id, "Бот завершает свою работу.")
        asyncio.run(save_user_data_to_file(message))
    except ValueError:
        bot.send_message(user_id, 'Пожалуйста, введите корректное числовое значение.')
        bot.register_next_step_handler(message, set_trading_amount)


# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_messages(message):

    if '/start' in message.text:
        start(message)
    elif '/run' in message.text:
        run(message)
    elif '/shutdown' in message.text:
        shutdown(message)
    elif '/stat' in message.text:
        get_stat(message)
    elif '/graph' in message.text:
        graph_command(message)
    elif '/set_stock' in message.text:
        set_stock(message)
    elif '/set_id' in message.text:
        set_id(message)
    elif '/set_api' in message.text:
        set_api(message)
    elif '/help' in message.text:
        help_command(message)
    else:
        process_command(message)


@bot.message_handler(commands=['shutdown'])
def shutdown(message):
    user_id = message.chat.id

    bot.stop_bot()
    # По завершении бота отправляем сигнал завершения всем процессам
    os.kill(os.getpid(), signal.SIGINT)
    sys.exit()


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.chat.id
    bot.send_message(user_id, f'Список команд:\n'
                              f'/start - запуск бота\n'
                              f'set_id - ввод вашего торгового счёта\n'
                              f'/set_api - ввод вашего API ключа\n'
                              f'/set_stock - ввод акции для торговли и баланса\n'
                              f'/graph - вывод графика акции\n'
                              f'/stat - вывод статистики\n'
                              f'/run - запуск торговли\n'
                              f'/shutdown - остановка торговли')


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    file_name = 'data/users.txt'
    file_exists = os.path.isfile(file_name)

    if file_exists:
        # Читаем существующие данные из файла
        existing_data = pd.read_csv(file_name, sep='\t', index_col='user_id')

        if user_id in existing_data.index:
            bot.send_message(user_id, "Вы прошли настройку.\nДля запуска бота нажмите /run\n")
            return
    user_data[user_id] = {'user_id': user_id}
    # Если файл не существует или user_id не найден, продолжаем с настройкой
    bot.send_message(user_id, "Для того чтобы пройти настройку, введите /set_id")


@bot.message_handler(commands=['run'])
def run(message):
    user_id = message.chat.id
    if user_id not in Live_strategy.active_strategies:
        asyncio.run(Live_strategy.handle_command_activate_strategy(user_id))
    else:
        bot.send_message(user_id, 'Вы уже запустили торгового бота')


# Обработчик команды /set_stock
@bot.message_handler(commands=['set_stock'])
def set_stock(message):
    user_id = message.chat.id
    stocks_list = list(stock_codes.keys())
    markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)

    for stock in stocks_list:
        button = types.KeyboardButton(stock)
        markup.add(button)

    bot.send_message(user_id, "Выберите акцию, на которой вы хотите торговать:", reply_markup=markup)
    bot.register_next_step_handler(message, set_stock_amount)


# Обработчик ввода суммы для торговли
def set_stock_amount(message):
    user_id = message.chat.id

    # Получаем код акции из словаря stock_codes по названию акции
    selected_stock_name = message.text
    selected_stock_code = stock_codes.get(selected_stock_name, 'Неизвестная акция')

    # Обновляем данные пользователя
    user_data[user_id]['ticker'] = selected_stock_code
    user_data[user_id]['security_board'] = 'TQBR'
    bot.send_message(user_id, f'Выбрана акция: {selected_stock_code}\nВведите сумму для торговли этой акцией в рублях.')
    bot.register_next_step_handler(message, set_trading_amount)


# Обработчик команды /set_id
@bot.message_handler(commands=['set_id'])
def set_id(message):
    user_id = message.chat.id
    bot.send_message(user_id, f'Введите ваш торговый счёт:')
    bot.register_next_step_handler(message, set_id_out)


# Обработчик ввода торгового счета
def set_id_out(message):
    user_id = message.chat.id
    user_data[user_id]['client_id'] = message.text
    bot.send_message(user_id, f'Ваш торговый счёт: {message.text}.\n')
    set_api(message)


# Обработчик команды /set_api
@bot.message_handler(commands=['set_api'])
def set_api(message):
    user_id = message.chat.id
    bot.send_message(user_id, f'Введите ваш API ключ Финам:')
    bot.register_next_step_handler(message, set_api_out)


# Обработчик ввода API ключа
def set_api_out(message):
    user_id = message.chat.id
    api = message.text
    user_data[user_id]['api_key'] = api  # Исправляем ключ 'API ключ' на 'api_key'
    bot.send_message(user_id, f'Ваш API ключ: {api}\nДля дальнейшей настройки введите /set_stock')


# Обработка других команд
def process_command(message):
    # Обработка других команд
    command = message.text[1:]  # Убираем первый символ '/', чтобы получить имя команды
    user_id = message.chat.id

    if command == 'start':
        start(message)
    elif command == 'set_stock':
        set_stock(message)
    # Добавьте обработку других команд по мере необходимости
    else:
        bot.send_message(user_id, f"Для начала введите /start")


@bot.message_handler(commands=['graph'])
def graph_command(message):
    user_id = message.chat.id
    # Получаем код акции из данных пользователя
    selected_stock_code = user_data.get(user_id, {}).get('ticker', '')

    file_path = f"data/graph_{user_id}.png"

    if user_id not in Live_strategy.active_strategies:
        bot.send_message(user_id, 'График отсутствует. Вы не запустили торгового бота')
        return
    else:
        if user_id in Live_strategy.graph_user_data:
            user_graph_config = Live_strategy.graph_user_data[user_id]

            # Используйте значения из user_graph_config для создания графика
            plot_trades(user_graph_config['user_id'], user_graph_config['scale'],
                        user_graph_config['security_board'], user_graph_config['ticker'],
                        user_graph_config['timeframe'], user_graph_config['trade_data'])

            img = Image.open(file_path)
            bot.send_photo(user_id, img, caption=f'График котировок акции {selected_stock_code}')
        else:
            bot.send_message(user_id, 'График пока не может быть создан. Попробуйте позже')


@bot.message_handler(commands=['stat'])
def get_stat(message):
    user_id = message.chat.id
    if user_id in Live_strategy.user_message:
        bot.send_message(user_id, Live_strategy.user_message[user_id])
    else:
        bot.send_message(user_id, 'Статистика еще не собрана. Попробуйте позже.')


bot.polling(non_stop=True)
