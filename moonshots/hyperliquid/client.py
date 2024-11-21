import logging
from typing import Optional
from dotenv import load_dotenv, find_dotenv
import os
import time
from decimal import Decimal
load_dotenv(find_dotenv())

import eth_account

from moonshots.hyperliquid.constants import MAINNET_API_URL
from moonshots.hyperliquid.api import API
from moonshots.hyperliquid.signing import sign_l1_action, float_to_wire, parse_secret_key
from moonshots.utils.time import ms_timestamp

logger = logging.getLogger(__name__)

class HyperliquidAsync(API):
    """
    Asynchronous hyperliquid client
    """
    def __init__(self, address = None, api_url = None, ws_url = None):
        super().__init__(api_url or MAINNET_API_URL)  
        self.address = address or os.getenv("USER_ADDRESS")
        self.api_url = api_url or MAINNET_API_URL
        self.wallet = eth_account.Account.from_key(parse_secret_key(os.getenv('WALLET_SECRET')))
        self.vault_address = None # TODO: need to update if using vault
        
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
    
    async def candle_snapshot(self, coin: str, interval: str, start: int = None, end: Optional[int] = None):
        """Retrieve candle snapshot for a given coin"""
        if end is None:
            end = int(time.time()*1000)
        if start is None:
            start = 1 # ensure max history
        return await self.post("/info", {"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": start, "endTime": end}})

    async def l2_snapshot(self, coin: str):
        """Retrieve L2 snapshot for a given coin"""
        return await self.post("/info", {"type": "l2Book", "coin": coin})
    
    async def place_order(self, coin: int, is_buy: bool, price: float, size: float, reduce_only: bool = False, time_in_force: str = 'Alo', cloid: Optional[int] = None):
        """Place a new order"""
        assert isinstance(coin, int), "Coin must be asset ID, not name!"
        order = {
            'a': coin, 
            'b': is_buy, 
            'p': float_to_wire(price),
            's': float_to_wire(size), 
            'r': reduce_only, 
            't': {'limit': {'tif': time_in_force}},
        }
        if cloid is not None:
            order['c'] = cloid
        return await self.bulk_orders([order])
    
    async def bulk_orders(self, orders: list[dict]):
        """Place order(s)"""
        # create order action
        order_action = {
            "type": "order",
            "orders": orders,
            "grouping": "na"
        }
        # get ms timestamp
        timestamp = ms_timestamp()
        # get action signature
        signature = sign_l1_action(
            self.wallet,
            order_action,
            self.vault_address,
            timestamp,
            self.api_url == MAINNET_API_URL,
        )
        return await self.post_action(order_action, signature, timestamp, self.vault_address)
    
    async def post_action(self, action, signature, nonce, vault_address=None):
        """Post an action to the exchange"""
        payload = {
            'action': action,
            'signature': signature,
            'nonce': nonce,
        }
        if vault_address is not None:
            payload['vaultAddress'] = vault_address
        logger.debug(f"Posting action: {payload}")
        return await self.post('/exchange', payload)
    
    async def modify_order(self, oid: int, coin: int, is_buy: bool, price: float, size: float, reduce_only: bool = False, time_in_force: str = 'Alo', cloid: Optional[int] = None):
        """Modify an existing order"""
        order = {
            'a': coin, 
            'b': is_buy, 
            'p': float_to_wire(price),
            's': float_to_wire(price), 
            'r': reduce_only,
            't': {'limit': {'tif': time_in_force}},
            }
        if cloid is not None:
            order['c'] = cloid
        return await self.post('/exchange', {'type': 'modify', 'oid': oid, 'order': order})