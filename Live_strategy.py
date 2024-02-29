import asyncio
import os.path
import math
import logging
from datetime import datetime
import aiofiles
from io import StringIO
import pandas as pd
import numpy as np
from FinamPy import FinamPy
from FinamPy.proto.tradeapi.v1.candles_pb2 import IntradayCandleTimeFrame
from keras.models import load_model
from keras.utils import img_to_array
from my_config.Cfg import Config
from Bars import save_candles_to_file
import functions_nn

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

active_strategies = {}  # Словарь для отслеживания активных стратегий по user_id
user_message = {}
graph_user_data = {}
user_data = {}
task = {}
model = load_model(os.path.join("NN_winner", "cnn_Open.hdf5"))


async def read_file_async(file_path):
    async with aiofiles.open(file_path, mode='r') as file:
        content = await file.read()
        return content


class LiveStrategy:

    def __init__(self, user_id, api_key, ticker, timeframe, days_back, check_interval, trading_hours_start, trading_hours_end,
                 security_board, client_id, balance):
        self.user_id = user_id
        self.api_key = api_key
        self.ticker = ticker
        self.timeframe = timeframe
        self.days_back = days_back
        self.check_interval = check_interval
        self.trading_hours_start = trading_hours_start
        self.trading_hours_end = trading_hours_end
        self.security_board = security_board
        self.client_id = client_id
        self.balance = balance
        self.position = False
        self.ask_price = float('nan')
        self.bid_price = float('nan')
        self.counter = int()
        self.scale = int
        self.portfolio = self.balance
        self.stop_loss = float
        self.trade_data_container = []
        self.stop_event = asyncio.Event()

    async def add_buy_data(self, timestamp, price, quantity):
        # Метод для добавления данных о покупке в контейнер
        self.trade_data_container.append({'action': 'buy', 'timestamp': timestamp, 'price': price, 'quantity': quantity})

    async def add_sell_data(self, timestamp, price, quantity):
        # Метод для добавления данных о продаже в контейнер
        self.trade_data_container.append({'action': 'sell', 'timestamp': timestamp, 'price': price, 'quantity': quantity})

    async def bars_data(self, fp_provider):
        await save_candles_to_file(self.security_board, self.ticker, True, IntradayCandleTimeFrame.INTRADAYCANDLE_TIMEFRAME_M1, False, False, False, fp_provider)

    async def live_check_position(self, model, fp_provider):
        await self.bars_data(fp_provider)
        df = await read_file_async(f'{Config.FilePath}{self.security_board}.{self.ticker}_{self.timeframe}.txt')
        df = pd.read_csv(StringIO(df), delimiter='\t')
        df['datetime'] = pd.to_datetime(df['datetime'], format='%d.%m.%Y %H:%M')

        period_sma_slow = 64
        period_sma_fast = 16
        draw_window = 128

        df['sma_fast'] = df['close'].rolling(period_sma_fast).mean()
        df['sma_slow'] = df['close'].rolling(period_sma_slow).mean()
        df.dropna(inplace=True)

        df_in = df.copy()
        _close_in = df_in["close"].tolist()
        sma_fast = df_in["sma_fast"].tolist()
        sma_slow = df_in["sma_slow"].tolist()
        j = len(_close_in)

        _sma_fast_list = sma_fast[j - draw_window:j]
        _sma_slow_list = sma_slow[j - draw_window:j]
        _closes_list = _close_in[j - draw_window:j]

        img = functions_nn.generate_img(_sma_fast_list, _sma_slow_list, _closes_list, draw_window)
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        _predict = model.predict(img_array, verbose=0)
        _class = 0

        if _predict[0][1] >= 0: _class = 1
        print("Predicted: ", model.predict(img_array), " class = ", _class)

        if not self.position:
            if _class == 1:
                self.position = True
                self.ask_price = await self.get_order_book_price(fp_provider, 'asks')
                self.stop_loss = 0.992 * self.ask_price
                print("Ask Price (before):", self.ask_price)
                self.counter = math.floor(self.balance / self.ask_price) if self.ask_price else None
                self.portfolio = self.balance
                self.balance = round(self.balance - (self.ask_price * self.counter), abs(self.scale)) if self.ask_price and self.counter else None
                print("Ask Price (after):", self.ask_price)
                print("Counter:", self.counter)
                print("Balance (after):", self.balance)
                await self.add_buy_data(df['datetime'].iloc[-1], self.ask_price, self.counter)
        elif self.position:
            self.bid_price = await self.get_order_book_price(fp_provider, 'bids')
            self.portfolio = round(self.balance + self.bid_price * self.counter, abs(self.scale))
            print("Bid Price (before):", self.bid_price)
            print("Ask Price (before):", self.ask_price)
            print("Counter (before):", self.counter)
            if _class == 0:
                self.position = False
                await self.add_sell_data(df['datetime'].iloc[-1], self.bid_price, self.counter)
                self.balance = round(self.balance + (self.bid_price * self.counter), abs(self.scale)) if self.bid_price and self.counter else None
            elif self.bid_price <= self.stop_loss:
                self.position = False
                await self.add_sell_data(df['datetime'].iloc[-1], self.bid_price, self.counter)
                self.balance = round(self.balance + (self.bid_price * self.counter), abs(self.scale)) if self.bid_price and self.counter else None
            print("Bid Price (after):", self.bid_price)
            print("Ask Price (after):", self.ask_price)
            print("Counter (after):", self.counter)
            print("Balance (after):", self.balance)

    async def get_order_book_price(self, fp_provider, order_type) -> float:
        price = None

        def on_order_book(order_book):
            nonlocal price
            price = getattr(order_book, order_type)[0].price

        fp_provider.on_order_book = on_order_book
        fp_provider.subscribe_order_book(self.ticker, self.security_board, 'orderbook1')

        # Ждем 1 секунду или до тех пор, пока не получим значение цены
        while price is None:
            await asyncio.sleep(0.1)

        fp_provider.unsubscribe_order_book('orderbook1', self.ticker, self.security_board)

        return round(float(price), abs(self.scale))

    async def ensure_market_open(self):
        is_trading_hours = False
        while not is_trading_hours:
            logger.debug("Ждем открытия рынка. ticker=%s", self.ticker)
            now = datetime.now()
            now_start = datetime.fromisoformat(now.strftime("%Y-%m-%d") + " " + self.trading_hours_start)
            now_end = datetime.fromisoformat(now.strftime("%Y-%m-%d") + " " + self.trading_hours_end)
            if now_start <= now <= now_end:
                is_trading_hours = True
            else:
                await asyncio.sleep(60)
        return is_trading_hours

    async def stop_strategy(self):
        self.stop_event.set()  # Set the event to signal stopping
        await task[self.user_id]  # Wait for the task to finish

    async def start_strategy(self):
        fp_provider = FinamPy(Config.AccessToken)
        decimals = 0
        securities = fp_provider.symbols  # Получаем справочник всех тикеров из провайдера
        # print('Ответ от сервера:', securities)
        if securities:  # Если получили тикеры
            si = next(
                item for item in securities.securities if item.board == self.security_board and item.code == self.ticker)
            self.scale = -(si.decimals + decimals)  # Кол-во десятичных знаков
        await self.bars_data(fp_provider)
        while not self.stop_event.is_set():
            if await self.ensure_market_open():
                try:
                    user_message[self.user_id] = f'Цена покупки: {self.ask_price if not np.isnan(self.ask_price) else None}\n' \
                                        f'Количество купленных акций: {self.counter}\n' \
                                        f'Цена продажи: {self.bid_price if not np.isnan(self.bid_price) else None}\n' \
                                        f'Стоимость портфеля(Стоимость акций + баланс): {self.portfolio}\n' \
                                        f'Баланс: {self.balance if hasattr(self, "balance") else None}'

                    graph_user_data[self.user_id] = {
                        'user_id': self.user_id,
                        'scale': self.scale,
                        'security_board': self.security_board,
                        'ticker': self.ticker,
                        'timeframe': self.timeframe,
                        'trade_data': self.trade_data_container
                    }
                    await self.live_check_position(model, fp_provider)

                    logger.debug("- live режим: запуск кода стратегии для покупки/продажи - тикер: %s", self.ticker)

                except Exception as are:
                    logger.error("Client error %s", are)

                await asyncio.sleep(self.check_interval)
            else:
                await asyncio.sleep(60)
        print('Стратегия завершила работу')


