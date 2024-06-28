import os
import json
from datetime import datetime
import logging

import pandas as pd
import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

def setup(skip_ws=False):
    if os.getenv("HL_NET")=='mainnet':
        base_url = MAINNET_API_URL
    elif os.getenv("HL_NET")=='testnet':
        base_url = TESTNET_API_URL
    else:
        raise ValueError(f"HL_NET: {os.getenv('HL_NET')} is invalid, must be mainnet or testnet.")
    account: LocalAccount = eth_account.Account.from_key(os.getenv("HL_KEY"))
    address = os.getenv("HL_ADDRESS")
    if address == "":
        address = account.address
    info = Info(base_url, skip_ws)
    exchange = Exchange(account, base_url, account_address=address)
    return address, info, exchange

def timestamp():
    return int(datetime.now().timestamp()*1000)

def log_time(func):
    def wrapper(*args, **kwargs):
        start = timestamp()
        result = func(*args, **kwargs)
        end = timestamp()
        logger.info(f"{func.__name__} took {end-start}ms")
        return result
    return wrapper
