"""Canonical wire conversion for twitter-cli models."""

from __future__ import annotations

from typing import Any, Iterable, Literal

import yaml

from .models import Author, BookmarkFolder, Metrics, Timeline, Tweet, TweetMedia, UserProfile

_TWEET_FIELDS = {
    "id",
    "text",
    "author",
    "metrics",
    "createdAt",
    "media",
    "urls",
    "isRetweet",
    "retweetedBy",
    "lang",
    "isSubscriberOnly",
    "isPromoted",
}
_TWEET_OPTIONAL_FIELDS = {"quotedTweet", "score", "articleTitle", "articleText"}
_AUTHOR_FIELDS = {"id", "name", "username", "profileImageUrl", "verified"}
_METRIC_FIELDS = {"likes", "retweets", "replies", "quotes", "views", "bookmarks"}
_MEDIA_FIELDS = {"type", "url", "width", "height"}


def tweet_to_dict(tweet: Tweet) -> dict[str, Any]:
    """Convert a Tweet to its one wire shape."""
    data: dict[str, Any] = {
        "id": tweet.id,
        "text": tweet.text,
        "author": {
            "id": tweet.author.id,
            "name": tweet.author.name,
            "username": tweet.author.username,
            "profileImageUrl": tweet.author.profile_image_url,
            "verified": tweet.author.verified,
        },
        "metrics": {
            "likes": tweet.metrics.likes,
            "retweets": tweet.metrics.retweets,
            "replies": tweet.metrics.replies,
            "quotes": tweet.metrics.quotes,
            "views": tweet.metrics.views,
            "bookmarks": tweet.metrics.bookmarks,
        },
        "createdAt": tweet.created_at,
        "media": [
            {
                "type": media.type,
                "url": media.url,
                "width": media.width,
                "height": media.height,
            }
            for media in tweet.media
        ],
        "urls": list(tweet.urls),
        "isRetweet": tweet.is_retweet,
        "retweetedBy": tweet.retweeted_by,
        "lang": tweet.lang,
        "isSubscriberOnly": tweet.is_subscriber_only,
        "isPromoted": tweet.is_promoted,
    }
    if tweet.quoted_tweet is not None:
        data["quotedTweet"] = tweet_to_dict(tweet.quoted_tweet)
    if tweet.score is not None:
        data["score"] = tweet.score
    if tweet.article_title is not None:
        data["articleTitle"] = tweet.article_title
    if tweet.article_text is not None:
        data["articleText"] = tweet.article_text
    return data


def tweet_from_dict(data: dict[str, Any]) -> Tweet:
    """Parse one current Tweet wire shape."""
    _exact_keys(data, _TWEET_FIELDS, _TWEET_OPTIONAL_FIELDS, "tweet")
    author_data = _mapping(data["author"], "tweet.author")
    metrics_data = _mapping(data["metrics"], "tweet.metrics")
    _exact_keys(author_data, _AUTHOR_FIELDS, set(), "tweet.author")
    _exact_keys(metrics_data, _METRIC_FIELDS, set(), "tweet.metrics")

    media_data = _list(data["media"], "tweet.media")
    media = []
    for index, raw_media in enumerate(media_data):
        item = _mapping(raw_media, f"tweet.media[{index}]")
        _exact_keys(item, _MEDIA_FIELDS, set(), f"tweet.media[{index}]")
        media.append(
            TweetMedia(
                type=_media_type(item["type"], f"tweet.media[{index}].type"),
                url=_string(item["url"], f"tweet.media[{index}].url"),
                width=_optional_integer(item["width"], f"tweet.media[{index}].width"),
                height=_optional_integer(item["height"], f"tweet.media[{index}].height"),
            )
        )

    raw_urls = _list(data["urls"], "tweet.urls")
    urls = [_string(url, f"tweet.urls[{index}]") for index, url in enumerate(raw_urls)]

    quoted_data = data.get("quotedTweet")
    if quoted_data is not None and not isinstance(quoted_data, dict):
        raise ValueError("tweet.quotedTweet must be a mapping.")

    score = data.get("score")
    if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
        raise ValueError("tweet.score must be a number.")

    return Tweet(
        id=_string(data["id"], "tweet.id"),
        text=_string(data["text"], "tweet.text"),
        author=Author(
            id=_string(author_data["id"], "tweet.author.id"),
            name=_string(author_data["name"], "tweet.author.name"),
            username=_string(author_data["username"], "tweet.author.username"),
            profile_image_url=_string(
                author_data["profileImageUrl"],
                "tweet.author.profileImageUrl",
            ),
            verified=_boolean(author_data["verified"], "tweet.author.verified"),
        ),
        metrics=Metrics(
            likes=_integer(metrics_data["likes"], "tweet.metrics.likes"),
            retweets=_integer(metrics_data["retweets"], "tweet.metrics.retweets"),
            replies=_integer(metrics_data["replies"], "tweet.metrics.replies"),
            quotes=_integer(metrics_data["quotes"], "tweet.metrics.quotes"),
            views=_integer(metrics_data["views"], "tweet.metrics.views"),
            bookmarks=_integer(metrics_data["bookmarks"], "tweet.metrics.bookmarks"),
        ),
        created_at=_string(data["createdAt"], "tweet.createdAt"),
        media=media,
        urls=urls,
        is_retweet=_boolean(data["isRetweet"], "tweet.isRetweet"),
        retweeted_by=_optional_string(data["retweetedBy"], "tweet.retweetedBy"),
        quoted_tweet=tweet_from_dict(quoted_data) if quoted_data is not None else None,
        lang=_string(data["lang"], "tweet.lang"),
        score=float(score) if score is not None else None,
        article_title=_optional_string(data.get("articleTitle"), "tweet.articleTitle"),
        article_text=_optional_string(data.get("articleText"), "tweet.articleText"),
        is_subscriber_only=_boolean(
            data["isSubscriberOnly"],
            "tweet.isSubscriberOnly",
        ),
        is_promoted=_boolean(data["isPromoted"], "tweet.isPromoted"),
    )


