from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass(frozen=True, slots=True)
class Task:
    task_id: int
    title: str
    description: str
    priority: str
    status: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class ProcessingConfig:
    skip_invalid: bool
    allowed_priorities: list[str]
    allowed_statuses: list[str]

@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    path: Path

@dataclass(frozen=True, slots=True)
class AppConfig:
    input_path: Path
    output_path: Path
    processing: ProcessingConfig
    logging: LoggingConfig
