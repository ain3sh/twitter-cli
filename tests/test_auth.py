"""Tests for browser cookie discovery and extraction."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from twitter_cli import auth
from twitter_cli.exceptions import AuthenticationError


class Cookie:
    def __init__(self, domain: str, name: str, value: str) -> None:
        self.domain = domain
        self.name = name
        self.value = value


def test_load_from_env_requires_complete_pair(monkeypatch) -> None:
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "token")
    monkeypatch.delenv("TWITTER_CT0", raising=False)

    with pytest.raises(AuthenticationError, match="Set both"):
        auth.load_from_env()


def test_load_from_env_returns_complete_pair(monkeypatch) -> None:
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWITTER_CT0", "csrf")

    assert auth.load_from_env() == {"auth_token": "token", "ct0": "csrf"}


def test_extract_cookies_forwards_full_twitter_context() -> None:
    jar = [
        Cookie(".x.com", "auth_token", "token"),
        Cookie(".x.com", "ct0", "csrf"),
        Cookie(".x.com", "lang", "en"),
        Cookie(".example.com", "ignored", "value"),
    ]

    cookies = auth._extract_cookies_from_jar(jar, source="test")

    assert cookies == {
        "auth_token": "token",
        "ct0": "csrf",
        "cookie_string": "auth_token=token; ct0=csrf; lang=en",
    }


def test_firefox_sources_discover_zen_flatpak(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    profile = tmp_path / ".var/app/app.zen_browser.zen/.zen/profile.default"
    profile.mkdir(parents=True)
    (profile / "cookies.sqlite").touch()

    sources = auth._firefox_sources(tmp_path)

    assert sources == [
        auth.CookieSource(
            name="zen",
            loader="firefox",
            cookie_file=profile / "cookies.sqlite",
        )
    ]


def test_firefox_sources_discover_zen_on_macos(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    profile = tmp_path / "Library/Application Support/zen/Profiles/profile.default"
    profile.mkdir(parents=True)
    (profile / "cookies.sqlite").touch()

    assert auth._firefox_sources(tmp_path) == [
        auth.CookieSource(
            name="zen",
            loader="firefox",
            cookie_file=profile / "cookies.sqlite",
        )
    ]


def test_firefox_sources_discover_firefox_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    profile = tmp_path / "Mozilla/Firefox/Profiles/profile.default"
    profile.mkdir(parents=True)
    (profile / "cookies.sqlite").touch()

    assert auth._firefox_sources(tmp_path / "home") == [
        auth.CookieSource(
            name="firefox",
            loader="firefox",
            cookie_file=profile / "cookies.sqlite",
        )
    ]


def test_chromium_sources_discover_network_cookie_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    profile = tmp_path / ".config/chromium/Default"
    (profile / "Network").mkdir(parents=True)
    (profile / "Network/Cookies").touch()
    (tmp_path / ".config/chromium/Local State").touch()

    sources = auth._chromium_sources(tmp_path)

    assert sources == [
        auth.CookieSource(
            name="chromium",
            loader="chromium",
            cookie_file=profile / "Network/Cookies",
            key_file=tmp_path / ".config/chromium/Local State",
        )
    ]


def test_explicit_source_accepts_firefox_cookie_database(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.sqlite"
    cookie_file.touch()

    assert auth._explicit_source(cookie_file) == auth.CookieSource(
        name="firefox",
        loader="firefox",
        cookie_file=cookie_file,
    )


def test_explicit_source_infers_brave_loader(tmp_path: Path) -> None:
    root = tmp_path / "BraveSoftware/Brave-Browser"
    cookie_file = root / "Default/Network/Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.touch()
    (root / "Local State").touch()

    assert auth._explicit_source(cookie_file) == auth.CookieSource(
        name="brave",
        loader="brave",
        cookie_file=cookie_file,
        key_file=root / "Local State",
    )


def test_explicit_source_requires_browser_for_ambiguous_chromium_file(
    tmp_path: Path,
) -> None:
    cookie_file = tmp_path / "Default/Network/Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.touch()

    with pytest.raises(AuthenticationError, match="also set TWITTER_BROWSER"):
        auth._explicit_source(cookie_file)


def test_explicit_source_rejects_unknown_file(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.db"
    cookie_file.touch()

    with pytest.raises(AuthenticationError, match="must point"):
        auth._explicit_source(cookie_file)


def test_cookie_sources_prioritize_explicit_file(monkeypatch, tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.sqlite"
    cookie_file.touch()
    monkeypatch.setenv("TWITTER_COOKIE_FILE", str(cookie_file))

    assert auth._cookie_sources() == [
        auth.CookieSource("firefox", "firefox", cookie_file=cookie_file)
    ]


def test_cookie_sources_uses_selected_loader_for_explicit_chromium_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "browser"
    cookie_file = root / "Default/Network/Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.touch()
    (root / "Local State").touch()
    monkeypatch.setenv("TWITTER_COOKIE_FILE", str(cookie_file))
    monkeypatch.setenv("TWITTER_BROWSER", "chrome")

    assert auth._cookie_sources() == [
        auth.CookieSource(
            "chrome",
            "chrome",
            cookie_file=cookie_file,
            key_file=root / "Local State",
        )
    ]


def test_extract_from_browser_uses_discovered_zen_profile(monkeypatch, tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.sqlite"
    source = auth.CookieSource("zen", "firefox", cookie_file=cookie_file)
    calls = []

    def firefox(**kwargs):
        calls.append(kwargs)
        return [
            Cookie(".x.com", "auth_token", "token"),
            Cookie(".x.com", "ct0", "csrf"),
        ]

    monkeypatch.setattr(auth, "_cookie_sources", lambda: [source])
    monkeypatch.setitem(sys.modules, "browser_cookie3", SimpleNamespace(firefox=firefox))

    cookies, diagnostics = auth.extract_from_browser()

    assert diagnostics == []
    assert cookies is not None
    assert cookies["auth_token"] == "token"
    assert calls == [{"cookie_file": str(cookie_file)}]


def test_get_cookies_returns_browser_session_without_preflight(monkeypatch) -> None:
    expected = {
        "auth_token": "token",
        "ct0": "csrf",
        "cookie_string": "auth_token=token; ct0=csrf",
    }
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    monkeypatch.setattr(auth, "extract_from_browser", lambda: (expected, []))

    assert auth.get_cookies() == expected


def test_get_cookies_reports_custom_profile_option(monkeypatch) -> None:
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    monkeypatch.setattr(auth, "extract_from_browser", lambda: (None, []))

    with pytest.raises(AuthenticationError, match="TWITTER_COOKIE_FILE"):
        auth.get_cookies()


def test_diagnose_keychain_issues_linux(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    hint = auth._diagnose_keychain_issues(["Unable to get key for cookie decryption"])
    assert hint == "Unlock the desktop keyring before reading encrypted browser cookies."
