"""
Simplified template and case management for Nexus framework.

This module provides the CaseManager class for managing pipeline cases and templates
with intelligent copy-on-write semantics.

Core Concepts:
    - **Case**: A complete workspace containing data files and configuration (case.yaml)
    - **Template**: A reusable pipeline definition stored in templates/
    - **Copy-on-First-Use**: Templates are copied to case.yaml on first execution
    - **Reference-on-Reuse**: Existing cases reference templates without modification

Typical Usage:
    >>> manager = CaseManager(project_root=Path("/path/to/project"))
    >>> config_path, config = manager.get_pipeline_config("mycase", "etl-pipeline")
    >>> # First run: Copies template to cases/mycase/case.yaml
    >>> # Subsequent runs: References template directly
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class CaseManager:
    """
    Manages pipeline cases and templates with copy-on-write semantics.

    The CaseManager implements a smart template system where:
    1. **First Execution**: If case.yaml doesn't exist, copy template → case.yaml
    2. **Subsequent Execution**: If case.yaml exists, reference template directly
    3. **No Template**: Use existing case.yaml as-is

    This pattern allows:
    - Quick case initialization from templates
    - Template updates benefit existing cases (via reference)
    - Case-specific customizations persist in case.yaml

    Attributes:
        project_root (Path): Root directory of the Nexus project
        cases_root (Path): Directory containing all case workspaces
        templates_dir (Path): Directory containing template definitions

    Example:
        >>> from pathlib import Path
        >>> manager = CaseManager(project_root=Path.cwd())
        >>>
        >>> # First run: Creates cases/analysis/case.yaml from template
        >>> path, config = manager.get_pipeline_config("analysis", "etl-pipeline")
        >>>
        >>> # Second run: References template, doesn't modify case.yaml
        >>> path, config = manager.get_pipeline_config("analysis", "etl-pipeline")
        >>>
        >>> # List available resources
        >>> templates = manager.list_available_templates()
        >>> cases = manager.list_existing_cases()
    """

    def __init__(self, project_root: Path, cases_root: str = "cases"):
        """
        Initialize CaseManager with project structure.

        Args:
            project_root (Path): Absolute path to project root directory.
                This should contain both 'cases/' and 'templates/' subdirectories.
            cases_root (str, optional): Relative path to cases directory from project_root.
                Defaults to "cases".

        Example:
            >>> manager = CaseManager(
            ...     project_root=Path("/path/to/project"),
            ...     cases_root="my_cases"
            ... )
        """
        self.project_root = project_root
        self.cases_root = project_root / cases_root
        self.templates_dir = project_root / "templates"

    def resolve_case_path(self, case_path: str) -> Path:
        """
        Resolve case identifier to absolute directory path.

        Supports both relative case names and absolute paths for flexibility:
        - Relative: Resolved relative to cases_root (e.g., "mycase" → "cases/mycase")
        - Absolute: Used as-is (e.g., "/tmp/analysis" → "/tmp/analysis")

        Args:
            case_path (str): Case identifier or absolute path.
                - Relative example: "financial-analysis"
                - Absolute example: "/home/user/projects/analysis"
                - Nested example: "finance/quarterly-report"

        Returns:
            Path: Absolute path to the case directory.

        Example:
            >>> manager = CaseManager(Path("/project"))
            >>> manager.resolve_case_path("mycase")
            Path('/project/cases/mycase')
            >>> manager.resolve_case_path("/tmp/analysis")
            Path('/tmp/analysis')
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
        Get pipeline configuration with intelligent template handling.

        This is the primary method for retrieving pipeline configurations. It implements
        copy-on-write semantics for templates:

        **Execution Modes**:

        1. **Template + New Case** (Copy Mode):
           - Template specified, case.yaml doesn't exist
           - Action: Copy template → case.yaml
           - Result: Returns (case.yaml path, copied config)
           - Use case: Initializing new case from template

        2. **Template + Existing Case** (Reference Mode):
           - Template specified, case.yaml exists
           - Action: Load template directly (don't modify case.yaml)
           - Result: Returns (template path, template config)
           - Use case: Running with latest template updates

        3. **No Template** (Direct Mode):
           - No template specified
           - Action: Load existing case.yaml
           - Result: Returns (case.yaml path, case config)
           - Use case: Running standalone case

        Args:
            case_path (str): Case identifier or absolute path.
                The case directory will be created if it doesn't exist.
                Examples: "analysis", "finance/q1", "/tmp/test-case"

            template_name (Optional[str], optional): Template name to use.
                Can be with or without .yaml extension.
                Examples: "etl-pipeline", "analytics.yaml"
                If None, uses existing case.yaml. Defaults to None.

        Returns:
            tuple[Path, Dict[str, Any]]: A tuple containing:
                - **config_path** (Path): Path to the configuration file being used
                  (either case.yaml or template.yaml)
                - **config_data** (Dict[str, Any]): Parsed configuration dictionary

        Raises:
            FileNotFoundError: If template not found or case.yaml missing when no template specified.
                The error message includes available templates or suggests creating case.yaml.

        Example:
            >>> manager = CaseManager(Path("/project"))
            >>>
            >>> # First run: Copy template to case.yaml
            >>> path, config = manager.get_pipeline_config("analysis", "etl-pipeline")
            >>> print(path)  # /project/cases/analysis/case.yaml
            >>>
            >>> # Second run: Reference template
            >>> path, config = manager.get_pipeline_config("analysis", "etl-pipeline")
            >>> print(path)  # /project/templates/etl-pipeline.yaml
            >>>
            >>> # No template: Use case.yaml
            >>> path, config = manager.get_pipeline_config("analysis")
            >>> print(path)  # /project/cases/analysis/case.yaml

        Note:
            The case directory is created automatically if it doesn't exist, allowing
            for seamless case initialization.
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
        """
        Handle pipeline execution when template is specified.

        Implements the copy-on-first-use, reference-on-reuse pattern:
        - **Copy**: If case.yaml doesn't exist, copy template to case.yaml
        - **Reference**: If case.yaml exists, load template directly

        Args:
            case_dir (Path): Absolute path to case directory
            case_config_path (Path): Expected path to case.yaml file
            template_name (str): Name of template to use

        Returns:
            tuple[Path, Dict[str, Any]]: Configuration path and parsed data

        Raises:
            FileNotFoundError: If specified template doesn't exist
        """
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
        """
        Handle pipeline execution with existing case configuration.

        Loads configuration from case.yaml without any template interaction.

        Args:
            case_config_path (Path): Expected path to case.yaml file

        Returns:
            tuple[Path, Dict[str, Any]]: Configuration path and parsed data

        Raises:
            FileNotFoundError: If case.yaml doesn't exist, with helpful message
                suggesting template usage or manual case.yaml creation
        """
        if not case_config_path.exists():
            raise FileNotFoundError(
                f"No case configuration found at {case_config_path}. "
                f"Either create a case.yaml file or specify a template with --template."
            )

        logger.info(f"Using case configuration: {case_config_path}")
        config_data = self._load_yaml(case_config_path)
        return case_config_path, config_data

    def _find_template(self, template_name: str) -> Path:
        """
        Locate template file by name with flexible naming.

        Supports both "template-name" and "template-name.yaml" formats.

        Args:
            template_name (str): Template identifier (with or without .yaml extension)

        Returns:
            Path: Absolute path to template file

        Raises:
            FileNotFoundError: If template not found, listing available templates
        """
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
        """
        Load and parse YAML configuration file.

        Args:
            file_path (Path): Path to YAML file

        Returns:
            Dict[str, Any]: Parsed configuration dictionary (empty dict if file is empty)

        Raises:
            ValueError: If YAML syntax is invalid
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")

    def list_available_templates(self) -> list[str]:
        """
        List all available template names.

        Returns:
            list[str]: List of template names (without .yaml extension).
                Empty list if templates directory doesn't exist.

        Example:
            >>> manager.list_available_templates()
            ['etl-pipeline', 'analytics', 'data-quality', 'default']
        """
        if not self.templates_dir.exists():
            return []
        return [f.stem for f in self.templates_dir.glob("*.yaml")]

    def list_existing_cases(self) -> list[str]:
        """
        List all existing cases with case.yaml files.

        Returns:
            list[str]: List of case directory names that contain case.yaml.
                Empty list if cases directory doesn't exist.

        Example:
            >>> manager.list_existing_cases()
            ['financial-analysis', 'customer-segmentation', 'quickstart']

        Note:
            Only returns cases that have a case.yaml file. Empty directories
            are not considered valid cases.
        """
        if not self.cases_root.exists():
            return []
        return [
            d.name
            for d in self.cases_root.iterdir()
            if d.is_dir() and (d / "case.yaml").exists()
        ]
