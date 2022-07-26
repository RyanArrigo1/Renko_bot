import atexit
import time

import arrow
import tda.utils

from tda.utils import Utils
from tda.client import Client


def is_market_hours():
    time = arrow.utcnow().to("US/Eastern")

    return time.weekday() < 5 and 9.5 < time.hour < 16


def get_account_id(c):
    resp = c.get_user_principals().json()
    print(str(resp))
    return resp['accounts'][0]['accountId']


def make_webdriver():
    # Import selenium here because it's slow to import
    from selenium import webdriver

    driver = webdriver.Firefox()
    atexit.register(lambda: driver.quit())
    return driver


def check_order_success(client: Client, account_id, order_resp):
    try:
        order_id = Utils(client, account_id).extract_order_id(order_resp)
    except tda.utils.UnsuccessfulOrderException:
        return False

    order = client.get_order(order_id, account_id)
    status = order["status"]
    while status not in ["ACCEPTED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"]:
        time.sleep(1)
        order = client.get_order(order_id, account_id)
        status = order["status"]

    return status in ["ACCEPTED", "FILLED"]


if __name__ == '__main__':
    print(is_market_hours())