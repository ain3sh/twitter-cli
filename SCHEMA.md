# Structured output schema

YAML is the default. `--format json` emits the same data model as JSON.

## Envelope

```yaml
ok: true
schemaVersion: "1"
data: ...
pagination:
  nextCursor: optional
```

```yaml
ok: false
schemaVersion: "1"
error:
  code: api_error
  message: ...
  details: optional
```

`pagination` appears only when an endpoint returns a continuation cursor.

## Tweet

```yaml
id: "123"
text: Post body
author:
  id: "42"
  name: Alice
  username: alice
  profileImageUrl: https://example.invalid/image
  verified: false
metrics:
  likes: 0
  retweets: 0
  replies: 0
  quotes: 0
  views: 0
  bookmarks: 0
createdAt: Sat Mar 08 12:00:00 +0000 2026
media: []
urls: []
isRetweet: false
retweetedBy: null
lang: en
isSubscriberOnly: false
isPromoted: false
```

Filtered tweets may add `score`. Quoted tweets add `quotedTweet` using this same Tweet shape
recursively. Article tweets may add `articleTitle` and `articleText`.
Media `type` is one of `photo`, `video`, or `animated_gif`.

## User

```yaml
id: "42"
name: Alice
username: alice
bio: ...
location: ...
url: ...
followers: 0
following: 0
tweets: 0
likes: 0
verified: false
profileImageUrl: https://example.invalid/image
createdAt: Sat Mar 08 12:00:00 +0000 2026
```

## Bookmark folder

```yaml
id: folder-id
name: Reading
```

## Write result

```yaml
id: affected-resource-id
```

## Error codes

- `not_authenticated`
- `not_found`
- `invalid_input`
- `rate_limited`
- `network_error`
- `query_id_error`
- `media_upload_error`
- `api_error`
