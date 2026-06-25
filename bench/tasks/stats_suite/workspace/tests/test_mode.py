import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stats import mode

assert mode([1, 1, 2, 3]) == 1
# two values tie for most frequent, pick the smallest
assert mode([4, 4, 2, 2, 9]) == 2
print("mode ok")
