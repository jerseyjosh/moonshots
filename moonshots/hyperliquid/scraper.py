import csv
import os
from datetime import datetime

from moonshots.hyperliquid.base import Hyperliquid
from moonshots.hyperliquid.utils import setup

from hyperliquid.utils.constants import MAINNET_API_URL

class Scraper(Hyperliquid):
    def __init__(self, skip_ws=False):
        super().__init__(skip_ws)

    @staticmethod
    def timestamp():
        return datetime.now().timestamp()
        
    def start(self):
        self.info.subscribe({'type': 'allMids'}, callback=self.on_all_mids)

    def on_all_mids(self, msg):
        mids_dict = {'timestamp': self.timestamp()}
        mids_dict.update(msg['data']['mids'])
        with open('mids.csv', 'a') as f:
            writer = csv.DictWriter(f, fieldnames=list(mids_dict.keys()))
            if not self.fieldnames_added:
                writer.writeheader()
                self.fieldnames_added = True
            writer.writerow(mids_dict)

if __name__ == "__main__":
    scraper = Scraper(output_path = './mids.csv')
    scraper.start()