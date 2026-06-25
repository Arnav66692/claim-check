import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stats import mean

assert mean([1, 2, 3, 4]) == 2.5
assert mean([10]) == 10
print("mean ok")
