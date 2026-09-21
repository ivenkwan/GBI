"""Offline tests for the demo environment toolchain (Phase 27, Task 146).

No Docker, no database: these exercise the pure-stdlib pieces — the
deterministic dataset, the reset env-key preservation, and the demo-tenant
marker parsing. Live-stack behavior is verified separately (Task 147).
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
