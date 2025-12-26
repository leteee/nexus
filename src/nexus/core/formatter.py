"""
Plugin information formatting for CLI and documentation.

Provides unified formatting logic for:
- CLI table output (rich)
- Markdown documentation
- JSON/YAML export
"""

from typing import List, Dict, Any, Optional
from pydantic_core import PydanticUndefined

from .types import PluginSpec


class PluginInfo:
    """Extracted plugin information for formatting."""

    def __init__(self, spec: PluginSpec):
        self.name = spec.name
        self.description = spec.description or ""
        self.tags = spec.tags or []
        self.has_config = spec.config_model is not None
        self.config_model = spec.config_model
        self.fields = self._extract_fields(spec.config_model) if spec.config_model else []

    def _extract_fields(self, config_model) -> List[Dict[str, Any]]:
        """Extract field metadata from Pydantic model."""
        fields = []
        json_schema = config_model.model_json_schema()
        properties = json_schema.get("properties", {})

        for field_name, field_info in config_model.model_fields.items():
            field_schema = properties.get(field_name, {})
            default = field_info.default

            fields.append({
                "name": field_name,
                "type": self._format_type(field_info.annotation),
                "required": default is PydanticUndefined,
                "default": default if default is not PydanticUndefined else None,
                "description": field_info.description or "",
                "schema": field_schema,
                "field_info": field_info,
            })

        return fields

    @staticmethod
    def _format_type(annotation) -> str:
        """Format type annotation to readable string."""
        type_str = getattr(annotation, "__name__", str(annotation))
        return type_str.replace("typing.", "")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/YAML export."""
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "has_config": self.has_config,
            "fields": [
                {
                    "name": f["name"],
                    "type": f["type"],
                    "required": f["required"],
                    "default": str(f["default"]) if f["default"] is not None else None,
                    "description": f["description"],
                }
                for f in self.fields
            ],
        }


class PluginFormatter:
    """Format plugin information for different outputs."""

    @staticmethod
    def generate_yaml_template(info: PluginInfo, include_comments: bool = True) -> str:
        """Generate YAML configuration template."""
        from .cli_helpers import generate_yaml_value_from_schema

        lines = [
            "pipeline:",
            f'  - plugin: "{info.name}"',
            "    config:",
        ]

        if not info.fields:
            lines.append("      # No configuration required")
            return "\n".join(lines)

        for field in info.fields:
            field_schema = field["schema"]
            default = field["default"]

            # Generate YAML value
            if field["required"]:
                yaml_lines = generate_yaml_value_from_schema(field_schema, indent=2)
            elif default is None:
                yaml_lines = ["null"]
            elif isinstance(default, str):
                yaml_lines = [f'"{default}"']
            elif isinstance(default, bool):
                yaml_lines = [str(default).lower()]
            elif isinstance(default, (int, float)):
                yaml_lines = [str(default)]
            elif isinstance(default, (list, dict)):
                yaml_lines = generate_yaml_value_from_schema(field_schema, indent=2)
            else:
                yaml_lines = [str(default)]

            # Build comment
            if include_comments:
                comment = f"  # {field['type']}"
                if field['required']:
                    comment += " (required)"
                if field['description']:
                    comment += f": {field['description']}"
            else:
                comment = ""

            # Output YAML lines
            if len(yaml_lines) == 1 and not yaml_lines[0].startswith("\n"):
                lines.append(f"      {field['name']}: {yaml_lines[0]}{comment}")
            else:
                lines.append(f"      {field['name']}:{comment}")
                for yaml_line in yaml_lines:
                    if yaml_line:
                        lines.append(f"    {yaml_line}")

        return "\n".join(lines)

    @staticmethod
    def generate_markdown(info: PluginInfo) -> str:
        """Generate Markdown documentation for a plugin."""
        lines = [f"# {info.name}", ""]

        # Tags
        if info.tags:
            lines.append(f"**Tags:** {', '.join(f'`{tag}`' for tag in info.tags)}")
            lines.append("")

        # Overview
        if info.description:
            lines.extend(["## Overview", "", info.description.strip(), ""])

        # Configuration
        lines.append("## Configuration")
        lines.append("")

        if info.has_config and info.fields:
            # YAML example
            lines.append("### Example Configuration")
            lines.append("")
            lines.append("```yaml")
            yaml_template = PluginFormatter.generate_yaml_template(info, include_comments=True)
            lines.append(yaml_template)
            lines.append("```")
            lines.append("")

            # Field reference table
            lines.append("### Field Reference")
            lines.append("")
            lines.append("| Field | Type | Default | Description |")
            lines.append("|-------|------|---------|-------------|")

            for field in info.fields:
                if field['required']:
                    default_str = "*required*"
                elif field['default'] is None:
                    default_str = "`null`"
                elif isinstance(field['default'], str):
                    default_str = f'`"{field["default"]}"`'
                elif isinstance(field['default'], bool):
                    default_str = f"`{str(field['default']).lower()}`"
                else:
                    default_str = f"`{field['default']}`"

                lines.append(
                    f"| `{field['name']}` | `{field['type']}` | {default_str} | {field['description']} |"
                )

            lines.append("")
        else:
            lines.append("This plugin has no configuration options.")
            lines.append("")

        # CLI Usage
        lines.append("## CLI Usage")
        lines.append("")
        lines.append("```bash")
        lines.append("# Run with default configuration")
        lines.append(f'nexus exec "{info.name}" --case mycase')
        lines.append("")
        if info.fields:
            lines.append("# Run with custom configuration")
            cmd_line = f'nexus exec "{info.name}" --case mycase ' + "\\"
            lines.append(cmd_line)
            for i, field in enumerate(example_fields):
                if i < len(example_fields) - 1:
                    lines.append(f"  -C {field['name']}=value \\")
                else:
                    lines.append(f"  -C {field['name']}=value")
        lines.append("```")
        lines.append("")

        return "\n".join(lines)
