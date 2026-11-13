"""Local, privacy-safe model usage ledger and explicit list-price estimates."""

import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


PRICE_SOURCE = "https://developers.openai.com/api/docs/models/gpt-6.1-sol"
PRICE_DATE = "2026-11-13"
_SOL_RATES = {
    "input": Decimal("2.00"),
    "cached_input": Decimal("0.10"),
    "cache_write_30m": Decimal("2.50"),
    "cache_write_12h": Decimal("5.00"),
    "output": Decimal("10.00"),
}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _count(value: Any) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def summarize_response_usage(usage: Any, model: str) -> dict[str, Any]:
    """Use response.usage counts; unknown billing details stay unknown."""

    input_tokens = _count(_field(usage, "input_tokens"))
    output_tokens = _count(_field(usage, "output_tokens"))
    details = _field(usage, "input_tokens_details")
    cached = _count(_field(details, "cached_tokens"))
    writes = _count(_field(details, "cache_write_tokens"))
    lifetimes = _field(details, "cache_write_tokens_details")
    write_30m = _count(_field(lifetimes, "ttl_30m_tokens"))
    write_12h = _count(_field(lifetimes, "ttl_12h_tokens"))
    if writes == 0 and write_30m is None and write_12h is None:
        write_30m = write_12h = 0
    unpriced_reason = None
    estimated_usd = None
    if model != "gpt-6.1-sol":
        unpriced_reason = "model_rate_unconfigured"
    elif input_tokens is None or output_tokens is None:
        unpriced_reason = "usage_missing"
    elif cached is None or writes is None or cached + writes > input_tokens:
        unpriced_reason = "input_breakdown_missing_or_invalid"
    elif write_30m is None or write_12h is None or write_30m + write_12h != writes:
        unpriced_reason = "cache_write_lifetime_missing"
    else:
        uncached = input_tokens - cached - writes
        input_multiplier = Decimal(2) if input_tokens > 272_000 else Decimal(1)
        output_multiplier = Decimal("1.5") if input_tokens > 272_000 else Decimal(1)
        amount = (
            input_multiplier
            * (
                uncached * _SOL_RATES["input"]
                + cached * _SOL_RATES["cached_input"]
                + write_30m * _SOL_RATES["cache_write_30m"]
                + write_12h * _SOL_RATES["cache_write_12h"]
            )
            + output_multiplier * output_tokens * _SOL_RATES["output"]
        ) / Decimal(1_000_000)
        estimated_usd = float(amount.quantize(Decimal("0.000001")))
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached,
        "cache_write_30m_tokens": write_30m,
        "cache_write_12h_tokens": write_12h,
        "estimated_usd": estimated_usd,
        "unpriced_reason": unpriced_reason,
        "price_source": PRICE_SOURCE,
        "price_date": PRICE_DATE,
    }


def record_model_usage(
    usage: Any,
    model: str,
    *,
    source: str,
    status: str = "completed",
    error_type: str | None = None,
) -> dict[str, Any]:
    """Append one record per API request; caller text and contact are never stored."""

    summary = summarize_response_usage(usage, model)
    record = {
        "request_id": uuid.uuid4().hex,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "status": status,
        "error_type": error_type,
        **summary,
    }
    path = Path(os.environ.get("SOPHIE_USAGE_LEDGER", ".local-sophie-usage.jsonl"))
    payload = (json.dumps(record, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "ab", closefd=False) as stream:
            fcntl.flock(fd, fcntl.LOCK_EX)
            stream.write(payload)
            stream.flush()
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return record
