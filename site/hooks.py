"""MkDocs hook: generate the ISP module reference from the Pydantic models.

Replaces ``<!-- MODULE_REFERENCE -->`` in ``modules.md`` so the documentation always
matches the parameters, ranges and defaults in ``fast_openisp.config``.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path
from typing import Any

import annotated_types as at

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fast_openisp.config import MODULE_INFO, MODULE_ORDER, ModulesConfig

MARKER = "<!-- MODULE_REFERENCE -->"


def _type_name(annotation: Any) -> str:
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return " \\| ".join(f"`{arg}`" for arg in typing.get_args(annotation))
    if origin is tuple:
        args = typing.get_args(annotation)
        if args and typing.get_origin(args[0]) is tuple:
            return f"{len(args)}×{len(typing.get_args(args[0]))} matrix"
        return f"{len(args)} × {getattr(args[0], '__name__', args[0])}"
    return getattr(annotation, "__name__", str(annotation))


def _range(metadata: list[Any]) -> str:
    low = high = ""
    for item in metadata:
        if isinstance(item, at.Ge):
            low = f"≥ {item.ge}"
        elif isinstance(item, at.Gt):
            low = f"> {item.gt}"
        elif isinstance(item, at.Le):
            high = f"≤ {item.le}"
        elif isinstance(item, at.Lt):
            high = f"< {item.lt}"
    return ", ".join(part for part in (low, high) if part)


def _default(value: Any) -> str:
    if isinstance(value, tuple) and value and isinstance(value[0], tuple):
        return "identity"
    return f"`{value}`"


def render_reference() -> str:
    lines: list[str] = []
    for name in MODULE_ORDER:
        info = MODULE_INFO[name]
        field = ModulesConfig.model_fields[name]
        model = field.annotation
        assert model is not None
        lines.append(f"### {name.upper()} — {info.full_name}\n")
        doc = (model.__doc__ or "").strip()
        if doc and not doc.startswith("!!!"):
            lines.append(f"{doc}\n")
        if info.requires:
            needs = ", ".join(f"**{req.upper()}**" for req in info.requires)
            lines.append(f"Requires {needs}.\n")
        params = {k: v for k, v in model.model_fields.items() if k != "enabled"}
        enabled_default = model.model_fields["enabled"].default
        lines.append(f"Enabled by default: {'yes' if enabled_default else 'no'}.\n")
        if not params:
            lines.append("No parameters.\n")
            continue
        lines.append("| Parameter | Type | Range | Default | Description |")
        lines.append("|---|---|---|---|---|")
        for key, param in params.items():
            lines.append(
                f"| `{key}` | {_type_name(param.annotation)} | {_range(param.metadata)} "
                f"| {_default(param.default)} | {param.description or ''} |"
            )
        lines.append("")
    return "\n".join(lines)


def on_page_markdown(markdown: str, page: Any, **_: Any) -> str:
    if MARKER in markdown:
        return markdown.replace(MARKER, render_reference())
    return markdown
