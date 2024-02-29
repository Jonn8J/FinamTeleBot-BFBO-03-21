import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from my_config.Cfg import Config
import aiofiles
from io import StringIO
import asyncio

"""Программу надо запускать минимум через минуту после последнего запуска. Иначе будет неправильно отображение"""


async def read_file_async(file_path):
    async with aiofiles.open(file_path, mode='r') as file:
        content = await file.read()
        return content


def plot_trades(user_id, scale_item, security_board, ticker, time_frame, trade_data_container):
    data = asyncio.run(read_file_async(f'{Config.FilePath}{security_board}.{ticker}_{time_frame}.txt'))
    data = pd.read_csv(StringIO(data), delimiter='\t')
    data['datetime'] = pd.to_datetime(data['datetime'], format='%d.%m.%Y %H:%M')

    # Получаем последнюю дату из столбца 'datetime'
    chosen_date = data['datetime'].max().date()

    # Фильтрация данных по выбранной дате
    df = data[data['datetime'].dt.date == chosen_date]

    # Ограничиваем количество отображаемых баров (например, последние 100 баров)
    df = df.tail(100)

    # Создание фигуры с заданными размерами.
    plt.subplots(figsize=(16, 9))  # fig, ax = plt.subplots(figsize=(16, 9), gridspec_kw={'top': 0.95, 'bottom': 0.1})
    # Значения размеров баров для нормального минутного графика
    # надо приближать чтобы нормально понять
    # Для минутного нужно сделать маштаб в пару часов чтобы было все понятно сразу и приближать не надо было
    width = 0.0005
    width2 = 0.00005

    # Определяем типы баров (возрастающий, убывающий или статичный)
    up = df[df.close > df.open]
    down = df[df.close < df.open]
    stop = df[df.close == df.open]
    # Цвета для баров
    col1 = 'green'
    col2 = 'red'
    col3 = 'black'

    # Рисуем возрастающие бары
    plt.bar(up.datetime, up.close - up.open, width, bottom=up.open, color=col1)
    plt.bar(up.datetime, up.high - up.close, width2, bottom=up.close, color=col1)
    plt.bar(up.datetime, up.low - up.open, width2, bottom=up.open, color=col1)
    # Рисуем убывающие бары
    plt.bar(down.datetime, down.close - down.open, width, bottom=down.open, color=col2)
    plt.bar(down.datetime, down.high - down.open, width2, bottom=down.open, color=col2)
    plt.bar(down.datetime, down.low - down.close, width2, bottom=down.close, color=col2)
    # Рисуем статичные бары
    plt.bar(stop.datetime, pow(10, scale_item-1) * 5, width, bottom=stop.open, color=col3)
    plt.bar(stop.datetime, stop.high - stop.open, width2, bottom=stop.open, color=col3)
    plt.bar(stop.datetime, stop.low - stop.close, width2, bottom=stop.close, color=col3)

    for trade_data in trade_data_container:
        timestamp = trade_data['timestamp']
        price = trade_data['price']
        action = trade_data['action']
        if action == 'buy':
            plt.scatter(timestamp, price, color='limegreen', marker='^', s=100, edgecolors='black', label='Buy')
        elif action == 'sell':
            plt.scatter(timestamp, price, color='tomato', marker='v', s=100, edgecolors='black', label='Sell')

    # Настройка осей и заголовка графика
    plt.xlabel(chosen_date.strftime('%d.%m.%Y'))
    plt.ylabel('Цена')
    plt.title('График баров')

    # Поворот и форматирование дат на оси X
    plt.xticks(rotation=45, ha='right')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y %H:%M'))

    # Добавление сетки на график
    plt.grid(True)

    # Увеличение количества пометок на осях
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    plt.gca().yaxis.set_major_locator(plt.MultipleLocator(pow(10, scale_item+1)))
    # Установка интервала оси x в 15 минут
    plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 5)))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # Смена формата времени на оси x
    plt.gcf().autofmt_xdate()

    plt.savefig(f'data/graph_{user_id}.png')
