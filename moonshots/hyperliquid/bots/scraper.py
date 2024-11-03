import asyncio
import logging
import time
import os
from typing import Optional

import uvloop
import pandas as pd
from aiolimiter import AsyncLimiter
from tqdm.asyncio import tqdm_asyncio

from moonshots.hyperliquid.constants import MAINNET_WS_URL, MAINNET_API_URL
from moonshots.hyperliquid.async_client import HyperliquidAsync
from moonshots.hyperliquid.websocket_manager import WebsocketManager
from moonshots.hyperliquid.pandas_utils import parse_candles_to_pandas

DATA_DIR = '../../../data/'

class Scraper(HyperliquidAsync):
    """
    Scraping functionality for Hyperliquid, both historical and live.
    """
    def __init__(self):
        super().__init__()
        self.ws = None
        self.data = []
        self.logger = logging.getLogger(__name__)

    async def historical_candles(
            self, 
            coins: Optional[list[str]] = None, 
            spot: bool = False, 
            interval: str = "1h", 
            parse_pandas: bool = True,
            requests_per_minute: int = 60
            ):
        """
        Retrieve historical candles for a list of coins, or whole universe if coins not given.
        """
        if coins is None:
            meta = await self.meta(spot)
            coins = [item['name'] for item in meta['universe']]
        async with AsyncLimiter(requests_per_minute, 60):
            self.logger.debug(f"Retrieving historical candles for {len(coins)} coins with {self.MAX_REQUESTS_PER_MINUTE} requests per minute.")
            candle_snapshots = await tqdm_asyncio.gather(*[self.candle_snapshot(coin, interval) for coin in coins])
        flat_candle_snapshots = [item for sublist in candle_snapshots for item in sublist]
        return parse_candles_to_pandas(flat_candle_snapshots) if parse_pandas else flat_candle_snapshots

    async def connect_ws(self):
        """
        Connect to Hyperliquid websocket
        """
        self.ws = await WebsocketManager().connect()
    
    async def subscribe_to_mids(self):
        """
        Subscribe to mids updates
        """
        await self.ws.subscribe({"type": "allMids"}, self.on_mids_update)

    def on_mids_update(self, msg):
        """
        Callback for mids updates
        """
        mids: dict = msg['data']['mids']
        mids.update({"time": int(time.time()*1000)})
        self.data.append(mids)

    async def periodic_save(self, save_path: str):
        """
        Periodically save mids to CSV
        """
        while True:
            await asyncio.sleep(10)
            try:
                if self.data:
                    df = pd.DataFrame(self.data)
                    file_exists = os.path.isfile(save_path)
                    df.to_csv(save_path, mode='a', index=False, header = not file_exists)
                    self.logger.info("Saved mids to mids.csv")
                    self.data = []
            except Exception as e:
                self.logger.error(f"Error saving data: {e}")

    async def live_scrape_mids(self, save_path: str):
        """
        Live scrape mids and save to CSV periodically
        """
        await self.connect_ws()
        await self.subscribe_to_mids()
        await asyncio.create_task(self.periodic_save(save_path))

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = Scraper()
    save_path = os.path.join(DATA_DIR, "mids.csv")
    uvloop.run(scraper.live_scrape_mids(save_path))