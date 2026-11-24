import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("tests"))
if not result.wasSuccessful():
    raise SystemExit(1)
print("WORKFLOW TESTS OK")
