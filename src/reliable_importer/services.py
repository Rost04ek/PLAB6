import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from reliable_importer.exceptions import RecordValidationError
from reliable_importer.models import Task, ProcessingConfig
from reliable_importer.readers import read_csv_rows
from reliable_importer.validators import parse_task

logger = logging.getLogger(__name__)

@dataclass
class ImportStatistics:
    total: int = 0
    valid: int = 0
    invalid: int = 0

def import_tasks(path: Path, *, config: ProcessingConfig, statistics: ImportStatistics) -> Iterator[Task]:
    for line_number, row in read_csv_rows(path):
        statistics.total += 1
        try:
            task = parse_task(row, line_number=line_number, config=config)
        except RecordValidationError as error:
            statistics.invalid += 1
            logger.warning("Invalid record at line %s: %s", error.line_number, error)
            if config.skip_invalid:
                continue
            raise
        statistics.valid += 1
        yield task