def timeline_from_structured(raw: str) -> Timeline:
    """Parse a timeline from the canonical YAML/JSON success envelope."""
    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid timeline YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Timeline input must be a mapping.")
    _exact_keys(payload, {"ok", "schemaVersion", "data"}, {"pagination"}, "envelope")
    if payload["ok"] is not True or payload["schemaVersion"] != "1":
        raise ValueError("Timeline input must be a schemaVersion 1 success envelope.")

    data = _list(payload["data"], "envelope.data")
    pagination = payload.get("pagination")
    next_cursor = None
    if pagination is not None:
        pagination_data = _mapping(pagination, "envelope.pagination")
        _exact_keys(
            pagination_data,
            {"nextCursor"},
            set(),
            "envelope.pagination",
        )
        next_cursor = _string(
            pagination_data["nextCursor"],
            "envelope.pagination.nextCursor",
        )

    return Timeline(
        [
            tweet_from_dict(_mapping(item, f"envelope.data[{index}]"))
            for index, item in enumerate(data)
        ],
        next_cursor,
    )


def tweets_to_data(tweets: Iterable[Tweet]) -> list[dict[str, Any]]:
    return [tweet_to_dict(tweet) for tweet in tweets]


def bookmark_folder_to_dict(folder: BookmarkFolder) -> dict[str, Any]:
    return {"id": folder.id, "name": folder.name}


def bookmark_folders_to_data(folders: Iterable[BookmarkFolder]) -> list[dict[str, Any]]:
    return [bookmark_folder_to_dict(folder) for folder in folders]


def user_profile_to_dict(user: UserProfile) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "bio": user.bio,
        "location": user.location,
        "url": user.url,
        "followers": user.followers,
        "following": user.following,
        "tweets": user.tweets,
        "likes": user.likes,
        "verified": user.verified,
        "profileImageUrl": user.profile_image_url,
        "createdAt": user.created_at,
    }


def users_to_data(users: Iterable[UserProfile]) -> list[dict[str, Any]]:
    return [user_profile_to_dict(user) for user in users]


def _exact_keys(
    value: dict[str, Any],
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{path} is missing fields: {', '.join(missing)}.")
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise ValueError(f"{path} has unknown fields: {', '.join(unknown)}.")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping.")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list.")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a string.")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean.")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} must be an integer.")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _integer(value, path)


def _media_type(value: Any, path: str) -> Literal["photo", "video", "animated_gif"]:
    media_type = _string(value, path)
    if media_type == "photo":
        return "photo"
    if media_type == "video":
        return "video"
    if media_type == "animated_gif":
        return "animated_gif"
    raise ValueError(f"{path} must be one of: animated_gif, photo, video.")
