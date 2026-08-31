"""Cookie authentication for Twitter/X."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)

_TWITTER_DOMAINS = {"x.com", "twitter.com", ".x.com", ".twitter.com"}
_KEYCHAIN_ERROR_KEYWORDS = (
    "key for cookie decryption",
    "safe storage",
    "keychain",
    "secretstorage",
)
_CHROMIUM_LOADERS = {"arc", "brave", "chrome", "chromium", "edge"}
_BROWSERS = {*_CHROMIUM_LOADERS, "firefox", "librewolf", "zen"}


@dataclass(frozen=True)
class CookieSource:
    """One browser cookie database and the browser-cookie3 loader it requires."""

    name: str
    loader: str
    cookie_file: Path | None = None
    key_file: Path | None = None


def _is_twitter_domain(domain: str) -> bool:
    return domain in _TWITTER_DOMAINS or domain.endswith((".x.com", ".twitter.com"))


def load_from_env() -> dict[str, str] | None:
    """Load an explicitly supplied cookie pair."""
    auth_token = os.environ.get("TWITTER_AUTH_TOKEN", "")
    ct0 = os.environ.get("TWITTER_CT0", "")
    if auth_token and ct0:
        return {"auth_token": auth_token, "ct0": ct0}
    if auth_token or ct0:
        raise AuthenticationError(
            "Set both TWITTER_AUTH_TOKEN and TWITTER_CT0, or unset both."
        )
    return None


def _extract_cookies_from_jar(
    jar: Iterable[Any],
    *,
    source: str,
) -> dict[str, str] | None:
    """Extract the complete Twitter cookie context from a browser jar."""
    cookies: dict[str, str] = {}
    for cookie in jar:
        if _is_twitter_domain(cookie.domain or "") and cookie.name and cookie.value:
            cookies[cookie.name] = cookie.value

    if "auth_token" not in cookies or "ct0" not in cookies:
        logger.debug(
            "%s has no usable Twitter session (auth_token=%s, ct0=%s)",
            source,
            "auth_token" in cookies,
            "ct0" in cookies,
        )
        return None

    return {
        "auth_token": cookies["auth_token"],
        "ct0": cookies["ct0"],
        "cookie_string": "; ".join(f"{name}={value}" for name, value in cookies.items()),
    }


def _firefox_sources(home: Path) -> list[CookieSource]:
    if sys.platform == "darwin":
        app_support = home / "Library/Application Support"
        roots = (
            ("zen", app_support / "zen/Profiles"),
            ("firefox", app_support / "Firefox/Profiles"),
            ("librewolf", app_support / "librewolf/Profiles"),
        )
    elif sys.platform == "win32":
        app_data_value = os.environ.get("APPDATA")
        if not app_data_value:
            return []
        app_data = Path(app_data_value)
        roots = (
            ("zen", app_data / "zen/Profiles"),
            ("firefox", app_data / "Mozilla/Firefox/Profiles"),
            ("librewolf", app_data / "librewolf/Profiles"),
        )
    else:
        roots = (
            ("zen", home / ".var/app/app.zen_browser.zen/.zen"),
            ("zen", home / ".zen"),
            ("firefox", home / ".mozilla/firefox"),
            ("firefox", home / "snap/firefox/common/.mozilla/firefox"),
            ("firefox", home / ".var/app/org.mozilla.firefox/.mozilla/firefox"),
            ("librewolf", home / ".librewolf"),
            ("librewolf", home / ".var/app/io.gitlab.librewolf-community/.librewolf"),
        )
    sources: list[CookieSource] = []
    for name, root in roots:
        if not root.is_dir():
            continue
        loader = "librewolf" if name == "librewolf" else "firefox"
        cookie_files = sorted(root.glob("*/cookies.sqlite"))
        if (root / "cookies.sqlite").is_file():
            cookie_files.insert(0, root / "cookies.sqlite")
        sources.extend(
            CookieSource(
                name=name,
                loader=loader,
                cookie_file=cookie_file,
            )
            for cookie_file in cookie_files
        )
    return sources


def _chromium_sources(home: Path) -> list[CookieSource]:
    if sys.platform == "darwin":
        app_support = home / "Library/Application Support"
        roots = (
            ("arc", "arc", app_support / "Arc/User Data"),
            ("chrome", "chrome", app_support / "Google/Chrome"),
            ("edge", "edge", app_support / "Microsoft Edge"),
            ("brave", "brave", app_support / "BraveSoftware/Brave-Browser"),
            ("chromium", "chromium", app_support / "Chromium"),
        )
    elif sys.platform == "win32":
        local_app_data_value = os.environ.get("LOCALAPPDATA")
        if not local_app_data_value:
            return []
        local_app_data = Path(local_app_data_value)
        roots = (
            ("chrome", "chrome", local_app_data / "Google/Chrome/User Data"),
            ("edge", "edge", local_app_data / "Microsoft/Edge/User Data"),
            ("brave", "brave", local_app_data / "BraveSoftware/Brave-Browser/User Data"),
            ("chromium", "chromium", local_app_data / "Chromium/User Data"),
        )
    else:
        config = home / ".config"
        roots = (
            ("chrome", "chrome", config / "google-chrome"),
            ("chrome", "chrome", config / "google-chrome-for-testing"),
            ("chromium", "chromium", config / "chromium"),
            ("brave", "brave", config / "BraveSoftware/Brave-Browser"),
            ("edge", "edge", config / "microsoft-edge"),
            (
                "chromium",
                "chromium",
                home / ".var/app/org.chromium.Chromium/config/chromium",
            ),
            (
                "chromium",
                "chromium",
                home / ".var/app/net.imput.helium/config/helium",
            ),
            (
                "brave",
                "brave",
                home / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
            ),
            (
                "chrome",
                "chrome",
                home / ".var/app/com.google.Chrome/config/google-chrome",
            ),
        )

    sources: list[CookieSource] = []
    for name, loader, root in roots:
        if not root.is_dir():
            continue
        key_file = root / "Local State"
        profile_dirs = [root / "Default", *sorted(root.glob("Profile *"))]
        for profile in profile_dirs:
            cookie_file = next(
                (
                    candidate
                    for candidate in (profile / "Network/Cookies", profile / "Cookies")
                    if candidate.is_file()
                ),
                None,
            )
            if cookie_file is not None:
                sources.append(
                    CookieSource(
                        name=name,
                        loader=loader,
                        cookie_file=cookie_file,
                        key_file=key_file if key_file.is_file() else None,
                    )
                )
    return sources


def _infer_chromium_loader(path: Path) -> str | None:
    normalized = str(path).lower().replace("\\", "/")
    markers = (
        ("brave", ("bravesoftware", "com.brave.browser")),
        ("edge", ("microsoft edge", "microsoft-edge", "com.microsoft.edge")),
        ("arc", ("/arc/", "thebrowser")),
        ("chrome", ("google/chrome", "google-chrome", "com.google.chrome")),
        ("chromium", ("chromium", "helium", "net.imput.helium")),
    )
    return next(
        (
            loader
            for loader, candidates in markers
            if any(candidate in normalized for candidate in candidates)
        ),
        None,
    )


def _explicit_source(path: Path, browser: str | None = None) -> CookieSource:
    if not path.is_file():
        raise AuthenticationError(f"TWITTER_COOKIE_FILE does not exist: {path}")
    if browser is not None and browser not in _BROWSERS:
        raise AuthenticationError(
            f"Unsupported TWITTER_BROWSER={browser!r}; choose from: "
            f"{', '.join(sorted(_BROWSERS))}."
        )
    if path.name == "cookies.sqlite":
        if browser in _CHROMIUM_LOADERS:
            raise AuthenticationError(
                f"TWITTER_BROWSER={browser!r} cannot read Firefox cookies.sqlite."
            )
        firefox_loader = "librewolf" if browser == "librewolf" else "firefox"
        return CookieSource(browser or "firefox", firefox_loader, cookie_file=path)
    if path.name == "Cookies":
        chromium_loader = browser or _infer_chromium_loader(path)
        if chromium_loader is None:
            raise AuthenticationError(
                "Cannot infer the Chromium-family browser from TWITTER_COOKIE_FILE; "
                "also set TWITTER_BROWSER=chrome|chromium|brave|edge|arc."
            )
        if chromium_loader not in _CHROMIUM_LOADERS:
            raise AuthenticationError(
                f"TWITTER_BROWSER={chromium_loader!r} cannot read Chromium Cookies."
            )
        key_file = path.parent.parent / "Local State"
        if path.parent.name == "Network":
            key_file = path.parent.parent.parent / "Local State"
        return CookieSource(
            chromium_loader,
            chromium_loader,
            cookie_file=path,
            key_file=key_file if key_file.is_file() else None,
        )
    raise AuthenticationError(
        "TWITTER_COOKIE_FILE must point to Firefox cookies.sqlite or Chromium Cookies."
    )


def _cookie_sources() -> list[CookieSource]:
    selected = os.environ.get("TWITTER_BROWSER", "").strip().lower() or None
    explicit = os.environ.get("TWITTER_COOKIE_FILE")
    if explicit:
        return [
            _explicit_source(
                Path(explicit).expanduser(),
                browser=selected,
            )
        ]

    home = Path.home()
    sources = [*_firefox_sources(home), *_chromium_sources(home)]
    if not selected:
        return sources

    supported = {source.name for source in sources}
    if selected not in supported:
        available = ", ".join(sorted(supported)) or "none"
        raise AuthenticationError(
            f"TWITTER_BROWSER={selected!r} is unavailable; discovered: {available}."
        )
    return [source for source in sources if source.name == selected]


def _diagnose_keychain_issues(diagnostics: list[str]) -> str | None:
    lowered = " ".join(diagnostics).lower()
    if not any(keyword in lowered for keyword in _KEYCHAIN_ERROR_KEYWORDS):
        return None
    is_ssh = any(
        os.environ.get(name)
        for name in ("SSH_CLIENT", "SSH_TTY", "SSH_CONNECTION")
    )
    if sys.platform == "darwin":
        if is_ssh:
            return (
                "macOS Keychain is locked. Run "
                "`security unlock-keychain ~/Library/Keychains/login.keychain-db`."
            )
        return "Allow your terminal to access the browser's Safe Storage key in Keychain."
    if sys.platform == "win32":
        return "Windows could not decrypt the browser cookie database."
    return "Unlock the desktop keyring before reading encrypted browser cookies."


def extract_from_browser() -> tuple[dict[str, str] | None, list[str]]:
    """Try each discovered browser profile exactly once."""
    try:
        import browser_cookie3
    except ImportError as exc:
        raise AuthenticationError("browser-cookie3 is not installed.") from exc

    diagnostics: list[str] = []
    sources = _cookie_sources()
    for source in sources:
        loader = getattr(browser_cookie3, source.loader, None)
        if loader is None:
            continue
        kwargs: dict[str, str] = {}
        if source.cookie_file is not None:
            kwargs["cookie_file"] = str(source.cookie_file)
        if source.key_file is not None:
            kwargs["key_file"] = str(source.key_file)
        label = f"{source.name}:{source.cookie_file}"
        try:
            jar = loader(**kwargs)
        except Exception as exc:
            diagnostics.append(f"{label}: {exc}")
            logger.debug("Cookie extraction failed for %s: %s", label, exc)
            continue
        cookies = _extract_cookies_from_jar(jar, source=label)
        if cookies:
            logger.info("Loaded Twitter cookies from %s", label)
            return cookies, diagnostics
    return None, diagnostics


def get_cookies() -> dict[str, str]:
    """Load explicit tokens or discover a local browser session."""
    cookies = load_from_env()
    if cookies:
        logger.info("Loaded cookies from environment variables")
        return cookies

    cookies, diagnostics = extract_from_browser()
    if cookies:
        return cookies

    lines = [
        "No Twitter cookies found.",
        "Log into x.com in Zen, Firefox, LibreWolf, Chrome, Chromium, Brave, Edge, or Arc.",
        "For a custom profile, set TWITTER_COOKIE_FILE to its cookies database.",
    ]
    hint = _diagnose_keychain_issues(diagnostics)
    if hint:
        lines.extend(("", hint))
    lines.extend(("", "Run `twitter -v <command>` for profile diagnostics."))
    raise AuthenticationError("\n".join(lines))
