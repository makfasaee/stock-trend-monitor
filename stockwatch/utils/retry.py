"""tenacity retry decorators for external I/O calls."""

from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from stockwatch.providers.base import ProviderError


# Retry up to 3 times with exponential backoff + jitter on ProviderError
retry_on_provider_error = retry(
    retry=retry_if_exception_type(ProviderError),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30, jitter=2),
    reraise=True,
)

# Generic network retry (e.g. for SES, tweepy)
retry_on_network_error = retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=20, jitter=2),
    reraise=True,
)
