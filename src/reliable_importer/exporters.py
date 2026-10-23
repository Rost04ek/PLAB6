import json
from collections.abc import Iterable
from pathlib import Path
from reliable_importer.exceptions import DataExportError
from reliable_importer.models import Task

def export_tasks_json(tasks: Iterable[Task], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    try:
        with temporary.open("w", encoding="utf-8") as file:
            file.write("[\n")
            first = True
            for task in tasks:
                if not first:
                    file.write(",\n")
                json.dump(task.to_dict(), file, ensure_ascii=False, indent=2)
                first = False
                count += 1
            file.write("\n]\n")
        temporary.replace(path)
    except (OSError, TypeError) as error:
        temporary.unlink(missing_ok=True)
        raise DataExportError(f"Cannot export data to {path}") from error
    return count
