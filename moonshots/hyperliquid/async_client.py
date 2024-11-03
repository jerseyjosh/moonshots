import logging
from typing import Optional
from dotenv import load_dotenv, find_dotenv
import os
import time
load_dotenv(find_dotenv())

from aiolimiter import AsyncLimiter
import contextlib

from moonshots.hyperliquid.constants import MAINNET_API_URL, MAINNET_WS_URL
from moonshots.hyperliquid.api import API
from moonshots.hyperliquid.websocket_manager import WebsocketManager

class HyperliquidAsync(API):
    """
    Asynchronous hyperliquid client
    """
    def __init__(self, address = None, api_url = None, ws_url = None):
        super().__init__(api_url or MAINNET_API_URL)  
        self.address = address or os.getenv("WALLET_ADDRESS")
        self.logger = logging.getLogger(__name__)
        
    async def user_state(self, spot: bool = False):
        """Retrieve user state"""
        type_str = "spotClearinghouseState" if spot else "clearinghouseState"
        return await self.post('/info', {"type": type_str, "user": self.address})
    
    async def open_orders(self):
        """Retrieve open orders"""
        return await self.post('/info', {"type": "openOrders", "user": self.address})
    
    async def meta(self, spot: bool = False):
        """Retrieve exchange perp/spot metadata"""
        type_str = "spotMeta" if spot else "meta"
        return await self.post("/info", {"type": type_str})
    
    async def all_mids(self):
        """
        Retrieve all mids for actively traded coinds
        """
        return await self.post("/info", {"type": "allMids"})
    
    async def candle_snapshot(self, coin: str, interval: str, startTime: int = None, endTime: Optional[int] = None):
        """Retrieve candle snapshot for a given coin"""
        if endTime is None:
            endTime = int(time.time()*1000)
        if startTime is None:
            startTime = 1 # ensure max history
        return await self.post("/info", {"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": startTime, "endTime": endTime}})


    async def l2_snapshot(self, coin: str):
        """Retrieve L2 snapshot for a given coin"""
        return await self.post("/info", {"type": "l2Book", "coin": coin})
    

# if __name__=="__main__":
#     import asyncio
#     async def main():
#         hl = HyperliquidAsync()
#         meta = await hl.meta(spot=False)
#         perps = [item['name'] for item in meta['universe']]
#         candles = await hl.candle_snapshot(perps[0], "1h")

#     asyncio.run(main())