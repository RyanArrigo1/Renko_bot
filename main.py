from tda.auth import easy_client
from tda.streaming import StreamClient
from tda.orders.equities import *
from tda.orders.common import Duration, Session

from utils.PriceData import PriceData
from utils.Candle import Candle
from utils.utils import *

import asyncio
import time
import csv
from enum import Enum, auto

import traceback

API_KEY = "AXXDNZXANDZRBVAVAQUDUTG9SAC7WCM4"

SYMBOL = 'TQQQ'
SYMBOL_SHORT = 'TQQQ'

TICKS = 6
TICK_SIZE = 0.01

LIVE_TRADES = False


class Position(Enum):
    NONE = auto
    LONG = auto
    SHORT = auto


# Market for exiting
# Normal session

# Limit for exiting, if no fill switch to market

# Invoice


class Trader:
    def __init__(self):
        self.client = easy_client(API_KEY, "http://localhost:8000/callback", "test.token", make_webdriver)
        self.stream_client = StreamClient(self.client)
        self.account_id = get_account_id(self.client)

        self.current_position = Position.NONE
        self.pos_open = False
        self.cash = 0
        self.shares = 0
        self.current_candle = None
        self.price_history = PriceData()

    def close_pos(self, price):
        """
        Close an open position. If the current open position is a long position will sell shares and if currently open
        position is short position will buy back shares.
        :param price: current share price
        """
        self.cash = self.cash + self.shares * price
        self.shares = 0

        if self.current_position == Position.LONG:
            resp = self.client.place_order(self.account_id, equity_sell_limit(SYMBOL, 1, price)
                                           .set_duration(Duration.FILL_OR_KILL)
                                           .set_session(Session.NORMAL)
                                           .build())
            if not check_order_success(self.client, self.account_id, resp):
                self.client.place_order(self.account_id, equity_sell_market(SYMBOL, 1)
                                        .set_session(Session.NORMAL)
                                        .build())
        elif self.current_position == Position.SHORT:
            pass
            # resp = self.client.place_order(self.account_id, equity_sell_limit(SYMBOL_SHORT, 1, price)
            #                                .set_duration(Duration.FILL_OR_KILL)
            #                                .set_session(Session.NORMAL)
            #                                .build())
            # if not check_order_success(self.client, self.account_id, resp):
            #     self.client.place_order(self.account_id, equity_sell_market(SYMBOL_SHORT, 1)
            #                             .set_session(Session.NORMAL)
            #                             .build())

        self.current_position = Position.NONE
        self.pos_open = False

    def open_long(self, price):
        """
        Close any previous positions and enter a long position at the given price. Buys 100 shares.
        :param price: current share price
        """
        self.close_pos(price)

        resp = self.client.place_order(self.account_id, equity_buy_limit(SYMBOL, 1, price)
                                       .set_duration(Duration.FILL_OR_KILL)
                                       .set_session(Session.NORMAL)
                                       .build())

        if check_order_success(self.client, self.account_id, resp):
            self.shares = 1
            self.cash = self.cash - self.shares * price

            self.current_position = Position.LONG
            self.pos_open = True

    def open_short(self, price):
        """
        Close any previous positions and enter a short position at the given price. Sells 100 shares.
        :param price: current share price
        """
        # self.close_pos(price)
        #
        # resp = self.client.place_order(self.account_id, equity_buy_limit(SYMBOL_SHORT, 1, price)
        #                                .set_duration(Duration.FILL_OR_KILL)
        #                                .set_session(Session.NORMAL)
        #                                .build())
        #
        # if check_order_success(self.client, self.account_id, resp):
        #     self.shares = -1
        #     self.cash = self.cash - self.shares * price
        #
        #     self.current_position = Position.SHORT
        #     self.pos_open = True

    def strategy(self):
        """
        Run strategy.
        """
        # Need to wait until we have 200 candles for calculating EMA200
        if self.price_history.length() > 200:
            # Once we have enough, calculate EMA200 and MACD
            ema200 = self.price_history.ema(200)
            (macd, macd_signal) = self.price_history.macd()

            # Get the most recent closing price
            price = self.price_history.current_price()
            print(f"Price: {price}  EMA200: {ema200}  MACD: {macd}  MACD signal: {macd_signal}")

            # Keep track of what action we are taking
            action = ""

            # Long positions if price is above EMA200, short positions otherwise
            if price is not None and is_market_hours():
                if self.pos_open:
                    if price > ema200 and macd < macd_signal:
                        self.close_pos(price)
                        action = "Sell to close"
                    elif price < ema200 and macd > macd_signal:
                        self.close_pos(price)
                        action = "Buy to close"
                else:
                    if price > ema200 and macd > macd_signal:
                        self.open_long(price)
                        action = "Buy to open"
                    elif price < ema200 and macd < macd_signal:
                        self.open_short(price)
                        action = "Sell to open"

                # Check if a trade was made
                if not action == "":
                    # Print trade to console
                    print(
                        f"Trade: t={self.price_history.current_time()} action={action} shares={self.shares} cash={self.cash} price={price} ema200={ema200} macd={macd} macd signal={macd_signal}")

                    # Write trade to log file and save candle data
                    with open('results/trades.csv', 'a') as trades_file:
                        trades_writer = csv.writer(trades_file)
                        trades_writer.writerow(
                            [self.price_history.current_time(), action, self.shares, self.cash, price, ema200, macd,
                             macd_signal])
            else:
                print("Error: Price is None")

    def price_handler(self, msg):
        """
        Handle new price data.
        :param msg: streamer data
        """

        # Get message content
        msg_content = msg['content'][0]

        with open("results/msg.log", "a") as message_log:
            message_log.write(str(msg_content) + "\n")

        print(msg_content)
        # Check if message contains price data
        if 'LAST_PRICE' in msg_content:
            # Initialize first candle
            if self.current_candle is None:
                self.current_candle = Candle(msg_content['TRADE_TIME_IN_LONG'], TICKS * TICK_SIZE)

            # Get price from message and add it to the current candle
            price = msg_content['LAST_PRICE']
            self.current_candle.add_price(price)

            # Check if total candle price change is greater than the specified tick amount
            if self.current_candle.filled:
                next_candle = Candle(msg_content['TRADE_TIME_IN_LONG'], TICKS * TICK_SIZE)
                next_candle.add_price(self.current_candle.close)
                next_candle.add_price(price)

                # If it is, add finished candle to history
                self.price_history.add_candle(self.current_candle)
                self.price_history.save("results/candles.csv")

                print("Added candle: " + self.current_candle.__str__())

                # Marked current candle as finished
                self.current_candle = next_candle

                # Run strategy
                self.strategy()

    async def stream_data(self):
        done = False

        # Add stream handler
        self.stream_client.add_level_one_equity_handler(self.price_handler)

        while not done:
            try:
                # Login
                await self.stream_client.login()
                print("Logged in")

                # self.account_id = self.stream_client._account_id

                # Add subscriptions
                await self.stream_client.level_one_equity_subs([SYMBOL])
                print("Subscribed")

                print("Begin listening...")
                while not done:
                    await self.stream_client.handle_message()

            except KeyboardInterrupt:
                done = True
                print("Exiting")
            except Exception as e:
                traceback.print_exc()
                print(e)
                done = False
                time.sleep(0.5)
                print("Restarting")


def main():
    print("Starting bot...")
    # Initialize trade log
    with open('results/trades.csv', 'w') as trades_file:
        trades_writer = csv.writer(trades_file)
        trades_writer.writerow(['Time', 'Action', 'Shares', 'Cash', 'Price', 'EMA200', 'MACD', 'MACD Signal'])
    with open("results/msg.log", "w") as message_log:
        message_log.write("----- Start message log: -----\n")

    trader = Trader()

    try:
        asyncio.run(trader.stream_data())
    except Exception as e:
        print(e)
        print("Saving...")
        trader.price_history.save("results/candles.csv")


if __name__ == '__main__':
    main()