import importlib
import os

assert os.path.isfile("greeting.py"), "greeting.py was not created"
greeting = importlib.import_module("greeting")
assert greeting.hello() == "hello"
print("control create ok")
