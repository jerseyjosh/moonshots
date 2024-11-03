import numpy as np
from numba import jit

@jit(nopython=True, cache=True)
def jit_round(x: float, n: int):
    """
    Round x to n decimal places
    """
    return np.round(x, n)

@jit(nopython=True, cache=True)
def jit_bollinger_bands(mids: np.array, n: int = 2):
    """
    Calculate bollinger bands for given mids

    inputs:
        mids: np.array of mid prices
        n: number of standard deviations
    outputs:
        lower: lower bollinger band
        upper: upper bollinger band
    """
    mid = mids[-1]
    std = np.std(mids)
    return mid - n*std, mid + n*std