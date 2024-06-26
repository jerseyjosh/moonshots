from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL

from moonshots.hyperliquid.utils import setup

class Agent:
    """
    Mean Reversion bot for hyperliquid:
        - Ranked L/S on hourly cross sectional z scores
    """
    def __init__(self, base_url, config):
        self.base_url = base_url
        self.q: float = config['q']
        self.address, self.info, self.exchange = setup(base_url=self.base_url, skip_ws=False)

    def subscribe(self):
        mids_sub = {'type': 'allMids'}
        sub_id = self.info.subscribe(mids_sub, callback=self.on_mids_update)

    def on_mids_update(self, msg):
        print(msg)

    def start(self):
        self.subscribe()


if __name__=="__main__":
    
    config = {
        'q': 0.01
    }
    agent = Agent(base_url=MAINNET_API_URL, config=config)




