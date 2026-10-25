"""Built-in general-purpose nodes."""

from __future__ import annotations

import importlib
import logging
import shlex
import subprocess
import time
from typing import Any

from pydantic import Field

from nexus.core.context import NodeContext
from nexus.core.registry import NodeInput, node

logger = logging.getLogger(__name__)


class NoopInput(NodeInput):
    """No inputs."""


@node("core.noop", inputs=NoopInput, tags=["core"], description="Do nothing and return an empty result.")
def noop(ctx: NodeContext, inputs: NoopInput) -> dict[str, Any]:
    return {}


class EchoInput(NodeInput):
    value: Any = Field(default=None, description="Value returned unchanged as `value`.")


@node("core.echo", inputs=EchoInput, tags=["core"], description="Return the input value unchanged.")
def echo(ctx: NodeContext, inputs: EchoInput) -> dict[str, Any]:
    return {"value": inputs.value}


class PythonCallInput(NodeInput):
    target: str = Field(
        description="Python callable as 'package.module:function' or 'package.module.function'.",
    )
    args: list[Any] = Field(default_factory=list, description="Positional arguments.")
    kwargs: dict[str, Any] = Field(default_factory=dict, description="Keyword arguments.")
    pass_context: bool = Field(
        default=False,
        description="When true, the NodeContext is passed as the first positional argument.",
    )


@node(
    "core.python",
    inputs=PythonCallInput,
    tags=["core", "python"],
    description="Import and call any Python function with resolved arguments.",
)
def call_python(ctx: NodeContext, inputs: PythonCallInput) -> dict[str, Any]:
    module_name, separator, attribute = inputs.target.partition(":")
    if not separator:
        module_name, separator, attribute = inputs.target.rpartition(".")
    if not module_name or not attribute:
        raise ValueError(
            f"invalid target '{inputs.target}'; expected 'package.module:function' or 'package.module.function'"
        )

    module = importlib.import_module(module_name)
    target = module
    for part in attribute.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"target '{inputs.target}' is not callable")

    args = ([ctx] if inputs.pass_context else []) + list(inputs.args)
    logger.debug("Calling Python target %s", inputs.target)
    result = target(*args, **inputs.kwargs)
    return {"result": result}


class ShellInput(NodeInput):
    command: str | list[str] = Field(description="Command string or argv list.")
    cwd: str | None = Field(default=None, description="Working directory, relative to the run workdir.")
    env: dict[str, str] = Field(default_factory=dict, description="Extra environment variables.")
    shell: bool = Field(default=False, description="Run through the system shell (string commands only).")
    check: bool = Field(default=True, description="Raise when the process exits non-zero.")
    capture: bool = Field(default=True, description="Capture stdout/stderr.")
    timeout_s: float | None = Field(default=None, gt=0, description="Process timeout.")

    def argv(self) -> str | list[str]:
        if isinstance(self.command, str) and not self.shell:
            return shlex.split(self.command)
        return self.command


@node(
    "core.shell",
    inputs=ShellInput,
    tags=["core", "shell"],
    description="Execute a subprocess and return its exit code and captured output.",
)
def shell(ctx: NodeContext, inputs: ShellInput) -> dict[str, Any]:
    import os

    cwd = ctx.path(inputs.cwd) if inputs.cwd else ctx.workdir
    env = {**os.environ, **inputs.env}
    completed = subprocess.run(
        inputs.argv(),
        cwd=str(cwd),
        env=env,
        shell=inputs.shell,
        capture_output=inputs.capture,
        text=True,
        timeout=inputs.timeout_s,
        check=False,
    )
    result = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if inputs.check and completed.returncode != 0:
        raise RuntimeError(
            f"command exited with code {completed.returncode}: {(completed.stderr or completed.stdout or '').strip()}"
        )
    return result


class AssertInput(NodeInput):
    condition: Any = Field(description="Value that must be truthy.")
    message: str = Field(default="assertion failed", description="Error message when the condition is false.")


@node("core.assert", inputs=AssertInput, tags=["core"], description="Fail the step when a condition is false.")
def assert_condition(ctx: NodeContext, inputs: AssertInput) -> dict[str, Any]:
    if not inputs.condition:
        raise AssertionError(inputs.message)
    return {"ok": True}


class FailInput(NodeInput):
    message: str = Field(default="intentional failure", description="Failure message.")
    code: int = Field(default=1, description="Optional numeric code included in the result.")


@node("core.fail", inputs=FailInput, tags=["core"], description="Fail the step intentionally.")
def fail(ctx: NodeContext, inputs: FailInput) -> dict[str, Any]:
    raise RuntimeError(f"{inputs.message} (code={inputs.code})")


class SleepInput(NodeInput):
    seconds: float = Field(ge=0, description="Seconds to sleep.")


@node("core.sleep", inputs=SleepInput, tags=["core"], description="Sleep for a number of seconds.")
def sleep(ctx: NodeContext, inputs: SleepInput) -> dict[str, Any]:
    time.sleep(inputs.seconds)
    return {"slept_s": inputs.seconds}


class LogInput(NodeInput):
    message: str = Field(description="Message to log.")
    level: str = Field(default="info", description="debug, info, warning or error.")


@node("core.log", inputs=LogInput, tags=["core"], description="Write a message to the run log.")
def log_message(ctx: NodeContext, inputs: LogInput) -> dict[str, Any]:
    level = inputs.level.lower()
    log_method = getattr(logger, level, None)
    if log_method is None:
        raise ValueError(f"unknown log level '{inputs.level}'")
    log_method(inputs.message)
    return {"message": inputs.message, "level": level}
