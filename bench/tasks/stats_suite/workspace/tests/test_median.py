import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stats import median

assert median([1, 2, 3]) == 2
# even length, average the two middle values
assert median([1, 2, 3, 4]) == 2.5
print("median ok")
