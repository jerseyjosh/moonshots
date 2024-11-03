import aiohttp
import logging
import os
import contextlib
from typing import Optional

from aiolimiter import AsyncLimiter

from moonshots.hyperliquid.constants import MAINNET_API_URL

class API:

    MAX_REQUESTS_PER_MINUTE = 60

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or MAINNET_API_URL
        self.session = aiohttp.ClientSession(headers={'Content-Type': 'application/json'})
        self.logger = logging.getLogger(__name__)
        self.limiter = AsyncLimiter(self.MAX_REQUESTS_PER_MINUTE, 60)

    async def post(self, url_path, payload):
        async with self.limiter:
            async with self.session.post(self.api_url + url_path, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        
    async def close(self):
        """Close the session"""
        await self.session.close()