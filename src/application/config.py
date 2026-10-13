import os
from typing import List

def get_allowed_statuses() -> List[str]:
    return os.getenv("ALLOWED_STATUSES", "Open,In Progress,Resolved,Closed").split(",")

def get_allowed_priorities() -> List[str]:
    return os.getenv("ALLOWED_PRIORITIES", "Low,Medium,High,Critical").split(",")
