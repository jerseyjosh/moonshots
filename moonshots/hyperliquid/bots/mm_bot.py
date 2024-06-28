# import time
# import logging
# from collections import deque
# import argparse

# from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL

# import pandas as pd

# from moonshots.setup import setup

# CONFIG = {
#     "symbol": 'PURR/USDC',
#     "ob_levels": 5,
#     "spread": 0.01,
#     "zero_q": True,
#     "q_factor": 0.01,
#     "order_size_pct": 0.02,
#     "store_last_n": 10,
#     "update_interval": 1
# }


# class Agent:

#     def __init__(self, base_url, config):
#         self.base_url = base_url
#         self.symbol = config['symbol']
#         self.ob_levels = config['ob_levels']
#         self.spread = config['spread']
#         self.zero_q = config['zero_q']
#         self.q_factor = config['q_factor']
#         self.order_size_pct = config['order_size_pct']
#         self.store_last_n = config['store_last_n']
#         self.update_interval = config['update_interval']
#         self.address, self.info, self.exchange = setup(base_url=self.base_url, skip_ws=False)
#         self.ob_data_deque = deque(maxlen=self.store_last_n)
#         self.ob_data_df = None
#         self.total_value = 0
#         self.pnl = 0
#         self.active_orders = []
#         self.init_inventory()
#         self.subscribe_to_streams()

#     def subscribe_to_streams(self):

#         # store subscription ids
#         self.id_to_sub = {}

#         # subscribe to datastream
#         l2_sub = {'type': 'l2Book', 'coin': self.symbol}
#         sub_id = self.info.subscribe(l2_sub, callback=self.on_book_update)
#         self.id_to_sub[sub_id] = l2_sub

#         # subscribe to user data
#         user_events_sub = {'type': 'userFills', 'user': self.address}
#         user_sub_id = self.info.subscribe(user_events_sub, callback=self.on_user_update)
#         self.id_to_sub[user_sub_id] = user_events_sub

#     def init_inventory(self):
#         user_state = self.info.spot_user_state(self.address)
#         for balance in user_state['balances']:
#             if balance['coin']=='USDC':
#                 self.usdc_balance = float(balance['total'])
#             if balance['coin']==self.symbol.split('/')[0]:
#                 self.symbol_balance = float(balance['total'])
#         symbol_value = float(self.info.all_mids()[self.symbol]) * self.symbol_balance
#         self.total_value = self.usdc_balance + symbol_value
#         self.q = 0 if self.zero_q else (symbol_value - self.usdc_balance) / self.total_value
#         logging.info(f"Initialised inventory: {self.symbol_balance} {self.symbol}, {self.usdc_balance} USDC, q={self.q}")

#     def on_user_update(self, msg):
#         logging.debug(f"Received user event update: {msg}")

#         # update balances
#         fill_updates = msg['data']['fills']
#         for fill in fill_updates:
#             if fill['coin'] == 'USDC':
#                 self.usdc_balance += fill['sz']
#             elif fill['coin'] == self.symbol:
#                 self.symbol_balance += fill['sz']
#         self.symbol_value = self.get_last_mid() * self.symbol_balance
#         # add difference to pnl
#         self.pnl += self.usdc_balance + self.symbol_value - self.total_value
#         # update new total
#         self.total_value = self.usdc_balance + self.symbol_value
#         self.q = 0 if self.zero_q else (self.symbol_value - self.usdc_balance) / self.total_value
#         logging.info(f"Updated inventory: {self.symbol_balance} {self.symbol}, {self.usdc_balance} USDC, q={self.q}")

#     def on_book_update(self, msg):
#         if msg["data"]["coin"] != self.symbol:
#             logging.info(f"Received data for {msg['data']['coin']} but expecting {self.symbol}, ignoring.")
#             return
#         # handle data
#         try:
#             # get timestamp
#             time = msg['data']['time']
#             bids = msg['data']['levels'][0][:self.ob_levels]
#             asks = msg['data']['levels'][1][:self.ob_levels]
#             weighted_bid = 0
#             weighted_ask = 0
#             total_sz = 0
#             for b,a in zip(bids, asks):
#                 weighted_bid += float(b['px']) * float(a['sz'])
#                 weighted_ask += float(a['px']) * float(b['sz'])
#                 total_sz += float(b['sz']) + float(a['sz'])
#             weighted_mid = (weighted_bid + weighted_ask) / total_sz

#             # store data in deque
#             self.ob_data_deque.append(
#                 {
#                     'timestamp': time, 
#                     'best_bid_px': float(bids[0]['px']), 
#                     'best_bid_sz': float(bids[0]['sz']), 
#                     'best_ask_px': float(asks[0]['px']),
#                     'best_ask_sz': float(asks[0]['sz']), 
#                     'weighted_mid': weighted_mid
#                     }
#             )

