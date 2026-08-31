---
name: twitter-cli
description: Use the local twitter CLI for Twitter/X reads and user-approved account actions.
author: ain3sh
version: "0.8.6"
tags:
  - twitter
  - x
  - cli
---

# twitter-cli

Binary: `twitter`

## Rules

- Reads are safe when they answer the user's request.
- Writes modify the user's real account. Run only the requested action.
- Never print raw browser cookies.
- YAML is the default output. Use `--format json` for strict JSON consumers.
- Bound network reads with `--max`.

## Authentication

```bash
twitter user
```

The CLI discovers common Zen, Firefox, LibreWolf, Chrome, Chromium, Brave, Edge, Arc,
and Helium profiles. The browser need not be running.

Custom cookie database:

```bash
TWITTER_COOKIE_FILE="/path/to/cookies.sqlite" twitter user
TWITTER_BROWSER=brave TWITTER_COOKIE_FILE="/path/to/Network/Cookies" twitter user
```

## Efficient reads

```bash
twitter feed --max 10
twitter feed --type following --max 10
twitter bookmarks --max 10
twitter search 'query' --max 10
twitter user <username> posts --max 10
twitter user <username> likes --max 10
```

Search accepts Twitter's native query grammar:

```bash
twitter search 'from:bbc lang:en -filter:retweets' --type Latest --max 10
```

## Read reference

```bash
twitter user [username] [posts|likes|followers|following] [--max N]
twitter feed [--type for-you|following] [--max N] [--cursor CURSOR]
twitter bookmarks [--max N]
twitter bookmark-folders [folder-id] [--max N]
twitter search QUERY [--type Top|Latest|Photos|Videos] [--max N]
twitter tweet <id-or-url> [--max N]
twitter article <id-or-url> [--format yaml|json|rich|markdown]
twitter list <list-id> [--max N] [--cursor CURSOR]
twitter filter [file|-]
```

Filter a saved or piped timeline without network access:

```bash
twitter feed --max 100 | twitter filter
twitter filter feed.yaml --format rich
```

## Write reference

```bash
twitter post 'text' [--reply-to id-or-url | --quote id-or-url] [--image file]
twitter delete <id-or-url>
twitter like <id-or-url>
twitter unlike <id-or-url>
twitter retweet <id-or-url>
twitter unretweet <id-or-url>
twitter bookmark <id-or-url>
twitter unbookmark <id-or-url>
twitter follow <username>
twitter unfollow <username>
```

Successful writes return only the affected identifier under `data.id`.

## Output

```yaml
ok: true
schemaVersion: "1"
data: ...
pagination:
  nextCursor: optional
```

Errors:

```yaml
ok: false
schemaVersion: "1"
error:
  code: not_authenticated
  message: ...
```
