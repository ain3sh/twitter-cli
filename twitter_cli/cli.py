"""Canonical Click command graph for twitter-cli."""

from __future__ import annotations

import logging
import re
import sys
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import click

from . import __version__
from .auth import get_cookies
from .client import TwitterClient
from .config import load_config
from .exceptions import InvalidInputError, TwitterError
from .filter import filter_tweets
from .formatter import (
    article_to_markdown,
    print_article,
    print_tweet_detail,
    print_tweet_table,
    print_user_profile,
    print_user_table,
)
from .models import Timeline
from .output import (
    emit_error,
    emit_success,
    ensure_utf8_streams,
    output_option,
    resolve_output_format,
    use_rich_output,
)
from .serialization import (
    bookmark_folders_to_data,
    timeline_from_structured,
    tweet_to_dict,
    tweets_to_data,
    user_profile_to_dict,
    users_to_data,
)

FEED_TYPES = ("for-you", "following")
SEARCH_PRODUCTS = ("Top", "Latest", "Photos", "Videos")
USER_RELATIONS = ("posts", "likes", "followers", "following")
_MAX_IMAGES = 4

if TYPE_CHECKING:
    from rich.console import Console


def _console(*, stderr: bool) -> Console:
    from rich.console import Console

    return Console(stderr=stderr)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _error_code(exc: Exception) -> str:
    return getattr(exc, "error_code", "api_error")


def _fail(exc: Exception, output_format: str | None = None) -> None:
    if emit_error(_error_code(exc), str(exc), output_format=output_format):
        raise SystemExit(1) from None
    _console(stderr=True).print(f"[red]{exc}[/red]")
    raise SystemExit(1) from None


def _guard(action: Callable[[], None], output_format: str | None = None) -> None:
    try:
        action()
    except (TwitterError, RuntimeError) as exc:
        _fail(exc, output_format)


def _config() -> dict[str, Any]:
    try:
        return load_config()
    except TwitterError as exc:
        _fail(exc)
    raise AssertionError("unreachable")


def _client(config: dict[str, Any], output_format: str | None) -> TwitterClient:
    if use_rich_output(output_format):
        _console(stderr=True).print("Reading browser session...")
    cookies = get_cookies()
    return TwitterClient(
        cookies["auth_token"],
        cookies["ct0"],
        config.get("rateLimit"),
        cookie_string=cookies.get("cookie_string"),
    )


def _fetch_count(config: dict[str, Any], maximum: int | None) -> int:
    return maximum if maximum is not None else config["fetch"]["count"]


def _tweet_id(value: str) -> str:
    raw = value.strip()
    if raw.isdigit():
        return raw

    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
    }:
        raise InvalidInputError(f"Invalid tweet ID or URL: {value}")

    match = re.fullmatch(r"/(?:[^/]+/)?(?:status|article)/(\d+)/?", parsed.path)
    if not match:
        raise InvalidInputError(f"Invalid tweet ID or URL: {value}")
    return match.group(1)


def _username(value: str) -> str:
    username = value.strip().lstrip("@")
    if not username:
        raise InvalidInputError("Username is required.")
    return username


def _pagination(timeline: Timeline) -> dict[str, str] | None:
    return {"nextCursor": timeline.next_cursor} if timeline.next_cursor else None


def _emit_timeline(timeline: Timeline, output_format: str | None, *, title: str) -> None:
    data = tweets_to_data(timeline.tweets)
    if emit_success(data, output_format, pagination=_pagination(timeline)):
        return
    print_tweet_table(timeline.tweets, _console(stderr=False), title=title)


def _emit_tweet_timeline(timeline: Timeline, output_format: str | None) -> None:
    if emit_success(tweets_to_data(timeline.tweets), output_format):
        return
    if timeline.tweets:
        console = _console(stderr=False)
        print_tweet_detail(timeline.tweets[0], console)
        if len(timeline.tweets) > 1:
            print_tweet_table(
                timeline.tweets[1:],
                console,
                title=f"Replies - {len(timeline.tweets) - 1}",
            )


