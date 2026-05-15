"""
Shared HTTP request helper with retry/backoff for all scrapers.

Retries on:
  - Network errors (TimeoutException, ConnectError, ReadError)
  - 5xx server errors
  - 429 rate limits

Does NOT retry on:
  - 4xx client errors other than 429 (those are real bugs)
"""
import logging
from typing import Optional
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
    retry_if_exception, before_sleep_log,
)

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class RetryableHTTPError(Exception):
    """A 5xx/429 response we want tenacity to retry on."""


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, RetryableHTTPError)):
        return True
    return False


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception(_should_retry),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def request(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    follow_redirects: bool = True,
) -> httpx.Response:
    merged_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
    if headers:
        merged_headers.update(headers)

    with httpx.Client(timeout=timeout, follow_redirects=follow_redirects) as client:
        resp = client.request(method, url, params=params, headers=merged_headers)
        if 500 <= resp.status_code < 600 or resp.status_code == 429:
            raise RetryableHTTPError(
                f"Retryable status {resp.status_code} from {url}"
            )
        resp.raise_for_status()
        return resp


def get(url: str, **kwargs) -> httpx.Response:
    return request("GET", url, **kwargs)


def get_json(url: str, **kwargs):
    return get(url, **kwargs).json()


def get_text(url: str, **kwargs) -> str:
    return get(url, **kwargs).text
