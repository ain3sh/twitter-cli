from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from twitter_cli.cli import cli
from twitter_cli.formatter import article_to_markdown
from twitter_cli.models import BookmarkFolder, Timeline, UserProfile
from twitter_cli.output import render_success
from twitter_cli.serialization import tweets_to_data


def _config() -> dict:
    return {
        "fetch": {"count": 20},
        "filter": {
            "lang": [],
            "excludeRetweets": False,
            "minScore": None,
            "limit": None,
            "weights": {},
        },
        "rateLimit": {},
    }


def _install_client(monkeypatch, client) -> None:
    monkeypatch.setattr("twitter_cli.cli._config", _config)
    monkeypatch.setattr("twitter_cli.cli._client", lambda config, output_format: client)


def test_help_exposes_only_the_canonical_command_vocabulary() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    command_help = result.output.split("Commands:\n", 1)[1]
    command_names = {
        line.split()[0]
        for line in command_help.splitlines()
        if line.startswith("  ") and line.strip() and not line.lstrip().startswith("-")
    }
    assert command_names == {
        "article",
        "bookmark",
        "bookmark-folders",
        "bookmarks",
        "delete",
        "feed",
        "filter",
        "follow",
        "like",
        "list",
        "post",
        "retweet",
        "search",
        "tweet",
        "unbookmark",
        "unfollow",
        "unlike",
        "unretweet",
        "user",
    }


def test_feed_defaults_to_yaml_and_preserves_cursor(monkeypatch, tweet_factory) -> None:
    class FakeClient:
        def fetch_home_timeline(self, count, include_promoted, cursor):
            assert (count, include_promoted, cursor) == (3, True, "cursor-1")
            return Timeline([tweet_factory("1", is_promoted=True)], "cursor-2")

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(
        cli,
        ["feed", "--max", "3", "--cursor", "cursor-1", "--include-promoted"],
    )

    assert result.exit_code == 0
    payload = yaml.safe_load(result.output)
    assert payload["schemaVersion"] == "1"
    assert payload["data"][0]["id"] == "1"
    assert payload["pagination"] == {"nextCursor": "cursor-2"}


def test_bookmarks_reads_timeline(monkeypatch, tweet_factory) -> None:
    class FakeClient:
        def fetch_bookmarks(self, count):
            assert count == 2
            return Timeline([tweet_factory("1"), tweet_factory("2")])

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["bookmarks", "--max", "2", "--format", "json"])

    assert result.exit_code == 0
    assert [tweet["id"] for tweet in yaml.safe_load(result.output)["data"]] == ["1", "2"]


def test_bookmark_folders_has_one_optional_resource_identifier(monkeypatch, tweet_factory) -> None:
    class FakeClient:
        def fetch_bookmark_folders(self):
            return [BookmarkFolder("f1", "Reading")]

        def fetch_bookmark_folder_timeline(self, folder_id, count):
            assert (folder_id, count) == ("f1", 4)
            return Timeline([tweet_factory("4")])

    _install_client(monkeypatch, FakeClient())
    runner = CliRunner()

    folders = yaml.safe_load(runner.invoke(cli, ["bookmark-folders"]).output)
    timeline = yaml.safe_load(runner.invoke(cli, ["bookmark-folders", "f1", "--max", "4"]).output)

    assert folders["data"] == [{"id": "f1", "name": "Reading"}]
    assert timeline["data"][0]["id"] == "4"


def test_search_forwards_native_query_unchanged(monkeypatch, tweet_factory) -> None:
    query = "from:alice lang:en min_faves:10"

    class FakeClient:
        def fetch_search(self, received_query, count, product):
            assert (received_query, count, product) == (query, 5, "Latest")
            return Timeline([tweet_factory("1")])

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["search", query, "--type", "Latest", "--max", "5"])

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["data"][0]["id"] == "1"


def test_user_without_username_emits_current_profile_directly(monkeypatch) -> None:
    class FakeClient:
        def fetch_me(self):
            return UserProfile(id="42", name="Alice", username="alice")

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["user"])

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["data"]["username"] == "alice"
    assert "authenticated" not in result.output


def test_user_relation_uses_one_resource_grammar(monkeypatch, tweet_factory) -> None:
    class FakeClient:
        def fetch_user(self, username):
            assert username == "alice"
            return UserProfile(id="42", name="Alice", username="alice")

        def fetch_user_tweets(self, user_id, count):
            assert (user_id, count) == ("42", 6)
            return Timeline([tweet_factory("6")])

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["user", "@alice", "posts", "--max", "6"])

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["data"][0]["id"] == "6"


