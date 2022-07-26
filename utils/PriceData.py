import pandas as pd
from utils.Candle import Candle

COLUMNS = ["open", "high", "low", "close", "time", "ema200", "macd", "macd_signal"]


class PriceData:
    def __init__(self):
        self.history = pd.DataFrame(columns=COLUMNS)
        self.history.index.name = "time"

    def add_candle(self, candle: Candle):
        (macd, macd_signal) = self.macd()

        new_data = pd.DataFrame(
            {"open": [candle.open],
             "high": [candle.high],
             "low": [candle.low],
             "close": [candle.close],
             "time": [candle.time],
             "ema200": [self.ema()],
             "macd": [macd],
             "macd_signal": [macd_signal]},
            index=[candle.time])

        self.history = pd.concat([self.history, new_data])

    def current_time(self) -> float:
        return self.history.iloc[self.length()-1]['time']

    def current_price(self) -> float:
        return self.history.iloc[self.length()-1]['close']

    def ema(self, length=200, value='close') -> float:
        if self.length() > length:
            ema_series = self.history[value].ewm(span=length, min_periods=length, adjust=True).mean()
            return ema_series.iloc[len(ema_series.index) - 1]
        else:
            return None

    def macd(self, length1=12, length2=24, signal_length=6) -> tuple[float, float]:
        if self.length() > 24:
            macd = self.ema(length1) - self.ema(length2)
            macd_signal = self.ema(signal_length, 'macd')
            return macd, macd_signal
        else:
            return None, None

    def length(self):
        return len(self.history.index)

    def save(self, file_path):
        self.history.to_csv(file_path)