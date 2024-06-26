from moonshots.hyperliquid.utils import setup

from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL  

class Hyperliquid:

    def __init__(self, base_url=MAINNET_API_URL, skip_ws=False):
        self.address, self.info, self.exchange = setup(base_url, skip_ws)

    

