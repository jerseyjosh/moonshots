import os
import json

import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange

def setup(base_url=None, skip_ws=False):
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    account: LocalAccount = eth_account.Account.from_key(config["secret_key"])
    address = config["account_address"]
    if address == "":
        address = account.address
    info = Info(base_url, skip_ws)
    exchange = Exchange(account, base_url, account_address=address)
    return address, info, exchange


if __name__ == "__main__":
    address, info, exchange = setup(skip_ws=True)