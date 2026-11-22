"""Import paths for the unit tests: tools/ and the runtime source.

Bytecode is not written, so a unit run leaves no __pycache__ in optional/runtime/ (the
installer's source tree).
"""

import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for sub in ("optional/runtime", "tools"):
    path = os.path.join(ROOT, sub)
    if path not in sys.path:
        sys.path.insert(0, path)
