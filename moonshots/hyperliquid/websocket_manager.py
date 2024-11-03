import asyncio
import uvloop
import websockets
import logging
import json

from moonshots.hyperliquid.constants import MAINNET_WS_URL

class WebsocketManager:
    """Async Websocket Manager for Hyperliquid"""
    def __init__(self, base_url: str = None):
        self.base_url = base_url or MAINNET_WS_URL
        self.ws = None
        self.ws_ready = False
        self.id_to_sub = {}
        self.id_to_callback = {}
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """Connect to websocket"""
        self.ws = await websockets.connect(self.base_url)
        self.logger.debug("Websocket connected")
        self.ws_ready = True
        #asyncio.create_task(self.send_ping())
        asyncio.create_task(self.listen())
        return self
    
    async def close(self):
        """Close websocket connection"""
        await self.ws.close()
        self.logger.debug("Websocket closed")

    async def send_ping(self):
        """Send ping to websocket every 50 seconds"""
        while True:
            self.logger.debug("Sending ping...")
            await self.ws.send(json.dumps({"method": "ping"}))
            await asyncio.sleep(50)

    async def subscribe(self, subscription: dict, callback = None):
        """Subscribe to a websocket channel"""
        id = self.subscription_to_identifier(subscription)
        self.id_to_sub[id] = subscription
        self.id_to_callback[id] = callback
        self.logger.debug(f"Subscribing to {subscription} with callback {callback}")
        await self.ws.send(json.dumps({"method" : "subscribe", "subscription" : subscription}))
        self.logger.debug(f"Subscribed to {subscription} with callback {callback}")
        return id

    async def post(self, id, request, callback):
        """Post request to websocket"""
        self.id_to_callback[id] = callback
        self.logger.debug(f"Posting request {request} with id {id}")
        await self.ws.send(json.dumps({"method": "post", "id": id, "request": request}))
        self.logger.debug(f"Posted request {request} with id {id}")

    async def listen(self):
        """Listen to websocket message"""
        self.logger.debug("Websocket listening...")
        while True:
            try:
                msg = await self.ws.recv()
                try:
                    msg = json.loads(msg)
                except json.JSONDecodeError:
                    self.logger.error(f"Could not decode msg to JSON: {msg}")
                    continue
                id = self.msg_to_identifier(msg)
                callback = self.id_to_callback.get(id)
                if callback:
                    callback(msg)
                else:
                    self.logger.debug(f"No callback for message: {id}")
            except websockets.ConnectionClosedOK:
                self.logger.debug("Websocket connection closed")
                break  
    
    @staticmethod
    def subscription_to_identifier(sub) -> str:
        """Helper to convert subscription to identifier for routing"""
        if sub["type"] == "allMids":
            return "allMids"
        elif sub["type"] == "l2Book":
            return f'l2Book:{sub["coin"].lower()}'
        elif sub["type"] == "trades":
            return f'trades:{sub["coin"].lower()}'
        elif sub["type"] == "userEvents":
            return "userEvents"
        elif sub["type"] == "webData2":
            return "webData2"
        
    @staticmethod
    def msg_to_identifier(ws_msg):
        """Helper to convert websocket message to identifier for routing"""
        if ws_msg["channel"] == "pong":
            return "pong"
        elif ws_msg["channel"] == "allMids":
            return "allMids"
        elif ws_msg["channel"] == "l2Book":
            return f'l2Book:{ws_msg["data"]["coin"].lower()}'
        elif ws_msg["channel"] == "trades":
            trades = ws_msg["data"]
            if len(trades) == 0:
                return None
            else:
                return f'trades:{trades[0]["coin"].lower()}'
        elif ws_msg["channel"] == "user":
            return "userEvents"
        elif ws_msg["channel"] == "post":
            return ws_msg["data"]["id"]
        elif ws_msg["channel"] == "subscriptionResponse":
            return "subscriptionResponse"
        elif ws_msg["channel"] == "webData2":
            return "webData2"
        else:
            raise ValueError(f"Unknown channel: {ws_msg['channel']}")

# if __name__ == "__main__":

#     logging.basicConfig(level=logging.DEBUG)

#     async def test_callback(msg):
#         print(f'CALLBACK: {str(msg)[:100]}')

#     async def main():
#         try:
#             ws = WebsocketManager()
#             await ws.connect()
#             await ws.subscribe({"type": "allMids"}, test_callback)
#             await asyncio.Future() # keep running
#         except Exception as e:
#             print(e)
    
#     uvloop.run(main())