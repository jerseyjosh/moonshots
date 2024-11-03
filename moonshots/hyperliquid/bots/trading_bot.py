import logging
from collections import deque
import time
import importlib

import orjson
import asyncio
import uvloop
import numpy as np
import cvxpy as cp

from moonshots.hyperliquid.async_client import HyperliquidAsync
from moonshots.hyperliquid.websocket_manager import WebsocketManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.ERROR)

def log_time(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        print(f"{func.__name__} took {time.time() - start} seconds")
        return result
    return wrapper

class Bot:

    def __init__(self):
        self.client = HyperliquidAsync()
        self.ws = WebsocketManager()
        self.cache = deque(maxlen=1000)
        self.ema_price = {}
        self.ema_vol = {}
        self.notional_positions = {}
        self.pct_positions = {}

    async def load_config(self):
        """
        Periodically load config from client
        """
        while True:
            logger.debug("Loading config...")
            try:
                with open("./config.json", "r") as f:
                    self.config = orjson.loads(f.read())                    
            except Exception as e:
                logger.error(f"Could not load config: {e}")
            await asyncio.sleep(5) # wait 5 seconds to load config again

    def handle_mids(self, msg):
        """
        Handle midprice updates
        """
        mids: dict = {k: float(v) for k,v in msg['data']['mids'].items()}
        last_mids: dict = self.cache[-1][1] if self.cache else mids
        self.cache.append((time.time(), mids))
        for coin, mid_price in mids.items():
            # update ema price
            if coin not in self.ema_price:
                self.ema_price[coin] = mid_price
            else:
                self.ema_price[coin] = self.ema_price[coin] * self.config['ema_alpha'] + mid_price * (1 - self.config['ema_alpha'])
            # update ema vol
            abs_price_change = abs(mid_price - float(last_mids[coin])) / last_mids[coin]
            if coin not in self.ema_vol:
                self.ema_vol[coin] = abs_price_change
            else:
                self.ema_vol[coin] = self.ema_vol[coin] * self.config['ema_alpha'] + abs_price_change * (1 - self.config['ema_alpha'])
    
    def handle_webdata(self, msg):
        """
        Handle account position updates
        """
        positions: list[dict] = msg['data']['clearinghouseState']['assetPositions']
        self.account_value = float(msg['data']['clearinghouseState']['marginSummary']['accountValue'])
        for item in positions:
            p = item['position']
            coin = p['coin']
            value = float(p['positionValue'])
            size = float(p['szi'])
            self.notional_positions[coin] = value * np.sign(size)
            self.pct_positions[coin] = value / self.account_value

    async def run(self):

        # init config loader
        asyncio.create_task(self.load_config())

        # init client/websocket
        await self.ws.connect()

        # subscribe to mids
        await self.ws.subscribe({"type": "allMids"}, callback=self.handle_mids)

        # subscribe to positions
        await self.ws.subscribe({"type": "webData2", "user": self.client.address}, callback=self.handle_webdata)

        # main loop
        while True:

            # trading logic


            # wait 1 second
            await asyncio.sleep(1)

        # keep running
        await asyncio.Future()


async def main():
    bot = Bot()
    await bot.run()


if __name__=="__main__":
    uvloop.run(main())