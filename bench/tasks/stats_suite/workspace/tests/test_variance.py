import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stats import variance

# sample variance, divide by n minus 1
assert variance([2, 4, 6]) == 4.0
assert variance([1, 1, 1]) == 0.0
print("variance ok")
