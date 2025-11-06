# Pipeline Templates

This directory contains reusable pipeline templates for common data processing workflows.

## What are Templates?

Templates are predefined pipeline configurations that can be used with the `--template` flag instead of creating a `case.yaml` file. They provide quick-start configurations for common use cases.

## Template Discovery

**NEW**: Nexus now supports flexible template discovery from multiple directories!

### Configuration

Configure template search paths in `config/global.yaml`:

```yaml
framework:
  discovery:
    templates:
      # Directories to search (in priority order)
      paths:
        - "templates"              # Built-in templates
        - "custom_templates"       # Your custom templates
        - "~/shared/templates"     # User shared templates
        - "$NEXUS_TEMPLATES"       # Environment variable

      # Enable nested organization
      recursive: true  # false = flat, true = nested
```

### Path Resolution

Template paths support:
- **Relative paths**: `"templates"` → resolved from project root
- **Absolute paths**: `"/opt/company/templates"` → used as-is
- **User home**: `"~/my_templates"` → expands to home directory
- **Environment variables**: `"$NEXUS_TEMPLATES"` → expands from environment

### Priority System

**First match wins** - templates are searched in the order specified in `paths`:

```yaml
paths:
  - "custom_templates"    # Checked first (highest priority)
  - "templates"           # Checked second (fallback)
```

If `custom_templates/quickstart.yaml` exists, it overrides `templates/quickstart.yaml`.

## Template Organization

### Flat Structure (`recursive: false`)

All templates in top-level directory:

```
templates/
├── quickstart.yaml
└── custom.yaml
```

**Usage**: `nexus run --case mycase --template quickstart`

### Nested Structure (`recursive: true`)

Organize templates in subdirectories:

```
templates/
├── quickstart.yaml
└── repro/               # Video data replay templates
    ├── repro.yaml       → "repro/repro"
    └── repro_datagen.yaml → "repro/repro_datagen"
```

**Usage**: `nexus run --case mycase --template repro/repro`

## Template vs Case.yaml

**Important**: Templates and `case.yaml` are **mutually exclusive**, not a configuration hierarchy:

- **With `--template`**: Use template (case.yaml is ignored if it exists)
- **Without `--template`**: Use case.yaml (must exist)

Templates **replace** case.yaml, they don't merge with it.

## Available Templates

### `quickstart.yaml`
**Minimal single-plugin example**

Generates synthetic data with one plugin. Perfect for learning Nexus basics.

**Usage**:
```bash
nexus run --case my-analysis --template quickstart
```

**What it does**:
1. Generates 1000 rows of synthetic data
2. Saves to `data/synthetic_data.csv`

**Pipeline**:
- Data Generator (1000 rows, 5 categories, 0.1 noise)

---

### `repro/repro.yaml`
**Video data replay pipeline**

Complete video processing workflow demonstrating multi-step data overlay on video frames.

**Usage**:
```bash
nexus run --case my-analysis --template repro/repro
```

**What it does**:
1. **Extract** video frames from input video
2. **Render** speed data overlay on frames
3. **Render** 3D target bounding boxes on frames
4. **Compose** final video from rendered frames

**Pipeline**:
- Frame Extractor → Speed Renderer → Target Renderer → Video Composer

---

### `repro/repro_datagen.yaml`
**Synthetic data generation for video replay testing**

Complete synthetic data generation pipeline for testing video replay scenarios.

**Usage**:
```bash
nexus run --case my-analysis --template repro/repro_datagen
```

**What it does**:
1. **Generate** synthetic driving video (1920×1080, 30 FPS)
2. **Generate** frame timeline with timestamp jitter
3. **Generate** event-driven speed data
4. **Generate** ADB target detection data

**Pipeline**:
- Synthetic Video Generator → Timeline Generator → Speed Generator → Target Generator

---

## Using Templates

### Basic Usage

```bash
# Create a case directory (or use existing one)
mkdir cases/my-analysis

# Run with template (no case.yaml needed)
nexus run --case my-analysis --template quickstart
```

### With Configuration Overrides

```bash
# Override template settings via CLI
nexus run --case my-analysis --template repro/repro \
  --config plugins.SpeedRenderer.tolerance_ms=100.0 \
  --config plugins.TargetRenderer.box_color="[255,0,0]"
```

### Template Behavior

When you use `--template`:
- Template file is loaded from `templates/{name}.yaml`
- Template completely replaces any `case.yaml` in the case directory
- CLI overrides (`--config`) still work and have highest precedence
- Case directory is created automatically if it doesn't exist

## Creating Custom Templates

Templates are standard pipeline configuration files in YAML format.

**Required structure**:
```yaml
case_info:
  name: "Template Name"
  description: "What this template does"
  version: "1.0.0"

pipeline:
  - plugin: "Plugin Name"
    config:
      # Plugin configuration
```

**Best practices**:
1. Include clear comments explaining each step
2. Use descriptive file paths for data outputs
3. Set reasonable defaults for configuration parameters
4. Document expected inputs and outputs
5. Add usage examples in comments

## Template Discovery

