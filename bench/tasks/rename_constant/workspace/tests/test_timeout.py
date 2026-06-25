import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TIMEOUT

assert DEFAULT_TIMEOUT == 30
print("timeout test ok")
