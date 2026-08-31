"""Tweet filtering and engagement scoring."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .models import Tweet

DEFAULT_WEIGHTS = {
    "likes": 1.0,
    "retweets": 3.0,
    "replies": 2.0,
    "bookmarks": 5.0,
    "viewsLog": 0.5,
}


def score_tweet(tweet: Tweet, weights: Optional[Dict[str, float]] = None) -> float:
    """Calculate engagement score for a single tweet.

    Formula:
      score = w_likes × likes
            + w_retweets × retweets
            + w_replies × replies
            + w_bookmarks × bookmarks
            + the configured viewsLog weight × log10(views)

    Args:
        weights: Pre-built weight dict. If None, uses DEFAULT_WEIGHTS.
    """
    w = weights or DEFAULT_WEIGHTS
    m = tweet.metrics
    return (
        w.get("likes", 1.0) * m.likes
        + w.get("retweets", 3.0) * m.retweets
        + w.get("replies", 2.0) * m.replies
        + w.get("bookmarks", 5.0) * m.bookmarks
        + w.get("viewsLog", 0.5) * math.log10(max(m.views, 1))
    )


def filter_tweets(tweets: Sequence[Tweet], config: Mapping[str, Any]) -> List[Tweet]:
    """Filter and rank tweets according to config.

    Config keys:
      lang: list[str]  (empty = no filter)
      excludeRetweets: bool
      minScore: optional float
      limit: optional int
      weights: dict
    """
    filtered = list(tweets)

    # 1. Language filter
    lang_filter = config.get("lang", [])
    if lang_filter:
        lang_set = {str(lang) for lang in lang_filter if str(lang)}
        filtered = [tweet for tweet in filtered if tweet.lang in lang_set]

    # 2. Exclude retweets
    if config.get("excludeRetweets", False):
        filtered = [tweet for tweet in filtered if not tweet.is_retweet]

    # 3. Score all tweets
    weights = _build_weights(config.get("weights", {}))
    scored = [replace(tweet, score=round(score_tweet(tweet, weights), 1)) for tweet in filtered]

    # 4. Sort by score (descending)
    scored.sort(key=lambda tweet: tweet.score or 0.0, reverse=True)

    min_score = config.get("minScore")
    if min_score is not None:
        scored = [tweet for tweet in scored if (tweet.score or 0.0) >= min_score]

    limit = config.get("limit")
    return scored[:limit] if limit is not None else scored


def _build_weights(raw_weights: Mapping[str, Any]) -> Dict[str, float]:
    """Merge canonical custom weights with defaults."""
    merged = {}
    for key, default_value in DEFAULT_WEIGHTS.items():
        merged[key] = raw_weights.get(key, default_value)
    return merged