def test_tweet_commands_share_url_identifier_parsing(monkeypatch, tweet_factory) -> None:
    calls = []

    class FakeClient:
        def fetch_tweet_detail(self, tweet_id, count):
            calls.append((tweet_id, count))
            return Timeline([tweet_factory(tweet_id)])

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["tweet", "https://x.com/alice/status/123?s=20"])

    assert result.exit_code == 0
    assert calls == [("123", 20)]


def test_filter_reads_canonical_envelope_without_a_client(monkeypatch, tmp_path, tweet_factory) -> None:
    input_path = tmp_path / "timeline.yaml"
    input_path.write_text(
        render_success(tweets_to_data([tweet_factory("1")]), "yaml"),
        encoding="utf-8",
    )
    monkeypatch.setattr("twitter_cli.cli._config", _config)
    monkeypatch.setattr(
        "twitter_cli.cli._client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )

    result = CliRunner().invoke(cli, ["filter", str(input_path)])

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["data"][0]["id"] == "1"


def test_filter_reports_invalid_input_as_a_structured_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("not: a timeline", encoding="utf-8")
    monkeypatch.setattr("twitter_cli.cli._config", _config)

    result = CliRunner().invoke(cli, ["filter", str(path)])

    assert result.exit_code == 1
    payload = yaml.safe_load(result.output)
    assert payload["error"]["code"] == "invalid_input"


def test_article_markdown_is_an_output_format(monkeypatch, tweet_factory) -> None:
    article = tweet_factory("88", article_title="Title", article_text="Body")

    class FakeClient:
        def fetch_article(self, tweet_id):
            assert tweet_id == "88"
            return article

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["article", "88", "--format", "markdown"])

    assert result.exit_code == 0
    assert result.output == article_to_markdown(article)


def test_post_composes_reply_and_quote_through_one_command(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def create_tweet(self, text, reply_to_id=None, media_ids=None):
            calls.append(("reply", text, reply_to_id, media_ids))
            return "new-reply"

        def quote_tweet(self, tweet_id, text, media_ids=None):
            calls.append(("quote", text, tweet_id, media_ids))
            return "new-quote"

    _install_client(monkeypatch, FakeClient())
    runner = CliRunner()

    reply = runner.invoke(cli, ["post", "hello", "--reply-to", "https://x.com/a/status/12"])
    quote = runner.invoke(cli, ["post", "hello", "--quote", "13"])

    assert yaml.safe_load(reply.output)["data"] == {"id": "new-reply"}
    assert yaml.safe_load(quote.output)["data"] == {"id": "new-quote"}
    assert calls == [
        ("reply", "hello", "12", None),
        ("quote", "hello", "13", None),
    ]


def test_post_rejects_two_parent_states() -> None:
    result = CliRunner().invoke(cli, ["post", "hello", "--reply-to", "1", "--quote", "2"])

    assert result.exit_code == 2
    assert "Use only one" in result.output


def test_mutations_use_the_same_tweet_identifier_parser(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def like_tweet(self, tweet_id):
            calls.append(tweet_id)
            return True

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["like", "https://twitter.com/alice/status/123"])

    assert result.exit_code == 0
    assert calls == ["123"]
    assert yaml.safe_load(result.output)["data"] == {"id": "123"}


def test_follow_results_contain_only_the_affected_identifier(monkeypatch) -> None:
    class FakeClient:
        def fetch_user(self, username):
            assert username == "alice"
            return UserProfile(id="42", name="Alice", username="alice")

        def follow_user(self, user_id):
            assert user_id == "42"
            return True

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["follow", "@alice"])

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["data"] == {"id": "42"}


def test_rich_result_uses_stdout(monkeypatch, tweet_factory) -> None:
    class FakeClient:
        def fetch_bookmarks(self, count):
            return Timeline([tweet_factory("1")])

    _install_client(monkeypatch, FakeClient())

    result = CliRunner().invoke(cli, ["bookmarks", "--format", "rich"])

    assert result.exit_code == 0
    assert "Bookmarks" in result.stdout
    assert "alice" in result.stdout


def test_invalid_xdg_config_uses_the_envelope(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "twitter-cli" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text("unknown: true\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = CliRunner().invoke(cli, ["bookmarks"])

    assert result.exit_code == 1
    assert yaml.safe_load(result.output)["error"]["code"] == "invalid_input"
