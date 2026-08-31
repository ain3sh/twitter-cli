"""Tests for the orthogonal filter contract."""

from __future__ import annotations

from twitter_cli.filter import filter_tweets, score_tweet
from twitter_cli.models import Metrics


def test_filter_scores_without_mutating_input(tweet_factory) -> None:
    tweet = tweet_factory("1", score=0.0)

    output = filter_tweets([tweet], {"weights": {}})

    assert tweet.score == 0.0
    assert output[0].score > 0.0
    assert output[0] is not tweet


def test_filter_composes_language_retweet_score_and_limit(tweet_factory) -> None:
    tweets = [
        tweet_factory("high", lang="en", metrics=Metrics(likes=100)),
        tweet_factory("middle", lang="en", metrics=Metrics(likes=50)),
        tweet_factory("low", lang="en", metrics=Metrics(likes=1)),
        tweet_factory("other-language", lang="zh", metrics=Metrics(likes=1000)),
        tweet_factory("retweet", lang="en", is_retweet=True, metrics=Metrics(likes=1000)),
    ]

    output = filter_tweets(
        tweets,
        {
            "lang": ["en"],
            "excludeRetweets": True,
            "minScore": 10,
            "limit": 2,
            "weights": {},
        },
    )

    assert [tweet.id for tweet in output] == ["high", "middle"]


def test_filter_without_optional_bounds_returns_all_sorted(tweet_factory) -> None:
    tweets = [
        tweet_factory("low", metrics=Metrics(likes=1)),
        tweet_factory("high", metrics=Metrics(likes=100)),
    ]

    output = filter_tweets(tweets, {})

    assert [tweet.id for tweet in output] == ["high", "low"]


def test_score_tweet_uses_canonical_weight_names(tweet_factory) -> None:
    weights = {
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "bookmarks": 0,
        "viewsLog": 0,
    }

    assert score_tweet(tweet_factory("1"), weights) == 0.0
