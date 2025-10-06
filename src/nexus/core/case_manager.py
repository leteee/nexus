"""
Simplified template and case management for Nexus framework.

Clear concepts:
- Case = Complete workspace (data + configuration)
- Template = Reusable pipeline definition
- Copy on first use, Reference on subsequent runs
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class CaseManager:
    """
    Manages cases and templates with simple copy/reference logic.

    Logic:
    1. If case.yaml doesn't exist and template specified → Copy template to case.yaml
    2. If case.yaml exists and template specified → Reference template (don't modify case.yaml)
    3. If no template specified → Use existing case.yaml
    """

    def __init__(self, project_root: Path, cases_root: str = "cases"):
        self.project_root = project_root
        self.cases_root = project_root / cases_root
        self.templates_dir = project_root / "templates"

    def resolve_case_path(self, case_path: str) -> Path:
        """
        Resolve case path supporting both relative and absolute paths.

        Args:
            case_path: Case identifier or path

        Returns:
            Absolute path to case directory
        """
        case_path_obj = Path(case_path)

        if case_path_obj.is_absolute():
            return case_path_obj
        else:
            return self.cases_root / case_path

    def get_pipeline_config(
        self, case_path: str, template_name: Optional[str] = None
    ) -> tuple[Path, Dict[str, Any]]:
        """
        Get pipeline configuration using copy/reference logic.

        Args:
            case_path: Case identifier or path
            template_name: Template to use (optional)

        Returns:
            Tuple of (config_file_path, config_data)

        Raises:
            FileNotFoundError: If template or case config not found
        """
        case_dir = self.resolve_case_path(case_path)
        case_config_path = case_dir / "case.yaml"

        # Ensure case directory exists
        case_dir.mkdir(parents=True, exist_ok=True)

        if template_name:
            return self._handle_template_execution(
                case_dir, case_config_path, template_name
            )
        else:
            return self._handle_case_execution(case_config_path)

    def _handle_template_execution(
        self, case_dir: Path, case_config_path: Path, template_name: str
    ) -> tuple[Path, Dict[str, Any]]:
        """Handle execution with template specified."""
        template_path = self._find_template(template_name)

        if not case_config_path.exists():
            # Copy: First time use, copy template to case.yaml
            logger.info(
                f"Creating new case config from template: {template_path} → {case_config_path}"
            )
            shutil.copy2(template_path, case_config_path)
            config_data = self._load_yaml(case_config_path)
            return case_config_path, config_data
        else:
            # Reference: Use template directly, don't modify case.yaml
            logger.info(f"Using template reference: {template_path}")
            config_data = self._load_yaml(template_path)
            return template_path, config_data

    def _handle_case_execution(
        self, case_config_path: Path
    ) -> tuple[Path, Dict[str, Any]]:
        """Handle execution with existing case config."""
        if not case_config_path.exists():
            raise FileNotFoundError(
                f"No case configuration found at {case_config_path}. "
                f"Either create a case.yaml file or specify a template with --template."
            )

        logger.info(f"Using case configuration: {case_config_path}")
        config_data = self._load_yaml(case_config_path)
        return case_config_path, config_data

    def _find_template(self, template_name: str) -> Path:
        """Find template file by name."""
        template_filename = (
            template_name
            if template_name.endswith(".yaml")
            else f"{template_name}.yaml"
        )
        template_path = self.templates_dir / template_filename

        if not template_path.exists():
            available = (
                [f.stem for f in self.templates_dir.glob("*.yaml")]
                if self.templates_dir.exists()
                else []
            )
            raise FileNotFoundError(
                f"Template '{template_name}' not found at {template_path}. "
                f"Available templates: {available}"
            )

        return template_path

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")

    def list_available_templates(self) -> list[str]:
        """List all available templates."""
        if not self.templates_dir.exists():
            return []
        return [f.stem for f in self.templates_dir.glob("*.yaml")]

    def list_existing_cases(self) -> list[str]:
        """List all existing cases."""
        if not self.cases_root.exists():
            return []
        return [
            d.name
            for d in self.cases_root.iterdir()
            if d.is_dir() and (d / "case.yaml").exists()
        ]
