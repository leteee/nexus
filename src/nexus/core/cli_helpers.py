"""
CLI helper functions for YAML generation.

Extracted from cli.py to be reused by formatter.py.
"""


def generate_yaml_value_from_schema(schema: dict, indent: int = 0) -> list[str]:
    """
    Generate YAML representation from JSON schema recursively.

    Args:
        schema: JSON schema dict from Pydantic
        indent: Current indentation level

    Returns:
        List of YAML lines
    """
    lines = []
    schema_type = schema.get("type")

    # Handle arrays
    if schema_type == "array":
        items_schema = schema.get("items", {})
        items_type = items_schema.get("type")

        if items_type == "object":
            # Array of objects - show example structure
            lines.append("")
            properties = items_schema.get("properties", {})
            if properties:
                # Has defined properties - show full structure
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item")
                for prop_name, prop_schema in properties.items():
                    prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 2)
                    if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                        # Simple value
                        lines.append(f"{indent_str}  {prop_name}: {prop_lines[0]}")
                    else:
                        # Complex value
                        lines.append(f"{indent_str}  {prop_name}:{prop_lines[0]}")
                        lines.extend(prop_lines[1:])
            else:
                # No properties defined - generic dict
                # Show a more useful example with common keys
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item (dict)")
                lines.append(f"{indent_str}  key1: \"value1\"")
                lines.append(f"{indent_str}  key2: \"value2\"")
        elif items_type == "string":
            # Array of strings
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- \"item1\"")
            lines.append(f"{indent_str}- \"item2\"")
        elif items_type == "number" or items_type == "integer":
            # Array of numbers
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- 1")
            lines.append(f"{indent_str}- 2")
        else:
            # Array of primitives or unknown
            lines.append(" []")

    # Handle objects
    elif schema_type == "object":
        properties = schema.get("properties", {})
        if properties:
            lines.append("")
            indent_str = "  " * (indent + 1)
            for prop_name, prop_schema in properties.items():
                prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 1)
                if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                    # Simple value
                    lines.append(f"{indent_str}{prop_name}: {prop_lines[0]}")
                else:
                    # Complex value
                    lines.append(f"{indent_str}{prop_name}:{prop_lines[0]}")
                    lines.extend(prop_lines[1:])
        else:
            lines.append(" {}")

    # Handle primitives
    elif schema_type == "string":
        default = schema.get("default")
        if default:
            lines.append(f'"{default}"')
        else:
            lines.append('"value"')

    elif schema_type == "number" or schema_type == "integer":
        default = schema.get("default")
        if default is not None:
            lines.append(str(default))
        else:
            lines.append("0")

    elif schema_type == "boolean":
        default = schema.get("default")
        if default is not None:
            lines.append(str(default).lower())
        else:
            lines.append("false")

    elif schema_type == "null":
        lines.append("null")

    else:
        # Unknown type or anyOf/oneOf
        if "anyOf" in schema or "oneOf" in schema:
            lines.append('"value"')
        else:
            lines.append('""')

    return lines
