import orjson

def dumps(obj: dict):
    return orjson.dumps(obj).decode()

def loads(s: str):
    return orjson.loads(s.encode())