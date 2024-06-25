from datetime import datetime
import logging
import time

def timestamp():
    return datetime.now()

def log_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        logging.info(f"{func.__name__} took {time.time() - start}")
        return result
    return wrapper