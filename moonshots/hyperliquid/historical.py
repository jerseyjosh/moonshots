import os
import io
import pandas as pd
import boto3
import json
from botocore import UNSIGNED
import lz4.frame

class HistoricalData:
    def __init__(self):
        # s3://hyperliquid-archive/market_data/20230916/9/l2Book/SOL.lz4
        self.bucket_name = 'hyperliquid-archive'
        self.base_url = 's3://hyperliquid-archive/market_data/'
        self.s3 = boto3.client('s3', config=boto3.session.Config(signature_version=UNSIGNED))

    def get_data(self, date, hour, datatype, coin, output_path=None):
        date = pd.to_datetime(date).strftime('%Y%m%d')
        key = os.path.join('market_data', str(date), str(hour), str(datatype), str(coin)+'.lz4')
        buffer = io.BytesIO()
        self.s3.download_fileobj(self.bucket_name, key, buffer)
        buffer.seek(0)
        data = lz4.frame.decompress(buffer.read())
        return data
    
    def parse_to_df(self, data):
        data_str = data.decode('utf-8')
        json_objects = data_str.split('\n')
        parsed_data = [json.loads(obj) for obj in json_objects if obj.strip() != '']
        df = pd.json_normalize(parsed_data)
        
        return df


if __name__=="__main__":
    client = HistoricalData()
    data = client.get_data('20230916', '9', 'l2Book', 'SOL')
    breakpoint()