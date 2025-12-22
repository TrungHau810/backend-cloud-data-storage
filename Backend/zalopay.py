import hashlib
import hmac
from typing import Dict


def generate_mac(data: str, key: str) -> str:
    return hmac.new(
        key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def create_order_mac(order: Dict, key1: str) -> str:
    """
    Dùng cho API create order
    """
    data = "|".join([
        str(order["app_id"]),
        order["app_trans_id"],
        order["app_user"],
        str(order["amount"]),
        str(order["app_time"]),
        order["embed_data"],
        order["item"],
    ])
    return generate_mac(data, key1)


def verify_callback_mac(data: str, mac: str, key2: str) -> bool:
    """
    Dùng cho callback từ ZaloPay
    """
    calculated_mac = generate_mac(data, key2)
    return calculated_mac == mac