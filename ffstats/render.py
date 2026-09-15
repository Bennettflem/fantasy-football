from __future__ import annotations

import math


def fmt(v, floatfmt: str = "{:.1f}") -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return floatfmt.format(v)
    return str(v).replace("|", "\\|")


def table(rows: list[dict], columns: list[tuple[str, str]] | None = None, floatfmt: str = "{:.1f}") -> str:
    if not rows:
        return "_(nothing to show)_"
    if columns is None:
        columns = [(k, k) for k in rows[0]]
    head = "| " + " | ".join(h for _, h in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(fmt(r.get(k), floatfmt) for k, _ in columns) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "_(nothing to report)_"


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def signed(x: float, digits: int = 1) -> str:
    return f"{x:+.{digits}f}"
