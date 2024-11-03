import pandas as pd

def parse_candles_to_pandas(candles: list[dict]):
    """
    Parse Hyperliquid API candle snapshot into pandas DataFrame

    inputs:
        candles: list of dicts
            {
                't': int - candle start timestamp
                'T': int - candle end timestamp
                's': str - symbol
                'i': str - interval
                'o': float - open
                'c': float - close
                'h': float - high
                'l': float - low
                'v': float - volume
                'n': int - number of trades
            }

    outputs:
        df: pd.DataFrame

    """
    df = pd.DataFrame(candles).drop('T', axis=1)
    df['t'] = pd.to_datetime(df['t'], unit='ms')
    df.set_index(['t','s'], inplace=True)
    df[['o', 'c', 'h', 'l', 'v']] = df[['o', 'c', 'h', 'l', 'v']].astype(float)
    df['n'] = df['n'].astype(int)
    return df.sort_index()