#             # update dataframe
#             self.ob_data_df = pd.DataFrame(self.ob_data_deque)

#         except Exception as e:
#             logging.error(f"Error processing book update: {e}")


#     def get_data_df(self):
#         return self.ob_data_df
    
#     def get_last_mid(self):
#         return self.get_data_df()['weighted_mid'].iloc[-1]
    
#     def get_quotes(self):
#         """
#         returns:
#             bid_px, ask_px, bid_sz, ask_sz
#         """

#         # get mid price
#         mid = self.get_last_mid()

#         # adjust mid by inventory
#         adj_mid = mid * (1 - self.q_factor * self.q)

#         # make quotes
#         bid = adj_mid * (1 - 0.5 * self.spread)
#         ask = adj_mid * (1 + 0.5 * self.spread)

#         return float(f'{bid:.5g}'), float(f'{ask:.5g}'), 

#     def get_order_sizes(self):
#         # place quotes for self.order_size_pct of inventory value

#         # minimum $10 order size
#         target_value = max(10, self.total_value * self.order_size_pct)
#         bid_sz = target_value / self.get_last_mid()
#         ask_sz = target_value / self.get_last_mid()

#         return round(bid_sz), round(ask_sz)
        
#     def run(self):

#         try:
#             # wait for data to populate
#             while True:
#                 if len(self.ob_data_deque) > 0:
#                     break
#                 logging.info("Waiting for data...")
#                 time.sleep(1)

#             # start trading loop
#             while True:

#                 # live pnl
#                 logging.info(f"Current PnL: {self.pnl:.2f} USDC")
#                 # started 2450
                
#                 # get quotes
#                 bid_px, ask_px = self.get_quotes()
#                 mid_px = self.get_last_mid()

#                 # get order sizes
#                 bid_sz, ask_sz = self.get_order_sizes()

#                 logging.info((
#                     f"Quotes and Sizes - Bid: {bid_sz:.2f} @ {bid_px:.5f}, "
#                     f"Mid: {mid_px:.5f}, "
#                     f"Ask: {ask_sz:.2f} @ {ask_px:.5f}. "
#                     f"Spread: {(ask_px-bid_px)/mid_px:.2%}"
#                 ))

#                 # cancel existing unfilled orders
#                 for _ in range(len(self.active_orders)):
#                     oid = self.active_orders.pop()
#                     response = self.exchange.cancel(self.symbol, oid)
#                     logging.info(f"Cancelled order {oid}, response: {response}")

#                 # make new orders
#                 orders = [
#                     {"coin": self.symbol, "is_buy": True, "sz": bid_sz, "limit_px": bid_px, "order_type": {"limit": {"tif": "Alo"}}, "reduce_only": False},
#                     {"coin": self.symbol, "is_buy": False, "sz": ask_sz, "limit_px": ask_px, "order_type": {"limit": {"tif": "Alo"}}, "reduce_only": False}
#                 ]
#                 response = self.exchange.bulk_orders(orders)
#                 for status in response['response']['data']['statuses']:
#                     if 'resting' in status:
#                         self.active_orders.append(status['resting']['oid'])
#                         logging.info(f"Placed order {status['resting']['oid']}")

#                 logging.info(f"Waiting for {self.update_interval}s")
#                 time.sleep(self.update_interval)

#         except Exception as e:
#             if "KeyboardInterrupt" in str(e):
#                 logging.info("Exiting agent.")
#                 self.stop()
#                 return
#             else:
#                 import traceback
#                 logging.error(f"Error in agent: {e}, {traceback.format_exc()}")
#                 self.stop()
#                 return

#     def stop(self):

#         #TODO: close orders
#         pass

#         # cancel subscriptions
#         logging.debug("Unsubscribing from subscriptions.")
#         for sub_id, sub in self.id_to_sub.items():
#             self.info.unsubscribe(sub, sub_id)



# if __name__=="__main__":

#     # argparse
#     parser = argparse.ArgumentParser(description='HyperLiquid Agent')
#     parser.add_argument('--logging', default='INFO', help='Logging level')
#     args = parser.parse_args()

#     # logging setup
#     logging.basicConfig(
#         level=logging.getLevelName(args.logging.upper()),
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         datefmt='%Y-%m-%d %H:%M:%S'
#     )

#     # init hyperliquid setup
#     logging.info(f"Initialising Agent with config: {CONFIG}")
#     agent = Agent(base_url=MAINNET_API_URL, config=CONFIG)
#     agent.run()
