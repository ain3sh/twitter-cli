"""Canonical structured output for twitter-cli."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Literal, cast

import click
import yaml

OutputFormat = Literal["yaml", "json", "rich", "markdown"]

_SCHEMA_VERSION = "1"
_STRUCTURED_FORMATS = ("yaml", "json")
_OUTPUT_FORMATS = (*_STRUCTURED_FORMATS, "rich")


class _YamlDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_YamlDumper.add_representer(str, _represent_string)


def ensure_utf8_streams() -> None:
    """Use UTF-8 for captured Windows output."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def resolve_output_format(output_format: str | None) -> OutputFormat:
    """Resolve the command's output format, defaulting to YAML."""
    return cast(OutputFormat, output_format or "yaml")


def output_option(command: Callable | None = None, *, markdown: bool = False) -> Callable:
    """Add the shared output-format option to a Click command."""
    formats = (*_OUTPUT_FORMATS, "markdown") if markdown else _OUTPUT_FORMATS

    def decorate(target: Callable) -> Callable:
        return click.option(
            "--format",
            "output_format",
            type=click.Choice(formats),
            default=None,
            help="Output format (default: yaml).",
        )(target)

    return decorate(command) if command is not None else decorate


def use_rich_output(output_format: str | None) -> bool:
    """Return whether human-readable Rich output is active."""
    return resolve_output_format(output_format) == "rich"


def use_structured_output(output_format: str | None) -> bool:
    """Return whether the output uses the canonical serialized envelope."""
    return resolve_output_format(output_format) in _STRUCTURED_FORMATS


def success_payload(
    data: Any,
    *,
    pagination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap successful data in the stable structured envelope."""
    payload = {
        "ok": True,
        "schemaVersion": _SCHEMA_VERSION,
        "data": data,
    }
    if pagination is not None:
        payload["pagination"] = pagination
    return payload


def error_payload(code: str, message: str, *, details: Any | None = None) -> dict[str, Any]:
    """Wrap an error in the stable structured envelope."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {
        "ok": False,
        "schemaVersion": _SCHEMA_VERSION,
        "error": error,
    }


def _render_payload(payload: dict[str, Any], output_format: str | None) -> str:
    """Serialize one canonical envelope."""
    fmt = resolve_output_format(output_format)
    if fmt not in _STRUCTURED_FORMATS:
        raise ValueError(f"{fmt} output is not a structured envelope")
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return yaml.dump(
        payload,
        Dumper=_YamlDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=10_000,
    )


def render_success(
    data: Any,
    output_format: str | None,
    *,
    pagination: dict[str, Any] | None = None,
) -> str:
    """Serialize one successful envelope."""
    return _render_payload(
        success_payload(data, pagination=pagination),
        output_format,
    )


def emit_success(
    data: Any,
    output_format: str | None,
    *,
    pagination: dict[str, Any] | None = None,
) -> bool:
    """Emit a success envelope, or return False when Rich output is active."""
    if not use_structured_output(output_format):
        return False
    click.echo(
        render_success(data, output_format, pagination=pagination),
        nl=False,
    )
    return True


def emit_error(
    code: str,
    message: str,
    *,
    output_format: str | None = None,
    details: Any | None = None,
) -> bool:
    """Emit an error using the active command format."""
    if output_format is None:
        ctx = click.get_current_context(silent=True)
        if ctx is not None:
            output_format = ctx.params.get("output_format")
    if not use_structured_output(output_format):
        return False
    click.echo(
        _render_payload(error_payload(code, message, details=details), output_format),
        nl=False,
    )
    return True
