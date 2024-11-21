import time
import logging

logger = logging.getLogger(__name__)

def ms_timestamp():
    """
    Get current timestamp in milliseconds
    """
    return int(time.time()*1000)