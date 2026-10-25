"""Built-in filesystem and serialization nodes."""

from __future__ import annotations

import csv
import json
from typing import Any

import yaml
from pydantic import Field

from nexus.core.context import NodeContext
from nexus.core.registry import NodeInput, node


class PathInput(NodeInput):
    path: str = Field(description="Path resolved relative to the run working directory.")


class ReadTextInput(PathInput):
    encoding: str = "utf-8"


@node("io.read_text", inputs=ReadTextInput, tags=["io"], description="Read a UTF-8 text file.")
def read_text(ctx: NodeContext, inputs: ReadTextInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    return {"text": path.read_text(encoding=inputs.encoding), "path": str(path)}


class WriteTextInput(PathInput):
    text: str
    encoding: str = "utf-8"
    mkdir: bool = True


@node("io.write_text", inputs=WriteTextInput, tags=["io"], description="Write a UTF-8 text file.")
def write_text(ctx: NodeContext, inputs: WriteTextInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    if inputs.mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(inputs.text, encoding=inputs.encoding)
    return {"path": str(path), "bytes": path.stat().st_size}


class ReadJsonInput(PathInput):
    pass


@node("io.read_json", inputs=ReadJsonInput, tags=["io", "json"], description="Read a JSON file.")
def read_json(ctx: NodeContext, inputs: ReadJsonInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    return {"data": json.loads(path.read_text(encoding="utf-8")), "path": str(path)}


class WriteJsonInput(PathInput):
    data: Any
    indent: int = 2
    mkdir: bool = True


@node("io.write_json", inputs=WriteJsonInput, tags=["io", "json"], description="Write a JSON file.")
def write_json(ctx: NodeContext, inputs: WriteJsonInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    if inputs.mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inputs.data, indent=inputs.indent, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "bytes": path.stat().st_size}


class ReadYamlInput(PathInput):
    pass


@node("io.read_yaml", inputs=ReadYamlInput, tags=["io", "yaml"], description="Read a YAML file.")
def read_yaml(ctx: NodeContext, inputs: ReadYamlInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    return {"data": yaml.safe_load(path.read_text(encoding="utf-8")), "path": str(path)}


class WriteYamlInput(PathInput):
    data: Any
    sort_keys: bool = False
    mkdir: bool = True


@node("io.write_yaml", inputs=WriteYamlInput, tags=["io", "yaml"], description="Write a YAML file.")
def write_yaml(ctx: NodeContext, inputs: WriteYamlInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    if inputs.mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(inputs.data, sort_keys=inputs.sort_keys, allow_unicode=True),
        encoding="utf-8",
    )
    return {"path": str(path), "bytes": path.stat().st_size}


class ReadJsonlInput(PathInput):
    pass


@node("io.read_jsonl", inputs=ReadJsonlInput, tags=["io", "json"], description="Read a JSON Lines file.")
def read_jsonl(ctx: NodeContext, inputs: ReadJsonlInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"rows": rows, "count": len(rows), "path": str(path)}


class WriteJsonlInput(PathInput):
    rows: list[Any]
    mkdir: bool = True


@node("io.write_jsonl", inputs=WriteJsonlInput, tags=["io", "json"], description="Write a JSON Lines file.")
def write_jsonl(ctx: NodeContext, inputs: WriteJsonlInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    if inputs.mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in inputs.rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"path": str(path), "count": len(inputs.rows)}


class ReadCsvInput(PathInput):
    delimiter: str = ","


@node("io.read_csv", inputs=ReadCsvInput, tags=["io", "csv"], description="Read a CSV file into a list of dictionaries.")
def read_csv(ctx: NodeContext, inputs: ReadCsvInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=inputs.delimiter)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return {"rows": rows, "count": len(rows), "fieldnames": fieldnames, "path": str(path)}


class WriteCsvInput(PathInput):
    rows: list[dict[str, Any]]
    fieldnames: list[str] | None = None
    delimiter: str = ","
    mkdir: bool = True


@node("io.write_csv", inputs=WriteCsvInput, tags=["io", "csv"], description="Write a list of dictionaries as CSV.")
def write_csv(ctx: NodeContext, inputs: WriteCsvInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    if inputs.mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = inputs.fieldnames or (list(inputs.rows[0].keys()) if inputs.rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=inputs.delimiter)
        writer.writeheader()
        for row in inputs.rows:
            writer.writerow(row)
    return {"path": str(path), "count": len(inputs.rows), "fieldnames": fieldnames}


class ListDirInput(PathInput):
    pattern: str = "*"
    recursive: bool = False


@node("io.list_dir", inputs=ListDirInput, tags=["io"], description="List files matching a glob pattern.")
def list_dir(ctx: NodeContext, inputs: ListDirInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    matches = path.rglob(inputs.pattern) if inputs.recursive else path.glob(inputs.pattern)
    paths = sorted(str(item) for item in matches if item.is_file())
    return {"paths": paths, "count": len(paths)}


class EnsureDirInput(NodeInput):
    path: str


@node("io.ensure_dir", inputs=EnsureDirInput, tags=["io"], description="Create a directory and its parents.")
def ensure_dir(ctx: NodeContext, inputs: EnsureDirInput) -> dict[str, Any]:
    path = ctx.ensure_dir(inputs.path)
    return {"path": str(path)}


class ExistsInput(PathInput):
    pass


@node("io.exists", inputs=ExistsInput, tags=["io"], description="Check whether a path exists.")
def exists(ctx: NodeContext, inputs: ExistsInput) -> dict[str, Any]:
    path = ctx.path(inputs.path)
    return {"exists": path.exists(), "is_file": path.is_file(), "is_dir": path.is_dir(), "path": str(path)}