def _run_timeline(
    fetch: Callable[[TwitterClient, int], Timeline],
    *,
    maximum: int | None,
    output_format: str | None,
    title: str,
) -> None:
    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        timeline = fetch(client, _fetch_count(config, maximum))
        _emit_timeline(timeline, output_format, title=f"{title} - {len(timeline.tweets)}")

    _guard(run, output_format)


def _upload_images(client: TwitterClient, paths: tuple[str, ...], *, rich: bool) -> list[str]:
    if len(paths) > _MAX_IMAGES:
        raise InvalidInputError(f"At most {_MAX_IMAGES} images may be attached.")
    media_ids = []
    for path in paths:
        if rich:
            _console(stderr=True).print(f"Uploading {path}...")
        media_ids.append(client.upload_media(path))
    return media_ids


def _run_write(
    operation: Callable[[TwitterClient], str],
    *,
    output_format: str | None,
    message: str,
) -> None:
    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        affected_id = operation(client)
        if emit_success({"id": affected_id}, output_format):
            return
        _console(stderr=False).print(f"[green]{message}[/green]")

    _guard(run, output_format)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.version_option(version=__version__)
def cli(verbose: bool) -> None:
    """twitter - Twitter/X from the terminal."""
    ensure_utf8_streams()
    _setup_logging(verbose)


@cli.command()
@click.option("--type", "feed_type", type=click.Choice(FEED_TYPES), default="for-you")
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@click.option("--cursor", default=None, help="Continue from a previous nextCursor.")
@click.option("--include-promoted", is_flag=True, help="Include promoted tweets when available.")
@output_option
def feed(
    feed_type: str,
    maximum: int | None,
    cursor: str | None,
    include_promoted: bool,
    output_format: str | None,
) -> None:
    """Read the home feed."""

    def fetch(client: TwitterClient, count: int) -> Timeline:
        if feed_type == "following":
            return client.fetch_following_feed(count, include_promoted, cursor)
        return client.fetch_home_timeline(count, include_promoted, cursor)

    title = "Following" if feed_type == "following" else "For You"
    _run_timeline(fetch, maximum=maximum, output_format=output_format, title=title)


@cli.command()
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@output_option
def bookmarks(maximum: int | None, output_format: str | None) -> None:
    """Read bookmarked tweets."""
    _run_timeline(
        lambda client, count: client.fetch_bookmarks(count),
        maximum=maximum,
        output_format=output_format,
        title="Bookmarks",
    )


@cli.command("bookmark-folders")
@click.argument("folder_id", required=False)
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@output_option
def bookmark_folders(
    folder_id: str | None,
    maximum: int | None,
    output_format: str | None,
) -> None:
    """List bookmark folders, or read one folder by ID."""
    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        if folder_id is not None:
            timeline = client.fetch_bookmark_folder_timeline(
                folder_id,
                _fetch_count(config, maximum),
            )
            _emit_timeline(
                timeline,
                output_format,
                title=f"Bookmark folder {folder_id} - {len(timeline.tweets)}",
            )
            return
        if maximum is not None:
            raise InvalidInputError("--max requires FOLDER_ID.")
        folders = client.fetch_bookmark_folders()
        if emit_success(bookmark_folders_to_data(folders), output_format):
            return
        from rich.table import Table

        table = Table(title=f"Bookmark folders - {len(folders)}")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        for folder in folders:
            table.add_row(folder.id, folder.name)
        _console(stderr=False).print(table)

    _guard(run, output_format)


@cli.command()
@click.argument("query")
@click.option(
    "--type",
    "product",
    type=click.Choice(SEARCH_PRODUCTS, case_sensitive=False),
    default="Top",
)
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@output_option
def search(query: str, product: str, maximum: int | None, output_format: str | None) -> None:
    """Search with Twitter's native query grammar."""
    if not query.strip():
        raise click.UsageError("QUERY must not be empty.")
    _run_timeline(
        lambda client, count: client.fetch_search(query, count, product),
        maximum=maximum,
        output_format=output_format,
        title=f"Search: {query}",
    )


