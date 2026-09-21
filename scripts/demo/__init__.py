"""GenBI demo environment toolchain (Phase 27).

Two execution contexts share this package:

- Host mode (``python3 scripts/demo.py <cmd>``): stdlib-only orchestration
  of docker compose / psql / redis-cli. See ``demo.py`` and ``common.py``.
- In-container mode (``GENBI_DEMO_INTERNAL=1``): the same entry point runs
  inside the backend container where the app dependencies exist and does
  the DB-heavy seed/unseed work. See ``ops.py``.

``dataset.py`` is pure stdlib and safe to import from either context
(and from the offline test suite).
"""
