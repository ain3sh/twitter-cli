from __future__ import annotations

from twitter_cli.models import Timeline
from twitter_cli.output import render_success
from twitter_cli.serialization import (
    timeline_from_structured,
    tweet_from_dict,
    tweet_to_dict,
    tweets_to_data,
)


def test_tweet_roundtrip_uses_one_recursive_shape(tweet_factory) -> None:
    quoted = tweet_factory("41", text="quoted")
    tweet = tweet_factory("42", quoted_tweet=quoted)

    payload = tweet_to_dict(tweet)
    restored = tweet_from_dict(payload)

    assert payload["author"]["username"] == "alice"
    assert payload["quotedTweet"] == tweet_to_dict(quoted)
    assert restored == tweet


def test_timeline_roundtrip_preserves_pagination(tweet_factory) -> None:
    timeline = Timeline(
        [tweet_factory("1"), tweet_factory("2", lang="zh")],
        next_cursor="cursor-2",
    )
    raw = render_success(
        tweets_to_data(timeline.tweets),
        "yaml",
        pagination={"nextCursor": timeline.next_cursor},
    )

    restored = timeline_from_structured(raw)

    assert restored == timeline


def test_timeline_accepts_canonical_json_envelope(tweet_factory) -> None:
    raw = render_success(tweets_to_data([tweet_factory("1")]), "json")

    restored = timeline_from_structured(raw)

    assert [tweet.id for tweet in restored.tweets] == ["1"]
    assert restored.next_cursor is None