@cli.command()
@click.argument("username", required=False)
@click.argument("relation", required=False, type=click.Choice(USER_RELATIONS))
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@output_option
def user(
    username: str | None,
    relation: str | None,
    maximum: int | None,
    output_format: str | None,
) -> None:
    """Read a user profile or one of its relations."""
    if relation is not None and username is None:
        raise click.UsageError("RELATION requires USERNAME.")
    if relation is None and maximum is not None:
        raise click.UsageError("--max requires RELATION.")

    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        profile = client.fetch_me() if username is None else client.fetch_user(_username(username))
        if relation is None:
            data = user_profile_to_dict(profile)
            if emit_success(data, output_format):
                return
            print_user_profile(profile, _console(stderr=False))
            return

        count = _fetch_count(config, maximum)
        if relation == "posts":
            timeline = client.fetch_user_tweets(profile.id, count)
            _emit_timeline(
                timeline,
                output_format,
                title=f"@{profile.username} posts - {len(timeline.tweets)}",
            )
            return
        if relation == "likes":
            timeline = client.fetch_user_likes(profile.id, count)
            _emit_timeline(
                timeline,
                output_format,
                title=f"@{profile.username} likes - {len(timeline.tweets)}",
            )
            return

        users = (
            client.fetch_followers(profile.id, count)
            if relation == "followers"
            else client.fetch_following(profile.id, count)
        )
        if emit_success(users_to_data(users), output_format):
            return
        print_user_table(
            users,
            _console(stderr=False),
            title=f"@{profile.username} {relation} - {len(users)}",
        )

    _guard(run, output_format)


@cli.command()
@click.argument("tweet_id")
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@output_option
def tweet(tweet_id: str, maximum: int | None, output_format: str | None) -> None:
    """Read a tweet and its replies."""
    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        timeline = client.fetch_tweet_detail(_tweet_id(tweet_id), _fetch_count(config, maximum))
        _emit_tweet_timeline(timeline, output_format)

    _guard(run, output_format)


@cli.command()
@click.argument("tweet_id")
@output_option(markdown=True)
def article(tweet_id: str, output_format: str | None) -> None:
    """Read a Twitter Article."""
    config = _config()

    def run() -> None:
        client = _client(config, output_format)
        article_tweet = client.fetch_article(_tweet_id(tweet_id))
        if resolve_output_format(output_format) == "markdown":
            click.echo(article_to_markdown(article_tweet), nl=False)
            return
        if emit_success(tweet_to_dict(article_tweet), output_format):
            return
        print_article(article_tweet, _console(stderr=False))

    _guard(run, output_format)


@cli.command("list")
@click.argument("list_id")
@click.option("--max", "maximum", type=click.IntRange(min=1), default=None)
@click.option("--cursor", default=None, help="Continue from a previous nextCursor.")
@output_option
def list_timeline(
    list_id: str,
    maximum: int | None,
    cursor: str | None,
    output_format: str | None,
) -> None:
    """Read tweets from a Twitter List."""
    _run_timeline(
        lambda client, count: client.fetch_list_timeline(list_id, count, cursor),
        maximum=maximum,
        output_format=output_format,
        title=f"List {list_id}",
    )


@cli.command("filter")
@click.argument("input_file", required=False, default="-")
@output_option
def filter_command(input_file: str, output_format: str | None) -> None:
    """Filter and rank a timeline envelope from FILE or stdin."""
    config = _config()

    def run() -> None:
        if input_file == "-":
            if sys.stdin.isatty():
                raise InvalidInputError("Provide FILE or pipe a timeline envelope to stdin.")
            raw = sys.stdin.read()
        else:
            try:
                raw = Path(input_file).read_text(encoding="utf-8")
            except OSError as exc:
                raise InvalidInputError(f"Failed to read {input_file}: {exc}") from exc
        try:
            timeline = timeline_from_structured(raw)
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
        filtered = Timeline(
            filter_tweets(timeline.tweets, config["filter"]),
            timeline.next_cursor,
        )
        _emit_timeline(
            filtered,
            output_format,
            title=f"Filtered tweets - {len(filtered.tweets)}",
        )

    _guard(run, output_format)


