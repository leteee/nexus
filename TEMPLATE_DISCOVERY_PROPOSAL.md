# Template Discovery Configuration - Design Proposal

## Overview

Add configurable template search paths similar to the existing plugin/handler discovery system, allowing users to organize templates in multiple directories and reference external template collections.

---

## Current Behavior

**Template Location**: Hardcoded to `templates/` directory in project root

```python
class CaseManager:
    def __init__(self, project_root: Path, cases_root: str = "cases"):
        self.project_root = project_root
        self.cases_root = project_root / cases_root
        self.templates_dir = project_root / "templates"  # HARDCODED
```

**Limitations**:
- Only one template directory supported
- Cannot reference external template collections
- No organization flexibility (all templates in one flat directory)

---

## Proposed Solution

### 1. Configuration Schema

Add `framework.discovery.templates` section to `config/global.yaml`:

```yaml
framework:
  discovery:
    plugins:
      modules: []
      paths: []
      recursive: true

    handlers:
      paths: []
      recursive: true

    # NEW: Template discovery configuration
    templates:
      # List of directories to search for templates (in priority order)
      paths:
        - "templates"                    # Built-in templates (default, highest priority)
        - "custom_templates"             # Project-specific templates
        - "~/shared/nexus_templates"     # User's shared templates
        - "/opt/company/templates"       # Company-wide templates
        - "$NEXUS_TEMPLATES"             # Environment variable support

      # Whether to search subdirectories (default: false)
      # false = flat structure, true = allows organization like templates/etl/basic.yaml
      recursive: false
```

### 2. Path Resolution Rules

**Same as plugin/handler discovery**:
- **Relative paths**: Resolved relative to project root
- **Absolute paths**: Used as-is
- **User home (~)**: Expanded to user's home directory
- **Environment variables**: `$VAR` or `${VAR}` expanded

**Example**:
```python
# Input: "templates"          → Output: /project/templates
# Input: "~/my_templates"     → Output: /home/user/my_templates
# Input: "/opt/templates"     → Output: /opt/templates
# Input: "$NEXUS_TEMPLATES"   → Output: /var/nexus/templates (if env var set)
```

### 3. Template Discovery Algorithm

**Search Order** (first match wins):
1. Search paths in the order specified in configuration
2. Within each path:
   - If `recursive: false`: Only top-level `*.yaml` files
   - If `recursive: true`: All `*.yaml` files in subdirectories

**Example with recursive=true**:
```
templates/
├── quickstart.yaml              # Found as "quickstart"
├── demo.yaml                    # Found as "demo"
└── etl/
    ├── basic.yaml               # Found as "etl/basic"
    └── advanced.yaml            # Found as "etl/advanced"

custom_templates/
├── company-standard.yaml        # Found as "company-standard"
└── ml/
    └── training.yaml            # Found as "ml/training"
```

**Usage**:
```bash
# Use built-in template
nexus run --case mycase --template quickstart

# Use nested template (if recursive: true)
nexus run --case mycase --template etl/basic

# Use custom template
nexus run --case mycase --template company-standard
```

### 4. Implementation Plan

#### 4.1 Update CaseManager

**File**: `src/nexus/core/case_manager.py`

**Changes**:

```python
class CaseManager:
    def __init__(
        self,
        project_root: Path,
        cases_root: str = "cases",
        template_paths: List[str] = None,  # NEW
        template_recursive: bool = False    # NEW
    ):
        """
        Initialize CaseManager with configurable template search paths.

        Args:
            project_root: Project root directory
            cases_root: Cases directory (relative or absolute)
            template_paths: List of template search paths (priority order)
            template_recursive: Whether to search template paths recursively
        """
        self.project_root = project_root
        self.cases_root = project_root / cases_root if not Path(cases_root).is_absolute() else Path(cases_root)

        # Template discovery configuration
        self.template_paths = template_paths or ["templates"]
        self.template_recursive = template_recursive

        # Resolve all template paths
        self._template_search_paths = [
            self._resolve_path(path) for path in self.template_paths
        ]

    def _resolve_path(self, path_str: str) -> Path:
        """
        Resolve path string to absolute Path object.

        Supports:
        - Relative paths (relative to project root)
        - Absolute paths
        - User home directory (~)
        - Environment variables ($VAR or ${VAR})
        """
        import os

        # Expand environment variables
        expanded = os.path.expandvars(path_str)

        # Expand user home directory
        expanded = os.path.expanduser(expanded)

        path_obj = Path(expanded)

        # If not absolute, make relative to project root
        if not path_obj.is_absolute():
            path_obj = self.project_root / path_obj

        return path_obj.resolve()

    def _find_template(self, template_name: str) -> Path:
        """
        Locate template file by name across all search paths.

        Searches template paths in priority order (first match wins).

        Args:
            template_name: Template identifier (e.g., "quickstart" or "etl/basic")
                Can be with or without .yaml extension

        Returns:
            Path: Absolute path to template file

        Raises:
            FileNotFoundError: If template not found in any search path
        """
        template_filename = (
            template_name
            if template_name.endswith(".yaml")
            else f"{template_name}.yaml"
        )

        # Search in priority order
        for search_path in self._template_search_paths:
            if not search_path.exists():
                continue

            # Try direct path first (for nested templates like "etl/basic")
            template_path = search_path / template_filename
            if template_path.exists():
                return template_path

            # If recursive, search subdirectories
            if self.template_recursive:
                for found_path in search_path.glob(f"**/{template_filename}"):
                    return found_path

        # Template not found, provide helpful error
        available = self.list_available_templates()
        raise FileNotFoundError(
            f"Template '{template_name}' not found in search paths: "
            f"{[str(p) for p in self._template_search_paths]}. "
            f"Available templates: {available}"
        )

    def list_available_templates(self) -> List[str]:
        """
        List all available template names from all search paths.

        Returns:
            List[str]: Template names (without .yaml extension).
                For nested templates (if recursive=True), includes path like "etl/basic".
                Duplicates are removed (first occurrence wins).

        Example:
            >>> manager.list_available_templates()
            ['quickstart', 'demo', 'etl/basic', 'etl/advanced', 'company-standard']
        """
        templates = []
        seen = set()

        for search_path in self._template_search_paths:
            if not search_path.exists():
                continue

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
```

#### 4.2 Update CLI Initialization

**File**: `src/nexus/cli.py`

**Changes in `run` and `plugin` commands**:

```python
@cli.command()
@click.option("--case", "-c", required=True, help="Case directory")
@click.option("--template", "-t", help="Template to use")
@click.option("--config", "-C", multiple=True, help="Config overrides")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def run(case: str, template: Optional[str], config: tuple, verbose: bool):
    """Run a pipeline in the specified case."""
    setup_logging("DEBUG" if verbose else "INFO")

    try:
        # Find project root and load global config
        project_root = find_project_root(Path.cwd())
        global_config = load_yaml(project_root / "config" / "global.yaml")

        # Get framework configuration
        framework_config = global_config.get("framework", {})
        cases_root = framework_config.get("cases_root", "cases")

        # NEW: Get template discovery configuration
        discovery_config = framework_config.get("discovery", {})
        template_config = discovery_config.get("templates", {})
        template_paths = template_config.get("paths", ["templates"])
        template_recursive = template_config.get("recursive", False)

        # Initialize case manager with template configuration
        case_manager = CaseManager(
            project_root,
            cases_root,
            template_paths=template_paths,      # NEW
            template_recursive=template_recursive  # NEW
        )

        # Rest of the command logic...
        config_path, pipeline_config = case_manager.get_pipeline_config(case, template)
        # ... existing code ...
```

**Similar changes for `plugin` command**.

#### 4.3 Update list Command

**File**: `src/nexus/cli.py`

**Changes in `list templates`**:

```python
@cli.command()
@click.argument("what", type=click.Choice(["templates", "cases", "plugins", "handlers"]), default="plugins")
def list(what: str):
    """List available templates, cases, plugins, or handlers."""
    try:
        project_root = find_project_root(Path.cwd())

        if what == "templates":
            global_config = load_yaml(project_root / "config" / "global.yaml")

            # Get configuration
            framework_config = global_config.get("framework", {})
            cases_root = framework_config.get("cases_root", "cases")

            # NEW: Get template discovery configuration
            discovery_config = framework_config.get("discovery", {})
            template_config = discovery_config.get("templates", {})
            template_paths = template_config.get("paths", ["templates"])
            template_recursive = template_config.get("recursive", False)

            # Initialize with configuration
            case_manager = CaseManager(
                project_root,
                cases_root,
                template_paths=template_paths,
                template_recursive=template_recursive
            )

            templates = case_manager.list_available_templates()
            if templates:
                click.echo("Available templates:")

                # Group by directory if recursive
                if template_recursive:
                    # Show with directory structure
                    current_dir = None
                    for template in sorted(templates):
                        template_dir = str(Path(template).parent) if "/" in template else ""
                        if template_dir != current_dir:
                            if template_dir:
                                click.echo(f"\n  {template_dir}/")
                            current_dir = template_dir

                        template_name = Path(template).name
                        click.echo(f"    {template_name}")
                else:
                    # Simple list
                    for template in sorted(templates):
                        click.echo(f"  {template}")
            else:
                click.echo("No templates found in search paths")
                click.echo(f"Search paths: {template_paths}")
```

