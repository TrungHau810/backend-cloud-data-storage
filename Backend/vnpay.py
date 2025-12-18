import hmac
import hashlib
from urllib.parse import quote_plus
from config import settings


def create_vnpay_signature(params: dict) -> str:
    hash_secret = settings.VNPAY_HASH_SECRET_KEY

    # 1. sort params
    sorted_params = sorted(params.items())

    # 2. build query string (KHỚP 100% với URL)
    query_string = "&".join(
        f"{k}={quote_plus(str(v))}"
        for k, v in sorted_params
        if v is not None and v != "" and k not in ["vnp_SecureHash", "vnp_SecureHashType"]
    )

    # 3. sign
    return hmac.new(
        hash_secret.encode(),
        query_string.encode(),
        hashlib.sha512
    ).hexdigest()