async def run_strategy(strategy):
    await strategy.start_strategy()


async def handle_command_stop_strategy(user_id):
    if user_id in active_strategies:
        strategy = active_strategies[user_id]
        await strategy.stop_strategy()
        del active_strategies[user_id]
        del task[user_id]


async def handle_command_activate_strategy(user_id):
    # Чтение данных для конкретного пользователя из файла
    user_data_file_name = os.path.join('data', 'users.txt')
    file_exists = os.path.isfile(user_data_file_name)
    if file_exists:
        user_data_file = pd.read_csv(user_data_file_name, sep='\t', index_col='user_id')
        if user_id in user_data_file.index:
            user_cfg = user_data_file.loc[user_id]
        else:
            raise ValueError(f"Пользователь с ID {user_id} не найден в файле данных о пользователях.")
    else:
        raise FileNotFoundError(f"Файл данных о пользователях '{user_data_file_name}' не найден.")

    if user_id not in active_strategies:
        active_strategies[user_id] = LiveStrategy(
            user_id=user_cfg.name,
            api_key=user_cfg['api_key'],
            ticker=user_cfg['ticker'],
            timeframe=Config.timeframe_0,
            days_back=1,
            check_interval=10,
            trading_hours_start=Config.trading_hours_start,
            trading_hours_end=Config.trading_hours_end,
            security_board=user_cfg['security_board'],
            client_id=user_cfg['client_id'],
            balance=user_cfg['trading_amount']
        )
    strategy = active_strategies[user_id]
    task = asyncio.create_task(run_strategy(strategy))
    await task


async def main():
    # Пример обработки команды от пользователя в телеграм-боте
    user_id_to_activate = "Jonn8J"
    await handle_command_activate_strategy(user_id_to_activate)

if __name__ == "__main__":
    asyncio.run(main())