#### 4.4 Update global.yaml

**File**: `config/global.yaml`

**Add templates section**:

```yaml
framework:
  discovery:
    # Plugin Discovery
    plugins:
      modules: []
      paths: []
      recursive: true

    # Handler Discovery
    handlers:
      paths: []
      recursive: true

    # Template Discovery (NEW)
    templates:
      # Directories to search for templates (in priority order)
      # First match wins when multiple templates have the same name
      paths:
        - "templates"  # Built-in templates (default)

      # Example: Add custom template directories
      # paths:
      #   - "templates"                  # Built-in (highest priority)
      #   - "custom_templates"           # Project-specific
      #   - "~/shared/nexus_templates"   # User's shared templates
      #   - "/opt/company/templates"     # Company-wide templates
      #   - "$NEXUS_TEMPLATES"           # Environment variable

      # Search subdirectories for nested organization
      # false: Only top-level *.yaml files (flat structure)
      # true: All *.yaml in subdirectories (templates/etl/basic.yaml → "etl/basic")
      recursive: false
```

---

## Compatibility

### Backward Compatibility

✅ **Fully backward compatible**

**Default behavior** (when no configuration specified):
- Template paths: `["templates"]` (same as current hardcoded behavior)
- Recursive: `false` (same as current flat structure)

**Existing code** continues to work without any changes:
```bash
# Still works exactly as before
nexus run --case mycase --template quickstart
```

### Migration Path

**No migration needed** for existing users. Configuration is opt-in:

1. **Keep current behavior**: Don't add `templates` config → uses default
2. **Add custom paths**: Add config → additional templates available
3. **Reorganize templates**: Enable `recursive: true` → nested organization

---

## Benefits

### 1. Organization Flexibility

**Flat structure** (recursive: false):
```
templates/
├── quickstart.yaml
├── demo.yaml
├── etl-basic.yaml
├── etl-advanced.yaml
└── ml-training.yaml
```

**Nested structure** (recursive: true):
```
templates/
├── quickstart.yaml
├── demo.yaml
├── etl/
│   ├── basic.yaml      → "etl/basic"
│   └── advanced.yaml   → "etl/advanced"
├── ml/
│   ├── training.yaml   → "ml/training"
│   └── inference.yaml  → "ml/inference"
└── analytics/
    ├── reports.yaml    → "analytics/reports"
    └── dashboard.yaml  → "analytics/dashboard"
```

### 2. External Template Collections

**Company-wide templates**:
```yaml
framework:
  discovery:
    templates:
      paths:
        - "templates"              # Project templates
        - "/opt/company/nexus"     # Company standard templates
```

**Shared user templates**:
```yaml
framework:
  discovery:
    templates:
      paths:
        - "templates"
        - "~/my-nexus-templates"   # Personal template collection
```

### 3. Environment-Specific Templates

```yaml
# Development
framework:
  discovery:
    templates:
      paths:
        - "templates"
        - "templates/dev"

# Production
framework:
  discovery:
    templates:
      paths:
        - "templates"
        - "/opt/production/templates"
```

### 4. Priority System

**First match wins** allows overriding:

```yaml
framework:
  discovery:
    templates:
      paths:
        - "custom_templates"    # Override templates here (highest priority)
        - "templates"           # Built-in templates (fallback)
```

If `custom_templates/quickstart.yaml` exists, it overrides `templates/quickstart.yaml`.

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_case_manager.py`

```python
def test_template_discovery_single_path():
    """Test template discovery with single path (default behavior)."""
    manager = CaseManager(
        project_root=Path("/project"),
        template_paths=["templates"]
    )
    assert manager._template_search_paths == [Path("/project/templates")]

def test_template_discovery_multiple_paths():
    """Test template discovery with multiple paths."""
    manager = CaseManager(
        project_root=Path("/project"),
        template_paths=["templates", "custom", "/opt/shared"]
    )
    assert len(manager._template_search_paths) == 3
    assert manager._template_search_paths[0] == Path("/project/templates")
    assert manager._template_search_paths[1] == Path("/project/custom")
    assert manager._template_search_paths[2] == Path("/opt/shared")