@cli.command()
@click.argument("text")
@click.option("--reply-to", default=None, help="Reply to this tweet ID or URL.")
@click.option("--quote", "quote_id", default=None, help="Quote this tweet ID or URL.")
@click.option(
    "--image",
    "images",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Attach an image. Repeatable up to four times.",
)
@output_option
def post(
    text: str,
    reply_to: str | None,
    quote_id: str | None,
    images: tuple[str, ...],
    output_format: str | None,
) -> None:
    """Create a post, reply, or quote."""
    if reply_to and quote_id:
        raise click.UsageError("Use only one of --reply-to or --quote.")
    rich = use_rich_output(output_format)

    def operation(client: TwitterClient) -> str:
        media_ids = _upload_images(client, images, rich=rich)
        if quote_id:
            return client.quote_tweet(_tweet_id(quote_id), text, media_ids or None)
        return client.create_tweet(
            text,
            reply_to_id=_tweet_id(reply_to) if reply_to else None,
            media_ids=media_ids or None,
        )

    _run_write(operation, output_format=output_format, message="Post created.")


def _tweet_action(
    value: str,
    output_format: str | None,
    method: Callable[[TwitterClient, str], bool],
    message: str,
) -> None:
    tweet_id = _tweet_id(value)

    def operation(client: TwitterClient) -> str:
        method(client, tweet_id)
        return tweet_id

    _run_write(operation, output_format=output_format, message=message)


@cli.command("delete")
@click.argument("tweet_id")
@output_option
def delete_tweet(tweet_id: str, output_format: str | None) -> None:
    """Delete a tweet."""
    _tweet_action(tweet_id, output_format, lambda client, value: client.delete_tweet(value), "Tweet deleted.")


@cli.command()
@click.argument("tweet_id")
@output_option
def like(tweet_id: str, output_format: str | None) -> None:
    """Like a tweet."""
    _tweet_action(tweet_id, output_format, lambda client, value: client.like_tweet(value), "Tweet liked.")


@cli.command()
@click.argument("tweet_id")
@output_option
def unlike(tweet_id: str, output_format: str | None) -> None:
    """Unlike a tweet."""
    _tweet_action(tweet_id, output_format, lambda client, value: client.unlike_tweet(value), "Tweet unliked.")


@cli.command()
@click.argument("tweet_id")
@output_option
def retweet(tweet_id: str, output_format: str | None) -> None:
    """Retweet a tweet."""
    _tweet_action(tweet_id, output_format, lambda client, value: client.retweet(value), "Tweet retweeted.")


@cli.command()
@click.argument("tweet_id")
@output_option
def unretweet(tweet_id: str, output_format: str | None) -> None:
    """Undo a retweet."""
    _tweet_action(tweet_id, output_format, lambda client, value: client.unretweet(value), "Retweet removed.")


@cli.command()
@click.argument("tweet_id")
@output_option
def bookmark(tweet_id: str, output_format: str | None) -> None:
    """Bookmark a tweet."""
    _tweet_action(
        tweet_id,
        output_format,
        lambda client, value: client.bookmark_tweet(value),
        "Tweet bookmarked.",
    )


@cli.command()
@click.argument("tweet_id")
@output_option
def unbookmark(tweet_id: str, output_format: str | None) -> None:
    """Remove a tweet bookmark."""
    _tweet_action(
        tweet_id,
        output_format,
        lambda client, value: client.unbookmark_tweet(value),
        "Bookmark removed.",
    )


def _follow_action(
    value: str,
    output_format: str | None,
    method: Callable[[TwitterClient, str], bool],
    message: str,
) -> None:
    username = _username(value)

    def operation(client: TwitterClient) -> str:
        user_id = client.fetch_user(username).id
        method(client, user_id)
        return user_id

    _run_write(operation, output_format=output_format, message=message)


@cli.command()
@click.argument("username")
@output_option
def follow(username: str, output_format: str | None) -> None:
    """Follow a user."""
    _follow_action(
        username,
        output_format,
        lambda client, value: client.follow_user(value),
        "User followed.",
    )


@cli.command()
@click.argument("username")
@output_option
def unfollow(username: str, output_format: str | None) -> None:
    """Unfollow a user."""
    _follow_action(
        username,
        output_format,
        lambda client, value: client.unfollow_user(value),
        "User unfollowed.",
    )


if __name__ == "__main__":
    cli()
