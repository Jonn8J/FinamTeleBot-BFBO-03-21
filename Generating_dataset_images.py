import functions_nn
import os
from my_config.Cfg import Config  # Файл конфигурации торгового робота


if __name__ == "__main__":
    # Применение настроек из cfg
    portfolio = Config.training_NN  # тикеры по которым обучаем нейросеть
    timeframe_0 = Config.timeframe_0  # таймфрейм для обучения нейросети - вход
    timeframe_1 = Config.timeframe_1  # таймфрейм для обучения нейросети - выход
    security_board = Config.security_board
    # Параметры для отрисовки картинок
    period_sma_slow = Config.period_sma_slow  # период медленной SMA
    period_sma_fast = Config.period_sma_fast  # период быстрой SMA
    draw_window = Config.draw_window  # окно данных
    steps_skip = Config.steps_skip  # шаг сдвига окна данных
    draw_size = Config.draw_size  # размер стороны квадратной картинки

    for ticker in portfolio:

        # Считываем данные для обучения нейросети - выход - timeframe_1
        df_out = functions_nn.get_df_t1(security_board, ticker, timeframe_1)
        # print(df_out)
        _date_out = df_out["datetime"].tolist()
        _date_out_index = {_date_out[i]: i for i in range(len(_date_out))}  # {дата : индекс}
        _close_out = df_out["close"].tolist()

        # Считываем данные для обучения нейросети - вход - timeframe_0
        df_in = functions_nn.get_df_tf0(security_board, ticker, timeframe_0, period_sma_fast, period_sma_slow)
        # print(df_in)
        _date_in = df_in["datetime"].tolist()
        _close_in = df_in["close"].tolist()
        sma_fast = df_in["sma_fast"].tolist()
        sma_slow = df_in["sma_slow"].tolist()

        _steps, j = 0, 0
        # Рисуем картинки только для младшего ТФ
        for _date in _date_in:
            if _date in _date_out:  # Если дата младшего ТФ есть в датах старшего ТФ
                _steps += 1
                j += 1
                if _steps >= steps_skip and j >= draw_window:
                    _steps = 0

                    # Формируем картинку для нейросети с привязкой к дате и тикеру с шагом steps_skip
                    # размером [draw_size, draw_size]
                    _sma_fast_list = sma_fast[j-draw_window:j]
                    _sma_slow_list = sma_slow[j-draw_window:j]
                    _closes_list = _close_in[j-draw_window:j]

                    # Генерация картинки для обучения/теста нейросети
                    img = functions_nn.generate_img(_sma_fast_list, _sma_slow_list, _closes_list, draw_window)
                    # img.show()  # Показать сгенерированную картинку

                    _date_str = _date.strftime('%d_%m_%Y_%H_%M')
                    _filename = f"{ticker}-{timeframe_0}-{_date_str}.png"
                    _path = os.path.join("NN_data", f"training_dataset_{timeframe_0}")

                    # Проводим классификацию изображений
                    # if data.close[0] > data.close[-1]:
                    if _close_out[_date_out_index[_date]] > _close_out[_date_out_index[_date]-1]:
                        _path = os.path.join(_path, "1")
                    else:
                        _path = os.path.join(_path, "0")

                    img.save(os.path.join(_path, _filename))
                print(ticker, _date)
