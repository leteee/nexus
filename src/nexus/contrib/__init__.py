"""Optional built-in node packs.

``nexus.contrib.repro`` requires the ``repro`` extra and is loaded only when
configured or installed as an entry point.  General-purpose example/test logic
should live in a separate project package registered via ``node_modules`` or a
``nexus.nodes`` entry point, not in this namespace.
"""
