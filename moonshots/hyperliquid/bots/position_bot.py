# Unfinished bot to build a position in a coin using limit orders

import asyncio
from collections import deque
import logging

import numpy as np

from moonshots.hyperliquid import HyperliquidAsync
from moonshots.hyperliquid.websocket_manager import WebsocketManager

logger = logging.getLogger(__name__)

MAX_DECIMALS = 6 # for perps

class PositionAlgo():
    def __init__(self, 
                 coin: str, 
                 freq: str,
                 cache_length: int = 1000,
                 ema_alpha: float = 0.02,
                 bollinger_b: float = 5.0,
                 order_size_usd: float = 20.0
                 ):
        self.client = HyperliquidAsync()
        self.ws = WebsocketManager()
        self.coin = coin
        self.freq = freq
        self.close_cache = deque(maxlen=cache_length)
        self.rolling_mean = None
        self.rolling_std = None
        self.ema_alpha = ema_alpha
        self.bollinger_b = bollinger_b
        self.order_size_usd = order_size_usd
        self.usd_balance = None
        self.buy_price = None

    def on_candle_update(self, msg):
        # extract data
        self.close_price = float(msg['data']['c'])
        # update rolling mean and std
        self.rolling_mean = self.ema_alpha * self.close_price + (1 - self.ema_alpha) * self.rolling_mean if self.rolling_mean else self.close_price
        self.rolling_std = self.ema_alpha * np.sqrt((self.close_price - self.rolling_mean)**2) + (1 - self.ema_alpha) * self.rolling_std if self.rolling_std is not None else 0
        # get optimal positions
        self.target_position_usd = 500.0
        # get buy price
        logger.info(f'Price: {self.close_price}, Rolling mean: {self.rolling_mean}, Rolling std: {self.rolling_std}, Buy price: {self.buy_price}')

    def get_target_position(self):
        """Get optimal position size"""
        inverse_z_score = - (self.close_price - self.rolling_mean) / self.rolling_std
        self.target_position = np.clip(inverse_z_score, a_min=0.0, a_max=1.0)
   
    def get_buy_price(self):
        """Get buy prices, rounded according to requirements"""
        price = self.rolling_mean - self.bollinger_b * self.rolling_std
        max_decimals = MAX_DECIMALS - self.coin_info['szDecimals']
        round_price: np.float64 = np.round(price * 10**max_decimals) / 10**max_decimals
        return round_price.item()
    
    def on_webdata_update(self, msg):
        """Update local cash holdings, see if there is enough to execute more trades"""
        self.usd_balance = float(msg['data']['clearinghouseState']['marginSummary']['totalRawUsd'])
        logger.info(f'Updated usd balance: {self.usd_balance}')

    def get_order_size(self):
        """Get order size in coin units"""
        size = self.order_size_usd / self.buy_price
        round_size: np.float64 = np.round(size * 10**self.coin_info['szDecimals']) / 10**self.coin_info['szDecimals']
        return round_size.item()
    
    async def run(self):

        # connect websocket
        await self.ws.connect()

        # get coin meta info
        self.universe = (await self.client.meta())['universe']
        for i in range(len(self.universe)):
            self.universe[i]['id'] = i
        self.coin_info = [item for item in self.universe if item['name']==self.coin][0]

        # subscribe to candle updates
        await self.ws.subscribe({'type': 'candle', 'coin': self.coin, 'interval': self.freq}, self.on_candle_update)

        # subscribe to holdings
        await self.ws.subscribe({"type": "webData2", "user": self.client.address}, callback=self.on_webdata_update)
        
        # main loop
        while True:

            # Wait for usd_balance to populate
            if self.usd_balance is None:
                logger.info('Waiting for usd balance to populate...')
                await asyncio.sleep(1)
                continue

            # check still money to invest
            if self.usd_balance < self.order_size_usd:
                break

            # wait until buy price
            if self.buy_price is None:
                await asyncio.sleep(1)
                continue

            # get open orders
            open_orders = await self.client.open_orders()
            # [{'coin': 'BTC', 'side': 'B', 'limitPx': '50000.0', 'sz': '0.0004', 'oid': 46093479467, 'timestamp': 1731323774883, 'origSz': '0.0004'}]
            if len(open_orders) == 0:
                logger.info('No open orders')
            for order in open_orders:
                if order['coin'] == self.coin:
                    if float(order['limitPx']) != self.buy_price:
                        response = await self.client.modify_order(order['oid'], coin=self.coin_info['id'], is_buy=True, price=self.buy_price, size=self.get_order_size())
            else:
                # no existing orders, place a new one
                response = await self.client.place_order(coin=self.coin_info['id'], is_buy=True, price=self.buy_price, size=self.get_order_size())
                breakpoint()
            logging.info(f'Order response: {response}')
            await asyncio.sleep(1)
        
        await self.ws.close()
        logger.info('Bot finished')


if __name__=="__main__":

    logging.basicConfig(level=logging.INFO)

    async def main():
        bot = BuildPosition(coin='BTC', freq='1m')
        await bot.run()
    
    asyncio.run(main())
