import os
import json
from pathlib import Path

def get_allowed_statuses() -> list[str]:
    return os.getenv("ALLOWED_STATUSES", "Open,In Progress,Resolved,Closed").split(",")

def get_allowed_priorities() -> list[str]:
    return os.getenv("ALLOWED_PRIORITIES", "Low,Medium,High,Critical").split(",")

def load_json_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
