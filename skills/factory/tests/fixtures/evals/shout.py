"""Toy end-to-end SUT: uppercase stdin and report a deterministic cost."""

import sys


sys.stdout.write(sys.stdin.read().upper() + "!")
sys.stderr.write("factory-cost: 0.001\n")
