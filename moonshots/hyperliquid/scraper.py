import csv
import os

from moonshots.setup import setup
from utils import timestamp

from hyperliquid.utils.constants import MAINNET_API_URL

class Scraper:
    def __init__(
            self, 
            base_url: str = MAINNET_API_URL,
            output_path: str = './mids.csv'
    ):
        self.base_url = base_url
        self.output_path = output_path
        self.fieldnames_added = False

    @staticmethod
    def timestamp():
        return timestamp()
        
    def start(self):
        self.address, self.info, self.exchange = setup(base_url=self.base_url, skip_ws=False)  
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