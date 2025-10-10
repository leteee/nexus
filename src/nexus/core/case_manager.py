"""
Simplified template and case management for Nexus framework.

This module provides the CaseManager class for managing pipeline cases and templates
with flexible template discovery from multiple search paths.

Core Concepts:
    - **Case**: A complete workspace containing data files and configuration (case.yaml)
    - **Template**: A reusable pipeline definition discovered from configured paths
    - **Template Discovery**: Configurable search paths with priority and nesting support
    - **Mutual Exclusion**: Template replaces case.yaml when specified, not a config layer

Typical Usage:
    >>> manager = CaseManager(
    ...     project_root=Path("/path/to/project"),
    ...     template_paths=["templates", "custom_templates"],
    ...     template_recursive=True
    ... )
    >>> # With template: Loads template directly (ignores case.yaml)
    >>> config_path, config = manager.get_pipeline_config("mycase", "quickstart")
    >>> # Without template: Loads case.yaml
    >>> config_path, config = manager.get_pipeline_config("mycase")
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class CaseManager:
    """
    Manages pipeline cases and templates with configurable template discovery.

    The CaseManager implements a template system with flexible discovery:
    1. **With Template**: Load template from configured search paths, ignore case.yaml
    2. **Without Template**: Load case.yaml from case directory

    Template Discovery Features:
    - Multiple search paths with priority order (first match wins)
    - Support for nested template organization (custom/pipeline.yaml → "custom/pipeline")
    - Path resolution: relative, absolute, user home (~), environment variables
    - Configurable recursive scanning

    Template is NOT a configuration layer - it's a starting point/scaffold:
    - Templates are reusable pipeline definitions
    - When specified, template completely replaces case.yaml
    - No merging, no reference semantics, pure mutual exclusion

    Attributes:
        project_root (Path): Root directory of the Nexus project
        cases_root (Path): Directory containing all case workspaces
        template_paths (List[str]): List of template search paths (in priority order)
        template_recursive (bool): Whether to search template paths recursively

    Example:
        >>> from pathlib import Path
        >>> manager = CaseManager(
        ...     project_root=Path.cwd(),
        ...     template_paths=["templates", "custom_templates", "~/shared/templates"],
        ...     template_recursive=True
        ... )
        >>>
        >>> # With template: Uses template, case.yaml ignored
        >>> path, config = manager.get_pipeline_config("analysis", "quickstart")
        >>> # Returns: (templates/quickstart.yaml, config_from_template)
        >>>
        >>> # Without template: Uses case.yaml
        >>> path, config = manager.get_pipeline_config("analysis")
        >>> # Returns: (cases/analysis/case.yaml, config_from_case)
        >>>
        >>> # List available resources
        >>> templates = manager.list_available_templates()
        >>> cases = manager.list_existing_cases()
    """

    def __init__(
        self,
        project_root: Path,
        cases_root: str = "cases",
        template_paths: List[str] = None,
        template_recursive: bool = False,
    ):
        """
        Initialize CaseManager with configurable template discovery.

        Args:
            project_root (Path): Absolute path to project root directory.
            cases_root (str, optional): Relative path to cases directory from project_root.
                Defaults to "cases".
            template_paths (List[str], optional): List of template search paths in priority order.
                Supports:
                - Relative paths (relative to project_root): "templates", "custom"
                - Absolute paths: "/opt/shared/templates"
                - User home: "~/my_templates"
                - Environment variables: "$NEXUS_TEMPLATES"
                Defaults to ["templates"].
            template_recursive (bool, optional): Whether to search template paths recursively.
                False: Only top-level *.yaml files (flat structure)
                True: All *.yaml in subdirectories (nested organization)
                Defaults to False.

        Example:
            >>> manager = CaseManager(
            ...     project_root=Path("/path/to/project"),
            ...     cases_root="my_cases",
            ...     template_paths=["templates", "~/shared", "/opt/company"],
            ...     template_recursive=True
            ... )
        """
        self.project_root = project_root
        self.cases_root = self._resolve_path(cases_root)
        self.template_paths = template_paths or ["templates"]
        self.template_recursive = template_recursive

        # Resolve all template search paths
        self._template_search_paths = [
            self._resolve_path(path) for path in self.template_paths
        ]

        logger.debug(
            f"CaseManager initialized with template search paths: "
            f"{[str(p) for p in self._template_search_paths]}, "
            f"recursive={self.template_recursive}"
        )

    def _resolve_path(self, path_str: str) -> Path:
        """
        Resolve path string to absolute Path object.

        Supports:
        - Relative paths (resolved relative to project root)
        - Absolute paths
        - User home directory (~)
        - Environment variables ($VAR or ${VAR})

        Args:
            path_str (str): Path string to resolve

        Returns:
            Path: Resolved absolute Path object

        Example:
            >>> manager._resolve_path("templates")
            Path('/project/templates')
            >>> manager._resolve_path("~/my_templates")
            Path('/home/user/my_templates')
            >>> manager._resolve_path("/opt/templates")
            Path('/opt/templates')
        """
        # Expand environment variables
        expanded = os.path.expandvars(path_str)

        # Expand user home directory
        expanded = os.path.expanduser(expanded)

        path_obj = Path(expanded)

        # If not absolute, make relative to project root
        if not path_obj.is_absolute():
            path_obj = self.project_root / path_obj

        return path_obj.resolve()

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
        Get pipeline configuration with template mutual exclusion.

        This is the primary method for retrieving pipeline configurations. Templates
        and case.yaml are mutually exclusive - not a configuration hierarchy.

        **Execution Modes**:

        1. **Template Mode** (--template specified):
           - Action: Load template from configured search paths
           - Result: Returns (template path, template config)
           - Note: case.yaml is completely ignored (even if it exists)
           - Use case: Using template as starting point or reusable pipeline
           - Supports nested templates: "custom/pipeline" if recursive=True

        2. **Case Mode** (no --template):
           - Action: Load case.yaml
           - Result: Returns (case.yaml path, case config)
           - Use case: Running custom case configuration

        **Configuration Hierarchy** (4 layers):
            CLI overrides > Case/Template config > Global config > Plugin defaults

        Args:
            case_path (str): Case identifier or absolute path.
                The case directory will be created if it doesn't exist.
                Examples: "analysis", "finance/q1", "/tmp/test-case"

            template_name (Optional[str], optional): Template name to use.
                Can be with or without .yaml extension.
                Examples: "quickstart", "demo", "custom/pipeline"
                If specified, case.yaml is ignored. Defaults to None.

        Returns:
            tuple[Path, Dict[str, Any]]: A tuple containing:
                - **config_path** (Path): Path to the configuration file being used
                  (either case.yaml or template.yaml)
                - **config_data** (Dict[str, Any]): Parsed configuration dictionary

        Raises:
            FileNotFoundError: If template not found or case.yaml missing when no template specified.
                The error message includes available templates or suggests creating case.yaml.

        Example:
            >>> manager = CaseManager(
            ...     Path("/project"),
            ...     template_paths=["templates"],
            ...     template_recursive=True
            ... )
            >>>
            >>> # Template mode: Load template, ignore case.yaml
            >>> path, config = manager.get_pipeline_config("analysis", "demo")
            >>> print(path)  # /project/templates/demo.yaml
            >>>
            >>> # Case mode: Load case.yaml
            >>> path, config = manager.get_pipeline_config("analysis")
            >>> print(path)  # /project/cases/analysis/case.yaml

        Note:
            - Template is NOT a configuration layer to merge
            - Template is a scaffold/starting point that replaces case.yaml
            - The case directory is created automatically for data storage
            - Template search follows priority order of template_paths
        """
        case_dir = self.resolve_case_path(case_path)
        case_config_path = case_dir / "case.yaml"

        # Ensure case directory exists (for data files)
        case_dir.mkdir(parents=True, exist_ok=True)

        if template_name:
            # Template mode: Load template, ignore case.yaml
            return self._handle_template_mode(template_name)
        else:
            # Case mode: Load case.yaml
            return self._handle_case_mode(case_config_path)

    def _handle_template_mode(
        self, template_name: str
    ) -> tuple[Path, Dict[str, Any]]:
        """
        Handle pipeline execution in template mode.

        Loads template from configured search paths, completely ignoring case.yaml.

        Args:
            template_name (str): Name of template to use (may include path if recursive)

        Returns:
            tuple[Path, Dict[str, Any]]: Template path and configuration

        Raises:
            FileNotFoundError: If specified template doesn't exist in any search path
        """
        template_path = self._find_template(template_name)
        logger.info(f"Template mode: Using template {template_path}")
        config_data = self._load_yaml(template_path)
        return template_path, config_data

    def _handle_case_mode(
        self, case_config_path: Path
    ) -> tuple[Path, Dict[str, Any]]:
        """
        Handle pipeline execution in case mode.

        Loads configuration from case.yaml.

        Args:
            case_config_path (Path): Expected path to case.yaml file

        Returns:
            tuple[Path, Dict[str, Any]]: Case config path and configuration

        Raises:
            FileNotFoundError: If case.yaml doesn't exist, with helpful message
                suggesting template usage or manual case.yaml creation
        """
        if not case_config_path.exists():
            raise FileNotFoundError(
                f"No case configuration found at {case_config_path}. "
                f"Either create a case.yaml file or specify a template with --template."
            )

        logger.info(f"Case mode: Using case configuration {case_config_path}")
        config_data = self._load_yaml(case_config_path)
        return case_config_path, config_data

    def _find_template(self, template_name: str) -> Path:
        """
        Locate template file by name across all configured search paths.

        Searches template paths in priority order (first match wins).

        Args:
            template_name (str): Template identifier (e.g., "quickstart" or "custom/pipeline")
                Can be with or without .yaml extension

        Returns:
            Path: Absolute path to template file

        Raises:
            FileNotFoundError: If template not found in any search path,
                with list of available templates

        Example:
            >>> # With recursive=False
            >>> manager._find_template("quickstart")
            Path('/project/templates/quickstart.yaml')

            >>> # With recursive=True (custom nested template)
            >>> manager._find_template("custom/pipeline")
            Path('/project/templates/custom/pipeline.yaml')
        """
        template_filename = (
            template_name
            if template_name.endswith(".yaml")
            else f"{template_name}.yaml"
        )

        # Search in priority order (first match wins)
        for search_path in self._template_search_paths:
            if not search_path.exists():
                logger.debug(f"Template search path does not exist: {search_path}")
                continue

            # Try direct path first (handles both flat and nested templates)
            template_path = search_path / template_filename
            if template_path.exists():
                logger.debug(f"Found template at: {template_path}")
                return template_path

            # If recursive, try glob search (for flexibility)
            if self.template_recursive:
                # Search for template in subdirectories
                glob_pattern = f"**/{template_filename}"
                for found_path in search_path.glob(glob_pattern):
                    logger.debug(f"Found template via glob at: {found_path}")
                    return found_path

        # Template not found in any search path
        available = self.list_available_templates()
        search_paths_str = ", ".join(str(p) for p in self._template_search_paths)

        raise FileNotFoundError(
            f"Template '{template_name}' not found in search paths: [{search_paths_str}]. "
            f"Available templates: {available}"
        )

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

    def list_available_templates(self) -> List[str]:
        """
        List all available template names from all configured search paths.

        Templates are discovered from all search paths in priority order.
        Duplicates are removed (first occurrence wins based on search path priority).

        Returns:
            List[str]: Template names (without .yaml extension).
                For nested templates (if recursive=True), includes path like "custom/pipeline".
                Empty list if no templates found.

        Example:
            >>> # With recursive=False
            >>> manager.list_available_templates()
            ['demo', 'quickstart']

            >>> # With recursive=True (with custom nested templates)
            >>> manager.list_available_templates()
            ['demo', 'quickstart', 'custom/pipeline1', 'custom/pipeline2']
        """
        templates = []
        seen = set()

        for search_path in self._template_search_paths:
            if not search_path.exists():
                logger.debug(f"Template search path does not exist: {search_path}")
                continue

            # Get YAML files based on recursive setting
            if self.template_recursive:
                yaml_files = search_path.glob("**/*.yaml")
            else:
                yaml_files = search_path.glob("*.yaml")

            for yaml_file in yaml_files:
                # Calculate relative template name
                rel_path = yaml_file.relative_to(search_path)
                template_name = str(rel_path.with_suffix("")).replace("\\", "/")

                # Add if not already seen (first occurrence wins)
                if template_name not in seen:
                    templates.append(template_name)
                    seen.add(template_name)

        return sorted(templates)

    def list_existing_cases(self) -> List[str]:
        """
        List all existing cases with case.yaml files.

        Returns:
            List[str]: List of case directory names that contain case.yaml.
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
