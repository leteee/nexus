"""Built-in node packs.

Importing this package registers the general-purpose nodes shipped with the
core engine.  Domain packs (``nexus.contrib.*``) are optional and are loaded
through config or entry points.
"""

from __future__ import annotations

from . import core, flow, io  # noqa: F401  (import side effects register nodes)

__all__: list[str] = []
