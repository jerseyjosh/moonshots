import os
import json

import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

def setup(base_url=None, skip_ws=False):
    account: LocalAccount = eth_account.Account.from_key(os.getenv("HL_KEY"))
    address = os.getenv("HL_ADDRESS")
    if address == "":
        address = account.address
    info = Info(base_url, skip_ws)
    exchange = Exchange(account, base_url, account_address=address)
    return address, info, exchange


if __name__ == "__main__":
    address, info, exchange = setup(skip_ws=True)