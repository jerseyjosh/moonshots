import logging
from collections import deque
import pickle
import json
import time
import traceback

import pandas as pd
import numpy as np
from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL
from sklearn.base import BaseEstimator
import cvxpy as cp

from moonshots.hyperliquid.utils import setup, log_time
from moonshots.hyperliquid.base import Hyperliquid

logger = logging.getLogger(__name__)

class Agent(Hyperliquid):
    """
    Mean Reversion bot for hyperliquid:
        - Ranked L/S on hourly cross sectional z scores
    """
    
    def __init__(self, min_gbp_size, gbp_size, max_single_position, trade_interval, tx=0.00035, memory=5000, slippage=None, trade_markets=None, model_path=None):
        super().__init__()
        self.slippage = slippage if slippage else self.exchange.DEFAULT_SLIPPAGE
        self.min_gbp_size = min_gbp_size # min trading amount
        self.gbp_size = gbp_size # total trading amount
        self.max_single_position = max_single_position # max position size
        self.trade_interval = trade_interval # trade interval in seconds
        self.memory = memory
        self.mids_cache = deque(maxlen=memory)
        self.signal_cache = deque(maxlen=memory)
        self.forecast_cache = deque(maxlen=memory)
        self.trade_markets = trade_markets
        self.holdings = {}
        self.sub_to_id = {}
        self.tx = tx
        self.asset_info = {asset['name']: {'szDecimals': asset['szDecimals'], 'id': i} for i,asset in enumerate(self.info.meta()['universe'])}
        if model_path is not None:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
                assert isinstance(self.model, BaseEstimator), "Model must be a scikit-learn regressor"
        else:
            self.model = None

    @staticmethod
    def pd_timestamp():
        return pd.Timestamp.now()
    
    @log_time
    def init_cache(self):
        logging.info("Initializing cache.")
        all_candles = self.all_candles_snapshot('1m', n=500, parse_pandas=True) # get last 500 minutes of data
        if self.trade_markets is not None:
            all_candles = all_candles[all_candles.index.get_level_values('market').isin(self.trade_markets)]
        close_prices = all_candles.unstack()['close'].resample('1s').ffill().reset_index().to_dict(orient='records') # resample to 1s candles
        self.mids_cache = deque(close_prices, maxlen=self.memory)
        logging.info(f"Cache intialized with {len(self.mids_cache)} records.")

    def subscribe(self):
        mids_sub = {'type': 'allMids'}
        mids_id = self.info.subscribe(mids_sub, callback=self.on_mids_update)
        self.sub_to_id[json.dumps(mids_sub)] = mids_id

    def on_mids_update(self, msg):
        last_rec = self.mids_cache[-1]
        mids: dict = {k:float(v) for k,v in msg['data']['mids'].items() if k in last_rec.keys()}
        mids.update({'time': self.pd_timestamp()})
        self.mids_cache.append(mids)
        self.calculate_signal()
        self.forecast_return()

    def calculate_signal(self):
        # self.mids_cache = [{'time': int[ms], 'btc': int, 'eth', int, ...}, {...}]
        df = pd.DataFrame(self.mids_cache).set_index('time').resample('1s').last().ffill()
        return_1h = df.pct_change(freq='1h', fill_method=None).iloc[-1]
        cs_z = (return_1h - return_1h.mean()) / return_1h.std()
        signal_dict = dict(cs_z)
        signal_dict.update({'time': self.pd_timestamp()})
        self.signal_cache.append(signal_dict)
    
    def forecast_return(self):
        assert self.model, "Model must be loaded before forecasting"
        signal = pd.Series(self.signal_cache[-1]).drop('time').astype(float).dropna()
        forecast = dict(zip(signal.index, self.model.predict(signal.values.reshape(-1,1))))
        forecast.update({'time': self.pd_timestamp()})
        self.forecast_cache.append(forecast)

    def get_holdings(self):
        records = self.info.user_state(self.address)['assetPositions']
        holdings = {}
        total_value = 0
        for r in records:
            position = r['position']
            size = float(position['szi'])
            value = float(position['positionValue'])
            total_value += abs(value)
            px = value / size
            holdings[position['coin']] = {'current_price': px, 'size': size, 'ratio': np.sign(size)*value/self.gbp_size} 
        logging.info(f'total invested value: {total_value}')
        return holdings

    def get_orders(self):

        # get E(r) forecast and current holdings
        forecast = pd.Series(self.forecast_cache[-1]).drop('time').astype(float)
        holdings = self.get_holdings() # {'btc': {'current_price': 10000, 'size': 0.1}, ...}
        current_portfolio = pd.Series({k:v['ratio'] for k,v in holdings.items()}, dtype=float).reindex(forecast.index).fillna(0.)
        current_prices = pd.Series({k:v['current_price'] for k,v in holdings.items()}, dtype=float).reindex(forecast.index)
        current_prices.fillna({k:v for k,v in self.mids_cache[-1].items() if k in current_prices.index}, inplace=True)

        # define optimisation problem 
        w = cp.Variable(len(forecast))
        tx_cost = self.tx * cp.norm(w - current_portfolio.values, 1)
        problem = cp.Problem(
            cp.Maximize(forecast.values.reshape(1,-1) @ w - tx_cost),
            [
                cp.sum(w) == 0,                        # delta neutral 
                cp.norm(w, 1) <= 1,                    # no leverage
                cp.abs(w) <= self.max_single_position  # max single position
            ]
        )
        problem.solve()

        # get new weights
        round_weights = np.round(w.value, 3)
        new_positions = pd.Series(round_weights, index=forecast.index)
        exp_return = forecast @ new_positions
        if exp_return < forecast @ current_portfolio:
            logging.info(f"Expected return: {float(exp_return)} < Current expected return: {float(forecast @ current_portfolio)}, not trading.")
            return [] # do not trade if expected return is less than current holdings
        weight_difference = new_positions - current_portfolio # trades in weight terms
        gbp_difference = self.gbp_size * weight_difference # trades in gbp terms
        gbp_difference[gbp_difference.abs()<self.min_gbp_size] = 0 # skip if trade size is too small
        sz_trades = gbp_difference / current_prices # trades in asset size terms

        # create orders
        orders = []
        for coin, sz in sz_trades.items():
            abs_sz = round(abs(float(sz)), self.asset_info[coin]['szDecimals'])
            if abs_sz == 0:
                continue # skip if position size is too small
            limit_px = current_prices[coin] * (1+self.slippage) if sz>0 else current_prices[coin] * (1-self.slippage)
            limit_px = float(f'{limit_px:.5g}')
            orders.append({'coin': coin, 'is_buy': sz>0, 'limit_px': limit_px, 'sz': abs_sz, 'order_type': {'limit': {'tif': 'Alo'}}, 'reduce_only': False})
        return orders
    
    def execute_orders(self, orders):
        try:
            self.exchange.bulk_orders(orders)
        except Exception as e:
            logging.error(f"Error {e}:\n executing orders {orders}\n")
            traceback.print_exc()
    
    def start(self):
        self.init_cache()
        self.subscribe() # process signal and forecast continuously
        time.sleep(5) # wait for cache
        while True:
            orders = self.get_orders() # make new portfolio every interval
            logging.info(f"New orders: {[(o['coin'], o['sz'] if o['is_buy'] else -o['sz']) for o in orders]}")
            self.execute_orders(orders)
            time.sleep(self.trade_interval)

    def stop(self):
        for sub, id in self.sub_to_id.items():
            self.info.unsubscribe(json.loads(sub), id)

if __name__=="__main__":

    logging.basicConfig(level=logging.INFO)
    
    config = {
        'min_gbp_size': 15,
        'gbp_size': 1000,
        'max_single_position': 0.1,
        'trade_interval': 60*10,
        'memory': 5000,
        'tx': 0.00035 + 0.0001,
        'slippage': 0.0001,
        'model_path': '../../../models/1h_csz.pickle'
    }

    agent = Agent(**config)
    agent.start()



