"""AegisCode mechanism demos (SPEC §16.4 / §A.6).

Four self-contained, zero-network demonstrations that each exercise a REAL
governance / harness / approval mechanism from the shipped ``aegiscode``
package. They deliberately do NOT import from ``tests`` (the test tree is
excluded from the Docker build context via ``.dockerignore``), so each demo
wires its own minimal spy tools / real components inline and depends only on
``aegiscode`` + the Python standard library.

Run them all via ``aegiscode demo``; run one standalone via e.g.
``python demos/demo1_dangerous_denied.py``.
"""
