import hmac
import hashlib

def create_momo_signature(raw_signature: str, secret_key: str):
    return hmac.new(
        secret_key.encode(),
        raw_signature.encode(),
        hashlib.sha256
    ).hexdigest()
