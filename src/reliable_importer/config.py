from pathlib import Path
import yaml
from reliable_importer.exceptions import ConfigurationError
from reliable_importer.models import AppConfig, LoggingConfig, ProcessingConfig

def load_config(path: Path) -> AppConfig:
    try:
        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError("Invalid YAML configuration") from error

    try:
        config = AppConfig(
            input_path=Path(raw["input"]["path"]),
            output_path=Path(raw["output"]["path"]),
            processing=ProcessingConfig(
                skip_invalid=bool(raw["processing"]["skip_invalid"]),
                allowed_priorities=list(raw["processing"]["allowed_priorities"]),
                allowed_statuses=list(raw["processing"]["allowed_statuses"]),
            ),
            logging=LoggingConfig(
                level=str(raw["logging"]["level"]),
                path=Path(raw["logging"]["path"])
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigurationError("Configuration structure is invalid") from error

    validate_config(config)
    return config

def validate_config(config: AppConfig) -> None:
    if not config.input_path.exists():
        raise ConfigurationError(f"Input file not found: {config.input_path}")
    if not config.processing.allowed_priorities:
        raise ConfigurationError("allowed_priorities cannot be empty")
    if not config.processing.allowed_statuses:
        raise ConfigurationError("allowed_statuses cannot be empty")
