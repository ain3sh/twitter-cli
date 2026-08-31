"""Tests for the canonical output contract."""

from __future__ import annotations

import json

import yaml

from twitter_cli.output import (
    emit_success,
    ensure_utf8_streams,
    error_payload,
    render_success,
    resolve_output_format,
    success_payload,
    use_rich_output,
    use_structured_output,
)


def test_ensure_utf8_streams_no_error() -> None:
    ensure_utf8_streams()


def test_success_payload_structure() -> None:
    assert success_payload({"key": "value"}) == {
        "ok": True,
        "schemaVersion": "1",
        "data": {"key": "value"},
    }


def test_error_payload_structure() -> None:
    assert error_payload("not_found", "User not found") == {
        "ok": False,
        "schemaVersion": "1",
        "error": {
            "code": "not_found",
            "message": "User not found",
        },
    }


def test_error_payload_with_details() -> None:
    payload = error_payload("api_error", "oops", details={"id": "123"})
    assert payload["error"]["details"] == {"id": "123"}


def test_output_defaults_to_yaml() -> None:
    assert resolve_output_format(None) == "yaml"


def test_explicit_output_formats() -> None:
    assert resolve_output_format("json") == "json"
    assert resolve_output_format("rich") == "rich"
    assert resolve_output_format("markdown") == "markdown"


def test_rich_output_is_explicit() -> None:
    assert use_rich_output(None) is False
    assert use_rich_output("rich") is True


def test_only_yaml_and_json_use_the_structured_envelope() -> None:
    assert use_structured_output("yaml") is True
    assert use_structured_output("json") is True
    assert use_structured_output("rich") is False
    assert use_structured_output("markdown") is False


def test_render_json_emits_success_envelope() -> None:
    payload = json.loads(render_success({"key": "value"}, "json"))
    assert payload["ok"] is True
    assert payload["data"] == {"key": "value"}


def test_render_yaml_uses_literal_multiline_strings() -> None:
    rendered = render_success({"text": "first\nsecond"}, "yaml")
    assert "text: |-" in rendered
    assert yaml.safe_load(rendered)["data"]["text"] == "first\nsecond"


def test_emit_success_returns_false_for_rich() -> None:
    assert emit_success({"key": "value"}, "rich") is False


def test_emit_success_includes_pagination(capsys) -> None:
    emit_success("hello", "yaml", pagination={"nextCursor": "next"})
    payload = yaml.safe_load(capsys.readouterr().out)
    assert payload == {
        "ok": True,
        "schemaVersion": "1",
        "data": "hello",
        "pagination": {"nextCursor": "next"},
    }