def test_template_path_resolution():
    """Test path resolution with various formats."""
    manager = CaseManager(
        project_root=Path("/project"),
        template_paths=["templates", "~/my_templates", "/opt/templates"]
    )
    # Test relative, home, and absolute paths resolved correctly
    # ...

def test_template_search_priority():
    """Test that first match wins in template search."""
    # Create test structure with duplicate template names
    # Verify first path's template is returned
    # ...

def test_recursive_template_discovery():
    """Test recursive template discovery."""
    manager = CaseManager(
        project_root=Path("/project"),
        template_paths=["templates"],
        template_recursive=True
    )
    # Verify nested templates found with path like "etl/basic"
    # ...

def test_list_templates_with_duplicates():
    """Test that list_available_templates removes duplicates."""
    # Setup multiple paths with same template names
    # Verify only unique names returned
    # Verify priority order (first occurrence wins)
    # ...
```

### Integration Tests

**File**: `tests/test_cli_templates.py`

```python
def test_cli_template_discovery_from_config():
    """Test CLI loads template paths from global.yaml."""
    # Create test global.yaml with custom template paths
    # Run nexus list templates
    # Verify templates from all paths listed
    # ...

def test_cli_nested_template_usage():
    """Test using nested templates via CLI."""
    # Create nested template structure
    # Run: nexus run --case test --template etl/basic
    # Verify correct template loaded
    # ...
```

---

## Documentation Updates

### 1. templates/README.md

Add section on custom template paths:

```markdown
## Custom Template Locations

### Configuring Search Paths

Add custom template directories in `config/global.yaml`:

```yaml
framework:
  discovery:
    templates:
      paths:
        - "templates"              # Built-in templates
        - "custom_templates"       # Your custom templates
        - "~/shared/templates"     # Shared templates
      recursive: false
```

### Nested Template Organization

Enable `recursive: true` to organize templates in subdirectories:

```yaml
framework:
  discovery:
    templates:
      paths:
        - "templates"
      recursive: true  # Enable nested structure
```

Then organize like:
```
templates/
├── etl/
│   ├── basic.yaml
│   └── advanced.yaml
└── ml/
    └── training.yaml
```

Use with: `nexus run --case mycase --template etl/basic`
```

### 2. config/global.yaml

Add inline documentation for the new configuration section (already shown above).

### 3. docs/user-guide.md

Add section on template discovery configuration.

### 4. docs/documentation-design.md

Update template system section with discovery mechanism.

---

## Implementation Checklist

- [ ] Update `CaseManager.__init__()` with `template_paths` and `template_recursive` parameters
- [ ] Implement `CaseManager._resolve_path()` method
- [ ] Update `CaseManager._find_template()` to search multiple paths
- [ ] Update `CaseManager.list_available_templates()` for multiple paths
- [ ] Update `cli.py run` command to load template configuration
- [ ] Update `cli.py plugin` command to load template configuration
- [ ] Update `cli.py list templates` command for better output
- [ ] Add template discovery section to `config/global.yaml`
- [ ] Write unit tests for template discovery
- [ ] Write integration tests for CLI template usage
- [ ] Update `templates/README.md` documentation
- [ ] Update `docs/user-guide.md` with template discovery
- [ ] Update `docs/documentation-design.md` if needed

---

## Estimated Effort

- **Code changes**: ~3-4 hours
- **Testing**: ~2 hours
- **Documentation**: ~1 hour
- **Total**: ~6-7 hours

---

## Alternative Considered: Template Registry

**Idea**: Create a template registry similar to PLUGIN_REGISTRY

**Rejected because**:
- Templates are simple YAML files, not Python code
- No registration decorator needed (just file discovery)
- CaseManager already handles template loading
- Would add unnecessary complexity

**Current approach is simpler**: Just scan directories for `*.yaml` files.

---

## Summary

This proposal adds flexible template discovery configuration following the same patterns as plugin/handler discovery:

✅ **Backward compatible**: Default behavior unchanged
✅ **Consistent**: Same configuration pattern as plugins/handlers
✅ **Flexible**: Multiple paths, priority system, nested organization
✅ **Well-tested**: Comprehensive test coverage
✅ **Documented**: Clear documentation for users

The implementation is straightforward and builds on existing patterns in the codebase.
