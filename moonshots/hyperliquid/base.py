import concurrent.futures

import pandas as pd
from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL  

from moonshots.hyperliquid.utils import setup

class Hyperliquid:

    def __init__(self, skip_ws=False):
        self.address, self.info, self.exchange = setup(skip_ws)
    
    def get_assets(self):
        universe = self.info.meta()['universe']
        return [asset['name'] for asset in universe]
    
    def all_candles_snapshot(self, interval: str, start: int = None, end: int = None, n=5000, parse_pandas=False, n_threads=10):
        assets = self.get_assets()
        now = pd.Timestamp.now()-pd.Timedelta('1min')
        if end is None:
            end = int(now.timestamp()*1000)
        if start is None:
            start = int((now - n * pd.Timedelta(interval)).timestamp()*1000)
        result = []
        with concurrent.futures.ThreadPoolExecutor(n_threads) as executor:
            futures = {executor.submit(self.candles_snapshot, asset, interval, start, end, n, False): asset for asset in assets}
            for future in concurrent.futures.as_completed(futures):
                result += future.result()
        return self.candle_to_df(result) if parse_pandas else result
    
    def candles_snapshot(self, coin: str, interval: str, start: int = None, end: int =None, n=5000, parse_pandas=False):
        now = pd.Timestamp.now()
        if end is None:
            end = int(now.timestamp()*1000)
        if start is None:
            start = int((now - n * pd.Timedelta(interval)).timestamp()*1000)
        result = self.info.candles_snapshot(coin, interval, start, end)
        return self.candle_to_df(result) if parse_pandas else result
    
    @staticmethod
    def candle_to_df(data: list[tuple]):
        df = pd.DataFrame(data)
        df.drop(['T','i'], axis=1, inplace=True)
        df.rename({'t': 'time', 's': 'coin', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 'n': 'n_trades'}, axis=1, inplace=True)
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        n_markets = df['coin'].nunique()
        return df.set_index('time') if n_markets==1 else df.set_index(['time', 'coin'])


if __name__=="__main__":
    hl = Hyperliquid()
    breakpoint()