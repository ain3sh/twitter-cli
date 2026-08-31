# twitter-cli

A terminal-first Twitter/X client for timelines, search, profiles, bookmarks, articles,
and account actions. It authenticates with an existing browser session instead of an API key.

## Install

```bash
git clone https://github.com/ain3sh/twitter-cli ~/projects/twitter-cli
uv tool install --editable ~/projects/twitter-cli
```

Reinstall after dependency or entrypoint changes:

```bash
uv tool install --editable --force ~/projects/twitter-cli
```

Install the companion agent skill with a symlink so it follows repository updates:

```bash
ln -s ~/projects/twitter-cli/.agents/skills/twitter-cli \
  ~/.agents/skills/twitter-cli
```

## Authentication

The CLI discovers logged-in profiles for Zen, Firefox, LibreWolf, Chrome, Chromium, Brave,
Edge, Arc, Helium, and their common Flatpak or Snap variants. The browser does not need to
be running.

Verify the current account:

```bash
twitter user
```

For a custom cookie database:

```bash
TWITTER_COOKIE_FILE="$HOME/path/to/cookies.sqlite" twitter user
TWITTER_BROWSER=brave \
  TWITTER_COOKIE_FILE="$HOME/path/to/Network/Cookies" \
  twitter user
```

Explicit tokens remain available for headless environments:

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
```

Browser extraction is preferable because it forwards the complete Twitter cookie context.

## Output

YAML is the default. JSON and Rich terminal output use the same command data:

```bash
twitter bookmarks --max 10
twitter bookmarks --max 10 --format json
twitter bookmarks --max 10 --format rich
```

Structured output uses the envelope in [SCHEMA.md](./SCHEMA.md). Redirect stdout to save it:

```bash
twitter feed --max 20 > feed.yaml
twitter feed --max 20 --format json > feed.json
```

Article commands also support Markdown:

```bash
twitter article <tweet-id-or-url> --format markdown
```

## Read commands

```bash
# Current or named user
twitter user
twitter user <username>

# User relations
twitter user <username> posts --max 20
twitter user <username> likes --max 20
twitter user <username> followers --max 20
twitter user <username> following --max 20

# Timelines
twitter feed
twitter feed --type following
twitter feed --max 20 --cursor '<next-cursor>'
twitter bookmarks --max 20
twitter bookmark-folders
twitter bookmark-folders <folder-id> --max 20
twitter list <list-id> --max 20 --cursor '<next-cursor>'

# Search uses Twitter's native query grammar
twitter search 'Claude Code' --max 20
twitter search 'from:bbc lang:en -filter:retweets' --type Latest --max 20

# Individual content
twitter tweet <tweet-id-or-url> --max 20
twitter article <tweet-id-or-url>
```

## Local filtering

`filter` consumes a canonical timeline envelope from a file or stdin. It never authenticates
or performs a network request.

```bash
twitter feed --max 100 | twitter filter
twitter filter feed.yaml --format rich
```

Filtering always scores and sorts tweets. Optional configuration fields compose additional
language, retweet, minimum-score, and result-limit constraints.

## Write commands

Write commands act on the authenticated account:

```bash
# One post grammar
twitter post 'Hello'
twitter post 'Nice' --reply-to <tweet-id-or-url>
twitter post 'Worth reading' --quote <tweet-id-or-url>
twitter post 'Gallery' --image one.png --image two.jpg

# Tweet actions
twitter delete <tweet-id-or-url>
twitter like <tweet-id-or-url>
twitter unlike <tweet-id-or-url>
twitter retweet <tweet-id-or-url>
twitter unretweet <tweet-id-or-url>
twitter bookmark <tweet-id-or-url>
twitter unbookmark <tweet-id-or-url>

# User actions
twitter follow <username>
twitter unfollow <username>
```

Images may be JPEG, PNG, GIF, or WebP, up to 5 MB each and four images per post.
Successful write envelopes contain only the affected `id`.

## Configuration

The optional configuration file is:

```text
$XDG_CONFIG_HOME/twitter-cli/config.yaml
```

When `XDG_CONFIG_HOME` is unset, the path is `~/.config/twitter-cli/config.yaml`.

```yaml
fetch:
  count: 20

filter:
  lang: []
  excludeRetweets: false
  minScore: null
  limit: null
  weights:
    likes: 1.0
    retweets: 3.0
    replies: 2.0
    bookmarks: 5.0
    viewsLog: 0.5

rateLimit:
  requestDelay: 2.5
  maxRetries: 3
  retryBaseDelay: 5.0
```

Parsing is strict. Unknown keys, malformed values, and invalid ranges produce an
`invalid_input` envelope.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy twitter_cli
uv run pytest -q
uv run pytest -m smoke -v
```

## Safety and performance

- Browser cookies are account credentials. Never print or share them.
- Read paths do not initialize write-only transaction machinery.
- Authentication does not make a preflight request.
- Browser discovery runs in-process once.
- Pagination sleeps only between pages.
- Writes include a randomized delay after account mutations.
