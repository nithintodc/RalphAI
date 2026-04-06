"""Map metrics to /update | /delete | /new | /keep."""

from __future__ import annotations

from typing import Any, Literal

Rec = Literal["/update", "/delete", "/new", "/keep"]


def recommend(pre: dict[str, Any], post: dict[str, Any]) -> Rec:
    _ = (pre, post)
    return "/keep"
