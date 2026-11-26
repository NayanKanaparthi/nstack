"""Echo stdin exactly, prefixed for input-contract assertions."""

import sys


sys.stdout.write("echo:" + sys.stdin.read())
