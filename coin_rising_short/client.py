import hashlib
import hmac
import logging
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from coin_rising_short import config

_time_offset_ms = 0
logger = logging.getLogger(__name__)


def refresh_time_offset() -> None:
    global _time_offset_ms
    r = _http_get(f"{config.BASE_URL_FUTURES}/fapi/v1/time", timeout=5)
    r.raise_for_status()
    server = int(r.json()["serverTime"])
    local = int(time.time() * 1000)
    _time_offset_ms = server - local


def effective_timestamp_ms() -> int:
    return int(time.time() * 1000) + _time_offset_ms


def _http_get(url: str, **kwargs) -> requests.Response:
    last: Optional[requests.Response] = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        last = requests.get(url, **kwargs)
        if last.status_code != 429:
            return last
        wait = int(last.headers.get("Retry-After", 1 + attempt))
        logger.warning(
            "Rate limit 429, %ss 후 재시도 (GET %s/%s)",
            wait,
            attempt + 1,
            config.HTTP_MAX_RETRIES,
            extra={"event": "http_rate_limit_get", "wait_sec": wait},
        )
        time.sleep(wait)
    return last  # type: ignore


def _http_post(url: str, **kwargs) -> requests.Response:
    last: Optional[requests.Response] = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        last = requests.post(url, **kwargs)
        if last.status_code != 429:
            return last
        wait = int(last.headers.get("Retry-After", 1 + attempt))
        logger.warning(
            "Rate limit 429, %ss 후 재시도 (POST %s/%s)",
            wait,
            attempt + 1,
            config.HTTP_MAX_RETRIES,
            extra={"event": "http_rate_limit_post", "wait_sec": wait},
        )
        time.sleep(wait)
    return last  # type: ignore


def _http_delete(url: str, **kwargs) -> requests.Response:
    last: Optional[requests.Response] = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        last = requests.delete(url, **kwargs)
        if last.status_code != 429:
            return last
        wait = int(last.headers.get("Retry-After", 1 + attempt))
        logger.warning(
            "Rate limit 429, %ss 후 재시도 (DELETE %s/%s)",
            wait,
            attempt + 1,
            config.HTTP_MAX_RETRIES,
            extra={"event": "http_rate_limit_delete", "wait_sec": wait},
        )
        time.sleep(wait)
    return last  # type: ignore


def sign_hmac_sha256(params: dict) -> str:
    query = urlencode(params, doseq=True)
    sig = hmac.new(config.API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    return f"{query}&signature={sig}"


def signed_request(method: str, path: str, params: Optional[dict] = None) -> requests.Response:
    headers = {"X-MBX-APIKEY": config.API_KEY}
    last_response: Optional[requests.Response] = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        p = dict(params or {})
        p.setdefault("timestamp", effective_timestamp_ms())
        p.setdefault("recvWindow", 8000)
        qs = sign_hmac_sha256(p)
        url = f"{config.BASE_URL_FUTURES}{path}?{qs}"
        method_upper = method.upper()
        if method_upper == "GET":
            last_response = _http_get(url, headers=headers, timeout=10)
        elif method_upper == "DELETE":
            last_response = _http_delete(url, headers=headers, timeout=10)
        else:
            last_response = _http_post(url, headers=headers, timeout=10)

        if last_response.status_code == 429:
            wait = int(last_response.headers.get("Retry-After", 1 + attempt))
            logger.warning(
                "서명 요청 429, %ss 후 재시도 (%s/%s)",
                wait,
                attempt + 1,
                config.HTTP_MAX_RETRIES,
                extra={"event": "signed_rate_limit", "wait_sec": wait},
            )
            time.sleep(wait)
            continue
        if last_response.status_code == 418:
            time.sleep(min(2**attempt, 30))
            continue

        try:
            body = last_response.json()
        except Exception:
            return last_response

        if isinstance(body, dict) and body.get("code") == -1021:
            logger.warning(
                "타임스탬프 오차(-1021), 서버 시간 재동기화 후 재시도",
                extra={"event": "timestamp_resync"},
            )
            refresh_time_offset()
            time.sleep(0.25)
            continue

        return last_response

    return last_response  # type: ignore


def parse_json_response(response: requests.Response, context: str) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"{context} HTTP 오류: {response.status_code} / {response.text}")
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"{context} JSON 파싱 실패: {exc}") from exc
