import json
from typing import Any, Dict, List


def write_backup_json(path: str, meta: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    payload = {
        "meta": meta,
        "items": items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_backup_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
