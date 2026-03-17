from __future__ import annotations

import builtins
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import click

from ..core.case_manager import CaseManager
from ..core.config import load_system_configuration
from ..core.discovery import discover_all_plugins


def find_project_root(start_path: Path) -> Path:
    current = start_path
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return start_path


def setup_logging(level: str = "INFO", project_root: Optional[Path] = None, config_path: Optional[str] = None) -> None:
    import logging.config

    if project_root is None:
        project_root = find_project_root(Path.cwd())

    logging_config_path = Path(config_path) if config_path else project_root / "config" / "logging.yaml"
    if not logging_config_path.is_absolute():
        logging_config_path = project_root / logging_config_path

    if logging_config_path.exists():
        try:
            import yaml
            with open(logging_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            logs_dir = project_root / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            if "handlers" in config and "file" in config["handlers"]:
                file_handler = config["handlers"]["file"]
                if "filename" in file_handler:
                    file_handler["filename"] = str(project_root / file_handler["filename"])

            logging.config.dictConfig(config)
            logging.info("Loaded logging configuration from %s", logging_config_path)
        except Exception as e:  # pylint: disable=broad-except
            logging.basicConfig(
                level=getattr(logging, level.upper()),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            logging.warning("Failed to load logging config from %s: %s", logging_config_path, e)
            logging.warning("Using basic logging configuration")
    else:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.info("No logging.yaml found, using basic configuration")


def load_case_manager(project_root: Path, system_config: Dict[str, Any]) -> CaseManager:
    framework_cfg = system_config.get("framework", {})

    cases_roots = framework_cfg.get("cases_roots", ["cases"])
    cases_roots = [cases_roots] if isinstance(cases_roots, str) else builtins.list(cases_roots)

    templates_roots = framework_cfg.get("templates_roots", ["templates"])
    templates_roots = [templates_roots] if isinstance(templates_roots, str) else builtins.list(templates_roots)

    return CaseManager(project_root, cases_roots=cases_roots, templates_roots=templates_roots)


def discover_plugins(project_root: Path, system_config: Dict[str, Any]) -> None:
    discover_all_plugins(project_root, system_config)


def parse_config_overrides(config_list: tuple[str, ...]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    import json

    system: Dict[str, Any] = {}
    business: Dict[str, Any] = {}
    system_namespaces = {"framework", "logging"}
    business_namespaces = {"plugins"}

    for item in config_list:
        if "=" not in item:
            click.echo(f"Invalid config format: {item}. Use key=value format.")
            continue

        key, value = item.split("=", 1)
        keys = key.split(".")
        namespace = keys[0]

        if namespace in system_namespaces:
            current = system
        elif namespace in business_namespaces:
            current = business
        else:
            click.echo(
                f"Warning: Invalid namespace '{namespace}' in {key}. "
                f"Valid namespaces: {', '.join(sorted(system_namespaces | business_namespaces))}"
            )
            continue

        for part in keys[:-1]:
            current = current.setdefault(part, {})

        lower = value.lower()
        if value.startswith("{") or value.startswith("["):
            try:
                current[keys[-1]] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if lower in {"true", "false"}:
            current[keys[-1]] = lower == "true"
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            current[keys[-1]] = int(value)
        else:
            try:
                current[keys[-1]] = float(value)
            except ValueError:
                current[keys[-1]] = value.strip('"')

    return system, business
