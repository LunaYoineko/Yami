import json
import hashlib
import time
from websocket import create_connection

DEFAULT_RELAY = "wss://yabu.me"

def get_nostr_entropy(relay_url=DEFAULT_RELAY, count=10):
    try:
        ws = create_connection(relay_url, timeout=10)
    except Exception as e:
        raise RuntimeError(f"リレー接続エラー ({relay_url}): {e}")
    
    req = [
        "REQ",
        "rand_subscription",
        {"kinds": [1], "limit": count}
    ]
    ws.send(json.dumps(req))
    
    contents_data = []
    
    while len(contents_data) < count:
        try:
            result = ws.recv()
            data = json.loads(result)
            
            if data[0] == "EVENT":
                event = data[2]
                content = event.get("content", "")
                created_at = event.get("created_at", 0)
                
                contents_data.append({
                    "length": len(content),
                    "created_at": created_at,
                    "id": event.get("id", "")
                })
        except Exception as e:
            ws.close()
            raise RuntimeError(f"データ受信中にエラーが発生しました: {e}")
    
    ws.close()
    
    entropy_string = "".join([f"{d['length']}-{d['created_at']}-{d['id']}" for d in contents_data])
    entropy_string += str(time.time_ns())
    return hashlib.sha256(entropy_string.encode('utf-8')).digest()

def nosrandom(min_val=1, max_val=6, relay_url=DEFAULT_RELAY):
    if min_val > max_val:
        raise ValueError("min_val は max_val 以下である必要があります")
    
    hash_bytes = get_nostr_entropy(relay_url=relay_url, count=10)
    
    rand_int64 = int.from_bytes(hash_bytes[:8], byteorder='big')
    
    range_size = (max_val - min_val) + 1
    result = min_val + (rand_int64 % range_size)
    
    return result

if __name__ == "__main__":
    dice = nosrandom(1, 6)
    
    print(f"出目: {dice}")