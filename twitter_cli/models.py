"""Canonical runtime models for twitter-cli."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Author:
    id: str
    name: str
    username: str
    profile_image_url: str = ""
    verified: bool = False


@dataclass
class Metrics:
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    views: int = 0
    bookmarks: int = 0


@dataclass
class TweetMedia:
    type: Literal["photo", "video", "animated_gif"]
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class Tweet:
    id: str
    text: str
    author: Author
    metrics: Metrics
    created_at: str
    media: list[TweetMedia] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    is_retweet: bool = False
    lang: str = ""
    retweeted_by: Optional[str] = None
    quoted_tweet: Optional[Tweet] = None
    score: Optional[float] = None
    article_title: Optional[str] = None
    article_text: Optional[str] = None
    is_subscriber_only: bool = False
    is_promoted: bool = False


@dataclass
class Timeline:
    tweets: list[Tweet]
    next_cursor: Optional[str] = None


@dataclass
class BookmarkFolder:
    id: str
    name: str


@dataclass
class UserProfile:
    id: str
    name: str
    username: str
    bio: str = ""
    location: str = ""
    url: str = ""
    followers: int = 0
    following: int = 0
    tweets: int = 0
    likes: int = 0
    verified: bool = False
    profile_image_url: str = ""
    created_at: str = ""
