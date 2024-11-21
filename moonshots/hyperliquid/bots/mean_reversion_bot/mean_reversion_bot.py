import asyncio
import uvloop
import logging
import time
import traceback

import numpy as np
import pandas as pd
import cvxpy as cp
import statsmodels.api as sm

from moonshots.hyperliquid import HyperliquidAsync
from moonshots.hyperliquid.websocket_manager import WebsocketManager
from moonshots.hyperliquid.scraper import Scraper
from moonshots.utils.time import ms_timestamp
from moonshots.utils.json import dumps, loads

logger = logging.getLogger(__name__)

class MeanReversionBot:

    def __init__(self, config_path: str):
        """Mean reversion bot"""
        self.config_path = config_path
        self.config = {}
        self.client = HyperliquidAsync()
        self.ws = WebsocketManager()
        self.rolling_means = {}
        self.rolling_std = {}
        self.signals = {}
        self.positions = {}
        self.live_positions = False

    async def read_config(self):
        """Reads config file periodically to change parameters while running"""
        while True:
            with open(self.config_path) as f:
                self.config = loads(f.read())
            # Calculate ema alpha from ema_n_minutes
            self.config['alpha'] = 2 / (self.config['ema_n_minutes'] + 1)
            logger.info(f"Updated config: {self.config}")
            await asyncio.sleep(self.config['config_refresh_interval']) 

    async def init_candle_cache(self):
        """Populate historical candle cache and fit initial model"""
        logger.info("Initializing candle cache...")
        # find how many periods we need to look back
        end = ms_timestamp()
        start = end - self.config['ema_n_minutes'] * 1000 * 60
        # get historical candles
        scraper = Scraper()
        candles = await scraper.historical_candles(interval='1m', start=start, end=end)
        close_prices = candles['c'].unstack()
        # get signals and fit initial model
        rolling_means = close_prices.ewm(span=self.config['ema_n_minutes']).mean()
        rolling_stds = close_prices.ewm(span=self.config['ema_n_minutes']).std()
        z_scores = (close_prices - rolling_means) / rolling_stds
        signals = z_scores.subtract(z_scores.mean(axis=1), axis=0)
        avg_holding = int((np.sign(signals).diff().abs()==2).apply(lambda s: s[s].index.diff().mean()).mean().total_seconds()/60)
        logger.info(f'Average holding period: {avg_holding} minutes')
        x = signals.stack()
        y = close_prices.pct_change(avg_holding).shift(-avg_holding).stack()
        idx = x.dropna().index.intersection(y.dropna().index)
        self.model = sm.OLS(y.loc[idx], sm.add_constant(x.loc[idx])).fit()
        logger.info(f"Model fit:\n{self.model.summary()}")
        # store most recent data
        self.rolling_means = dict(rolling_means.iloc[-1])
        self.rolling_stds = dict(rolling_stds.iloc[-1])
        self.z_scores = dict(z_scores.iloc[-1])
        self.signals = dict(signals.iloc[-1])
        self.last_prices = dict(close_prices.iloc[-1])
        self.last_time = close_prices.index[-1].timestamp()

    def on_mids_update(self, msg):
        """Update internal state with new mid prices"""
        # update last time
        self.last_time = time.time()
        # update price data
        for coin in msg['data']['mids']:
            price = float(msg['data']['mids'][coin])
            self.last_prices[coin] = float(price)
            time_diff_minutes = (time.time() - self.last_time) / 60
            adjusted_alpha = 1 - (1 - self.config['alpha']) ** time_diff_minutes
            if coin not in self.rolling_means:
                self.rolling_means[coin] = price
            else:
                self.rolling_means[coin] = adjusted_alpha * price + (1 - adjusted_alpha) * self.rolling_means[coin]
            if coin not in self.rolling_std:
                self.rolling_std[coin] = 0.0
            else:
                time_diff_minutes = (time.time() - self.last_time) / 60
                adjusted_alpha = 1 - (1 - self.config['alpha']) ** time_diff_minutes
                deviation = price - self.rolling_means[coin]
                square_deviation = deviation ** 2
                self.rolling_std[coin] = np.sqrt(
                    adjusted_alpha * square_deviation + (1 - adjusted_alpha) * self.rolling_std[coin] ** 2
                )
                self.z_scores[coin] = (price - self.rolling_means[coin]) / self.rolling_std[coin] if self.rolling_std[coin] > 0 else 0.0
        mean_z_score = np.mean(self.z_scores.values())
        self.signals = {k: v - mean_z_score for k, v in self.z_scores.items()}

    def on_positions_update(self, msg):
        logger.info(f"Received webData2 update.")
        positions = msg['data']['clearinghouseState']['assetPositions']
        account_value = float(msg['data']['clearinghouseState']['marginSummary']['accountValue'])
        for p in positions:
            coin = p['position']['coin']
            value = float(p['position']['positionValue'])
            self.positions[coin] = value / account_value
            logger.info(f"Position update: {coin} - {self.positions[coin]}")
        self.live_positions = True

    async def execute_trades(self, coin_weights: dict):
        """Execute trades based on coin weights"""
        logger.info(f'PLACEHOLDER: Executing trades, coin weights: {coin_weights}')
        current_positions = self.positions
        for coin in coin_weights:
            trade_size = coin_weights[coin] - current_positions.get(coin, 0.0)


    async def run(self):
        """Main loop"""

        # read config every 10 seconds
        asyncio.create_task(self.read_config())
        if not self.config:
            logger.info("Config not yet read, waiting...")
            await asyncio.sleep(1)

        # get cache
        await self.init_candle_cache()
        if not self.last_prices:
            logger.info("Candle cache not yet initialized, waiting...")
            await asyncio.sleep(1)

        # get coin metadata for tick sizes etc.
        self.meta = await self.client.meta()

        # connect to websocket
        await self.ws.connect()

        # # subscribe to mids
        await self.ws.subscribe({'type': 'allMids'}, callback=self.on_mids_update)

        # subscribe to positions
        await self.ws.subscribe({'type': 'webData2', 'user': self.client.address}, callback=self.on_positions_update)
        if not self.live_positions:
            logger.info("Positions not yet received, waiting...")
            await asyncio.sleep(1)

        # main loop
        while True:
            try:
                
                # get expected return of coins and current holdings
                coins = list(self.last_prices.keys())  # List of coins to ensure consistent order
                expected_returns = self.model.predict(sm.add_constant(
                    [0.0 if np.isnan(self.signals[coin]) else self.signals[coin] for coin in coins]
                ))                
                current_holdings = np.array([self.positions.get(coin, 0.0) for coin in self.last_prices.keys()])
                num_assets = len(self.last_prices)

                # define optimisation problem
                weights = cp.Variable(num_assets)
                portfolio_return = expected_returns @ weights
                transaction_costs = cp.sum(cp.abs(weights - current_holdings)) * self.config['tx_cost'] 
                objective = cp.Maximize(portfolio_return - transaction_costs)
                constraints = [
                    cp.sum(cp.abs(weights)) <= self.config['max_exposure'],  # limit absolute exposure
                    cp.abs(weights) <= self.config['max_single_position']    # limit single largest position
                ]
                problem = cp.Problem(objective, constraints)
                problem.solve()

                # check if problem is solved
                if problem.status not in ["optimal", "optimal_inaccurate"]:
                    logger.error(f"Optimization failed with status: {problem.status}, defaulting to long-short weights")
                    # just take optimal weights from n largest and n smallest signals
                    signal_series = pd.Series(self.signals).fillna(0.0)
                    long_short = (
                        (signal_series>signal_series.quantile(0.9).astype(int)) 
                        - (signal_series<signal_series.quantile(0.1).astype(int))
                    )
                    optimal_weights = long_short / long_short.abs().sum()
                else:
                    optimal_weights = weights.value
                optimal_weights = np.round(optimal_weights, 3)
                exposure = np.sum(np.abs(optimal_weights))
                if exposure > self.config['max_exposure']:
                    logger.error(f"Exposure {exposure} exceeds maximum exposure {self.config['max_exposure']}, not trading")
                    continue
                # get coin weights
                coin_weights = {k:v for k,v in dict(zip(coins, optimal_weights)) if v != 0.0}
                logger.info(f"Optimized Portfolio Weights: {coin_weights}")
                await self.execute_trades(coin_weights)

            # shutdown on keyboard interrupt
            except KeyboardInterrupt:
                logger.info("Shutting down bot")
                await self.ws.close()
                break

            except Exception:
                logger.error(traceback.format_exc())
                breakpoint()
            
            # wait until next iteration
            await asyncio.sleep(self.config['trading_interval'])


async def main():
    bot = MeanReversionBot(config_path='./config.json')
    await bot.run()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    uvloop.run(main())