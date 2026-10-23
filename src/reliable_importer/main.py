import logging
from pathlib import Path
from reliable_importer.config import load_config
from reliable_importer.exceptions import ApplicationError
from reliable_importer.exporters import export_tasks_json
from reliable_importer.logging_config import configure_logging
from reliable_importer.services import ImportStatistics, import_tasks
from reliable_importer.utils import logged_operation

logger = logging.getLogger(__name__)

def main() -> None:
    try:
        config = load_config(Path("config.yaml"))
        configure_logging(config.logging.level, config.logging.path)
        
        statistics = ImportStatistics()
        
        with logged_operation("Task import/export"):
            tasks = import_tasks(
                config.input_path,
                config=config.processing,
                statistics=statistics,
            )
            
            exported = export_tasks_json(tasks, config.output_path)
            
        logger.info(
            "Total=%s, valid=%s, invalid=%s, exported=%s",
            statistics.total,
            statistics.valid,
            statistics.invalid,
            exported,
        )
    except ApplicationError as error:
        logger.error("Application error: %s", error)
        raise SystemExit(1) from error

if __name__ == "__main__":
    main()
