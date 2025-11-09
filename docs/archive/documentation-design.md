# Documentation Design & Best Practices

## Overview

This document describes the design principles and implementation details for Nexus documentation generation and maintenance. It serves as a reference for understanding design decisions and maintaining consistency across documentation tools.

---

## Core Design Principles

### 1. **DRY (Don't Repeat Yourself)**
Every piece of information should appear exactly once in the documentation. Redundant sections create maintenance burden and confuse users.

### 2. **YAGNI (You Aren't Gonna Need It)**
Remove sections that provide no practical value to users. Focus on what users actually need to accomplish their tasks.

### 3. **Practical First**
Present information in the format users will actually use. For configuration, this means YAML with inline documentation, not abstract tables.

### 4. **Single Source of Truth**
Documentation should be auto-generated from code metadata (docstrings, type hints, Pydantic models) to ensure accuracy and consistency.

### 5. **Progressive Disclosure**
Start with essential information, provide deeper details when users need them. Don't overwhelm with unnecessary technical details upfront.

---

## Documentation Generation Tool (`nexus doc`)

### Purpose

Auto-generate API documentation for all plugins and handlers from code metadata, ensuring:
- Accuracy (generated from actual code)
- Consistency (same format for all plugins)
- Maintainability (no manual documentation drift)
- Completeness (all plugins documented automatically)

### Command Usage

```bash
# Generate all documentation (with confirmation)
nexus doc

# Force overwrite without confirmation
nexus doc --force

# Custom output directory
nexus doc --output docs/reference

# Different format
nexus doc --format rst
```

---

## Plugin API Documentation Format

### Evolution History

#### Initial Format (Redundant)
The original format had significant redundancy:

