import os

assert not os.path.exists("obsolete.py"), "obsolete.py should be deleted"
assert os.path.isfile("main.py"), "main.py should be kept"
print("control delete ok")
