"""Native format: a JSON list (or {"ops": [...]}) of op dicts, or JSON Lines with one op per line."""
from __future__ import annotations

import json
from typing import Any, List

from ..ops import Op


def load(doc: Any, **_) -> List[Op]:
    if isinstance(doc, dict):
        doc = doc.get("ops", [])
    return [Op.from_dict(d) for d in doc]


def load_jsonl(text: str) -> List[Op]:
    return [Op.from_dict(json.loads(line)) for line in text.splitlines() if line.strip()]