1. **Description** section (from `plugin_spec.description`)
2. **Overview** section (from `plugin_spec.func.__doc__`)
3. **Configuration** table (from `config_model.model_fields`)
4. **YAML Configuration** (from same `config_model.model_fields`)
5. **Function Signature** (technical, no practical value)
6. **Python API** (didn't exist in framework)

**Problems**:
- Description and Overview showed identical content
- Configuration table and YAML Configuration showed same data in different formats
- Function Signature provided no user value
- Python API section was misleading (not applicable)
- Documentation was ~30-40% longer than necessary

#### Optimization (January 2025)

**Design Decision**: Eliminate all redundancy, focus on practical YAML format.

**Changes Made**:
1. ❌ Removed **Description** section (duplicated Overview)
2. ✅ Kept **Overview** section (from function docstring)
3. ❌ Removed **Configuration** table (duplicated YAML)
4. ✅ Kept **YAML Configuration** with enhanced inline comments
5. ❌ Removed **Function Signature** (no practical value)
6. ❌ Removed **Python API** (doesn't exist)
7. ✅ Kept **CLI Usage** (practical examples)

**Results**:
- 30-40% size reduction
- Single source of truth for each piece of information
- All information in copy-pasteable YAML format
- Enhanced YAML with rich inline comments: `field: value  # type: description`

### Current Format

```markdown
# {Plugin Name}

## Overview

{Complete docstring from plugin function}

## Configuration

```yaml
pipeline:
  - plugin: "{Plugin Name}"
    config:
      field1: value1  # type1: description1
      field2: value2  # type2: description2
      nested_config:  # description
        nested_field: value  # type: description
```

## CLI Usage

```bash
# Run with defaults
nexus plugin "{Plugin Name}" --case mycase

# Run with custom config
nexus plugin "{Plugin Name}" --case mycase \
  -C field1=value \
  -C field2=value
```
```

### Design Rationale

**Why YAML-only format?**
- Users copy YAML into their `case.yaml` files
- Inline comments provide type and description exactly where needed
- No need to cross-reference between table and YAML
- Natural format for hierarchical configuration (nested Pydantic models)

**Why rich inline comments?**
- Format: `field: value  # type: description`
- Combines all metadata in one place
- Types help users understand expected values
- Descriptions explain field purpose
- Example: `threshold: 0.0  # float: Minimum value for filtering`

**Why keep CLI Usage?**
- Shows practical command-line examples
- Demonstrates `nexus plugin` command usage
- Provides quick-start template for users

---

## Implementation Details

### Key Functions

#### `_generate_markdown_doc(plugin_name: str, plugin_spec) -> str`

Located in: `src/nexus/cli.py` (lines 861-911)

**Purpose**: Generate complete markdown documentation for a plugin.

**Structure**:
1. Plugin name as H1 header
2. Overview section (from function docstring)
3. Configuration section (YAML with rich comments)
4. CLI Usage section (practical examples)

**Key Design Decisions**:
- No separate handling for nested vs simple configs
- Single unified YAML generation
- No redundant tables or sections

#### `_generate_yaml_config(config_model, lines: list, indent: int = 6)`

Located in: `src/nexus/cli.py` (lines 782-831)

**Purpose**: Generate YAML configuration with rich inline comments.

**Features**:
- Handles nested Pydantic models recursively
- Generates comments in format: `# type: description`
- Supports all Pydantic field types
- Properly formats default values

**Example Output**:
```yaml
      input_data: "data/input.csv"  # str: Input data file path
      threshold: 0.5  # float: Threshold for filtering
      config:  # Advanced configuration options
        nested_field: true  # bool: Enable feature
```

#### Helper Functions

**`_format_yaml_value(value) -> str`** (lines 834-858)
- Formats Python values for YAML output
- Handles str, bool, int, float, list, None
- Returns "# REQUIRED" for required fields

**`_get_field_type_name(field_info) -> str`** (lines 749-760)
- Extracts clean type name from Pydantic field
- Handles complex types (Optional, List, etc.)
- Returns user-friendly type names

**`_is_nested_model(field_info) -> bool`** (lines 732-746)
- Checks if field is a nested Pydantic model
- Used to determine YAML structure
- Enables proper nesting in generated docs

---

## CLI Help System (`nexus help`)

### Purpose

Provide quick terminal-based help for commands and plugins.

### Command Usage

```bash
# General help
nexus help

# Plugin-specific help
nexus help --plugin "Data Generator"
```

### Design Decision: Separation from `nexus doc`

**Question**: Should `nexus help` and `nexus doc` share code for plugin information?

**Answer**: No, keep them separate.

**Rationale**:

1. **Different Use Cases**:
   - `nexus help`: Quick terminal reference, minimal output
   - `nexus doc`: Complete documentation generation, full details

2. **Different Output Formats**:
   - `nexus help`: Plain text, concise, terminal-friendly
   - `nexus doc`: Markdown/RST/JSON, structured, file-based

3. **Different Information Density**:
   - `nexus help`: Essential info only (name, description, key config)
   - `nexus doc`: Complete info (all fields, types, descriptions, examples)

4. **Different Audiences**:
   - `nexus help`: Users needing quick reminder
   - `nexus doc`: Users writing configurations, developers contributing

5. **Maintenance Simplicity**:
   - Sharing code would create coupling
   - Each command can evolve independently
   - Code duplication is minimal (just metadata access)

**Implementation**: Both commands access the same source (plugin metadata from `PluginSpec`), but format and present it differently for their specific purposes.

---

## Handler Documentation Format

### Current Format

```markdown
# {HANDLER_NAME} Handler

## Overview

{Handler docstring}

## Produced Type

**Type**: `{type_name}`

## Methods

### `load(path: Path) -> Any`
Load data from the specified file path.

### `save(data: Any, path: Path) -> None`
Save data to the specified file path.

## Usage Example

### In Plugin Configuration
```python
from typing import Annotated
from nexus import PluginConfig, DataSource, DataSink

class MyConfig(PluginConfig):
    input_data: Annotated[str, DataSource(handler="{handler}")] = "data/input.{ext}"
    output_data: Annotated[str, DataSink(handler="{handler}")] = "data/output.{ext}"
```

### In YAML Configuration
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "data/input.{ext}"
      output_data: "data/output.{ext}"
```
```

### Design Rationale

**Why show both Python and YAML?**
- Handlers are used through type annotations in plugin code
- Users need to understand the annotation pattern
- YAML shows the user-facing configuration
- Both perspectives are valuable for handler documentation

**Why include produced_type?**
- Helps users understand what data type the handler returns
- Important for type safety and plugin development
- Useful for debugging type mismatches

---

## Documentation Output Structure

### Generated Structure

```
docs/api/
├── README.md              # API documentation index
├── plugins/
│   ├── README.md          # Plugin index
│   ├── data_generator.md
│   ├── data_filter.md
│   ├── data_aggregator.md
│   ├── data_validator.md
│   └── sample_data_generator.md
└── handlers/
    ├── README.md          # Handler index
    ├── csv.md
    ├── json.md
    ├── parquet.md
    ├── excel.md
    ├── xml.md
    └── pickle.md
```

### Index Generation

**Plugin Index** (`docs/api/plugins/README.md`):
- Lists all plugins with links
- Shows description for each plugin
- Displays total plugin count

**Handler Index** (`docs/api/handlers/README.md`):
- Lists all handlers with links
- Shows first line of docstring
- Displays total handler count

**Main Index** (`docs/api/README.md`):
- Links to plugin and handler sections
- Shows counts for both categories
- Notes auto-generation source

---

## Best Practices for Maintaining Documentation

### 1. Auto-Generate Regularly

Run `nexus doc --force` whenever:
- New plugins are added
- Plugin configurations change
- Plugin docstrings are updated
- New handlers are added

### 2. Write Good Docstrings

Plugin function docstrings should:
- Start with concise one-line summary
- Explain what the plugin does (not implementation)
- Document supported features/options
- Include return value description
- Use clear, user-focused language

**Example**:
```python
@plugin(name="Data Filter", config=DataFilterConfig)
def data_filter(config: DataFilterConfig, logger) -> pd.DataFrame:
    """
    Filter data based on column conditions.

    Applies filtering conditions to a dataset and optionally removes null values.
    Useful for data cleaning and subsetting operations.

    Supported operators:
    - '>' : Greater than
    - '<' : Less than
    - '>=' : Greater than or equal
    - '<=' : Less than or equal
    - '==' : Equal to
    - '!=' : Not equal to

    Returns:
        Filtered DataFrame with matching rows
    """
```

### 3. Use Pydantic Field Descriptions

All config fields should have descriptions:

```python
class DataFilterConfig(PluginConfig):
    input_data: Annotated[str, DataSource(handler="csv")] = Field(
        default="data/input.csv",
        description="Input data file path"
    )
    column: str = Field(
        default="value",
        description="Column name to filter on"
    )
    operator: str = Field(
        default=">",
        description="Comparison operator (>, <, >=, <=, ==, !=)"
    )
```

### 4. Commit Generated Docs

- Generated documentation should be committed to version control
- Ensures docs match code version
- Enables documentation review in pull requests
- Provides offline documentation access

### 5. Review Generated Output

After running `nexus doc`, review:
- YAML syntax is correct
- Comments are properly formatted
- Type names are clear and accurate
- Examples are practical and correct
- No missing information

---

## Future Enhancements

### Potential Improvements

1. **Interactive Documentation**
   - Web-based documentation viewer
   - Searchable plugin/handler index
   - Live configuration validator

2. **Additional Formats**
   - HTML output with CSS styling
   - PDF generation for offline reading
   - Man pages for Unix systems

3. **Enhanced Metadata**
   - Plugin categories/tags
   - Complexity ratings
   - Performance characteristics
   - Usage examples from test cases

4. **Documentation Testing**
   - Verify all examples are valid YAML
   - Check that config matches actual plugin
   - Validate type annotations
   - Test CLI examples automatically

5. **Multilingual Support**
   - Generate docs in multiple languages
   - Translate docstrings
   - Localized examples

---

## Version History

### Version 1.0 (January 2025)
- Optimized plugin documentation format
- Eliminated redundancy (30-40% size reduction)
- Enhanced YAML with rich inline comments
- Unified documentation structure
- Added this design document

### Initial Version (December 2024)
- Basic `nexus doc` command
- Markdown/RST/JSON output formats
- Auto-generation from plugin metadata
- Plugin and handler documentation

---

## References

- [Architecture Documentation](architecture.md) - Framework design principles
- [User Guide](user-guide.md) - User-facing documentation
- [API Documentation](api/README.md) - Generated API docs
- `src/nexus/cli.py` - Documentation generation implementation

---

**Last Updated**: 2025-01-10
**Maintained By**: Nexus Development Team
