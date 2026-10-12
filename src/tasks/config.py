import os

def get_allowed_statuses() -> list[str]:
    return os.getenv("ALLOWED_STATUSES", "Open,In Progress,Resolved,Closed").split(",")

def get_allowed_priorities() -> list[str]:
    return os.getenv("ALLOWED_PRIORITIES", "Low,Medium,High,Critical").split(",")
