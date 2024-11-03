import time
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def ms_timestamp():
    """
    Get current timestamp in milliseconds
    """
    return int(time.time()*1000)

def log_time(func):
    """
    Log time taken by function
    """
    def wrapper(*args, **kwargs):
        start = ms_timestamp()
        result = func(*args, **kwargs)
        end = ms_timestamp()
        logger.info(f"{func.__name__} took {end-start}ms")
        return result
    return wrapper

def async_log_time(func):
    """
    Log time taken by async function
    """
    async def wrapper(*args, **kwargs):
        start = ms_timestamp()
        result = await func(*args, **kwargs)
        end = ms_timestamp()
        logger.debug(f"{func.__name__} took {end-start}ms")
        return result
    return wrapper
