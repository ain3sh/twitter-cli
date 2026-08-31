"""Strict configuration loading from the XDG user config directory."""

from __future__ import annotations

from typing import Any

import yaml

from .exceptions import InvalidInputError
from .paths import config_file

DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "fetch": {
        "count": 20,
    },
    "filter": {
        "lang": [],
        "excludeRetweets": False,
        "minScore": None,
        "limit": None,
        "weights": {
            "likes": 1.0,
            "retweets": 3.0,
            "replies": 2.0,
            "bookmarks": 5.0,
            "viewsLog": 0.5,
        },
    },
    "rateLimit": {
        "requestDelay": 2.5,
        "maxRetries": 3,
        "retryBaseDelay": 5.0,
    },
}

_ROOT_KEYS = frozenset(DEFAULT_CONFIG)


def load_config() -> dict[str, Any]:
    """Load and validate the one supported config shape."""
    path = config_file()
    if not path.is_file():
        return _validate_config({})

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidInputError(f"Failed to read config file {path}: {exc}") from exc

    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise InvalidInputError(f"Invalid YAML in config file {path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise InvalidInputError("Config root must be a mapping.")
    return _validate_config(parsed)


def _validate_config(config: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(config, _ROOT_KEYS, "config")

    fetch = _section(config, "fetch")
    _reject_unknown_keys(fetch, {"count"}, "fetch")

    filter_config = _section(config, "filter")
    _reject_unknown_keys(
        filter_config,
        {"lang", "excludeRetweets", "minScore", "limit", "weights"},
        "filter",
    )

    weights = _mapping(filter_config.get("weights", {}), "filter.weights")
    default_weights = DEFAULT_CONFIG["filter"]["weights"]
    _reject_unknown_keys(weights, set(default_weights), "filter.weights")

    rate_limit = _section(config, "rateLimit")
    _reject_unknown_keys(
        rate_limit,
        {"requestDelay", "maxRetries", "retryBaseDelay"},
        "rateLimit",
    )

    langs = filter_config.get("lang", DEFAULT_CONFIG["filter"]["lang"])
    if not isinstance(langs, list) or not all(
        isinstance(lang, str) and lang
        for lang in langs
    ):
        raise InvalidInputError("filter.lang must be a list of non-empty strings.")

    exclude_retweets = filter_config.get(
        "excludeRetweets",
        DEFAULT_CONFIG["filter"]["excludeRetweets"],
    )
    if not isinstance(exclude_retweets, bool):
        raise InvalidInputError("filter.excludeRetweets must be a boolean.")

    return {
        "fetch": {
            "count": _positive_int(
                fetch.get("count", DEFAULT_CONFIG["fetch"]["count"]),
                "fetch.count",
            ),
        },
        "filter": {
            "lang": list(langs),
            "excludeRetweets": exclude_retweets,
            "minScore": _optional_number(
                filter_config.get("minScore", DEFAULT_CONFIG["filter"]["minScore"]),
                "filter.minScore",
            ),
            "limit": _optional_positive_int(
                filter_config.get("limit", DEFAULT_CONFIG["filter"]["limit"]),
                "filter.limit",
            ),
            "weights": {
                key: _number(
                    weights.get(key, default),
                    f"filter.weights.{key}",
                )
                for key, default in default_weights.items()
            },
        },
        "rateLimit": {
            "requestDelay": _non_negative_number(
                rate_limit.get(
                    "requestDelay",
                    DEFAULT_CONFIG["rateLimit"]["requestDelay"],
                ),
                "rateLimit.requestDelay",
            ),
            "maxRetries": _non_negative_int(
                rate_limit.get(
                    "maxRetries",
                    DEFAULT_CONFIG["rateLimit"]["maxRetries"],
                ),
                "rateLimit.maxRetries",
            ),
            "retryBaseDelay": _positive_number(
                rate_limit.get(
                    "retryBaseDelay",
                    DEFAULT_CONFIG["rateLimit"]["retryBaseDelay"],
                ),
                "rateLimit.retryBaseDelay",
            ),
        },
    }


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return _mapping(config.get(key, {}), key)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidInputError(f"{path} must be a mapping.")
    return value


def _reject_unknown_keys(
    value: dict[str, Any],
    allowed: set[str] | frozenset[str],
    path: str,
) -> None:
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise InvalidInputError(
            f"{path} has unknown keys: {', '.join(unknown)}."
        )


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(f"{path} must be a number.")
    return float(value)


def _optional_number(value: Any, path: str) -> float | None:
    if value is None:
        return None
    return _number(value, path)


def _positive_number(value: Any, path: str) -> float:
    number = _number(value, path)
    if number <= 0:
        raise InvalidInputError(f"{path} must be greater than 0.")
    return number


def _non_negative_number(value: Any, path: str) -> float:
    number = _number(value, path)
    if number < 0:
        raise InvalidInputError(f"{path} must be at least 0.")
    return number


def _positive_int(value: Any, path: str) -> int:
    integer = _integer(value, path)
    if integer <= 0:
        raise InvalidInputError(f"{path} must be greater than 0.")
    return integer


def _optional_positive_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, path)


def _non_negative_int(value: Any, path: str) -> int:
    integer = _integer(value, path)
    if integer < 0:
        raise InvalidInputError(f"{path} must be at least 0.")
    return integer


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInputError(f"{path} must be an integer.")
    return value
