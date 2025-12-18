
from __future__ import annotations

import requests

DEFAULT_TIMEOUT = 2.0

def post_bytes(url: str, data: bytes, timeout: float = DEFAULT_TIMEOUT) -> requests.Response:
    return requests.post(url, data=data, timeout=timeout)

def put_bytes(url: str, data: bytes, timeout: float = DEFAULT_TIMEOUT) -> requests.Response:
    return requests.put(url, data=data, timeout=timeout)

def get_bytes(url: str, timeout: float = DEFAULT_TIMEOUT) -> requests.Response:
    return requests.get(url, timeout=timeout)