Templates are automatically discovered from:
1. Built-in templates: `templates/` directory in project root
2. Custom templates: Additional paths configured in `config/global.yaml`

**Configuration example** (`config/global.yaml`):
```yaml
framework:
  discovery:
    templates:
      paths:
        - "custom_templates"      # Additional template directory
        - "/absolute/path/templates"
```

## Listing Available Templates

```bash
# Show all available templates
nexus list templates
```

**Output**:
```
Available templates:
  quickstart

  repro/
    repro
    repro_datagen
```

## Example Workflow

### Quick Start
```bash
# 1. Create case
mkdir cases/test-run

# 2. Run with template
nexus run --case test-run --template quickstart

# 3. Check results
ls cases/test-run/data/
# Output: synthetic_data.csv
```

### Video Replay Pipeline
```bash
# 1. Create case with input video
mkdir -p cases/my_video/input
cp my_video.mp4 cases/my_video/input/video.mp4

# 2. Run video replay pipeline
nexus run --case my_video --template repro/repro

# 3. Check outputs
ls cases/my_video/frames/          # Extracted frames
ls cases/my_video/rendered/        # Rendered frames
ls cases/my_video/output/          # Final video
```

### Synthetic Data Generation
```bash
# 1. Create case
mkdir cases/test_data

# 2. Generate all test data
nexus run --case test_data --template repro/repro_datagen

# 3. Check generated data
ls cases/test_data/input/
# Output: synthetic_driving.mp4, vehicle_timeline.csv, speed.jsonl, adb_targets.jsonl
```

## Template vs Case.yaml: When to Use Each

### Use Templates when:
- ✅ You want to quickly test a standard workflow
- ✅ You're learning Nexus and need examples
- ✅ You want to reuse a pipeline across multiple cases
- ✅ You need a starting point for a new project

### Use case.yaml when:
- ✅ You have project-specific requirements
- ✅ You want full control over pipeline configuration
- ✅ You're building a custom multi-step workflow
- ✅ You need to version-control your pipeline with your data

## Configuration Hierarchy

When using templates, configuration precedence is:

1. **CLI arguments** (`--config key=value`) - Highest priority
2. **Template file** (`templates/{name}.yaml`)
3. **Global config** (`config/global.yaml`)
4. **Plugin defaults** (from PluginConfig class) - Lowest priority

Note: `case.yaml` is **not in the hierarchy** when using `--template` - it's completely ignored.

## Advanced Usage

### Combining with Plugin Command

Templates are for full pipelines. For single plugins, use:
```bash
nexus plugin "Data Generator" --case my-case --config num_rows=1000
```

### Creating Template Variants

You can create template variants for different scenarios:
```
templates/
├── quickstart.yaml           # Standard quickstart
├── quickstart-large.yaml     # Large dataset variant
└── repro/
    ├── repro.yaml            # Standard video replay
    ├── repro_datagen.yaml    # Synthetic data generation
    └── repro_fast.yaml       # Fast/small variant for testing
```

---

## Template Development Guidelines

### 1. Clear Naming
Use descriptive template names that indicate the workflow:
- ✅ `quickstart.yaml` - Obvious purpose
- ✅ `repro/repro.yaml` - Clear workflow type
- ❌ `template1.yaml` - Not descriptive

### 2. Documentation
Include comprehensive comments:
```yaml
# Step 1: Extract video frames
# Splits input video into individual PNG frames for processing
- plugin: "Frame Extractor"
  config:
    video_path: "input/video.mp4"  # Input video file
    output_dir: "frames"           # Frame output directory
```

### 3. Sensible Defaults
Choose defaults that work for most cases:
- Reasonable dataset sizes (not too small, not too large)
- Common parameter values
- Standard file paths

### 4. Output Organization
Use clear, sequential file naming:
```yaml
output_data: "data/01_raw_data.csv"      # Step 1
output_data: "data/02_cleaned.csv"       # Step 2
output_data: "data/03_transformed.csv"   # Step 3
```

### 5. Version Control
Include version info in `case_info`:
```yaml
case_info:
  name: "Template Name"
  description: "Clear description"
  version: "1.0.0"  # Semantic versioning
```

---

## Troubleshooting

### Template not found
```
ERROR: Template 'mytemplate' not found
```
**Solution**: Check template exists in `templates/` and use correct name:
```bash
nexus list templates  # Show available templates
```

### Case.yaml ignored when using template
**This is expected behavior**. Templates completely replace case.yaml. If you want to use case.yaml, don't use `--template` flag.

### Configuration not applying
Check configuration precedence:
1. CLI args override everything
2. Template settings override global
3. Global settings override plugin defaults

---

## See Also

- [User Guide](../docs/user-guide.md) - Complete Nexus usage guide
- [Repro Module Documentation](../workspace/cases/repro/README.md) - Video replay system details
- [Configuration System](../docs/user-guide.md#configuration-system) - Config hierarchy details

---

**Total Templates**: 3 (quickstart, repro/repro, repro/repro_datagen)
**Last Updated**: 2025-11-06
