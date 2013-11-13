#!/usr/bin/env python

import sys
import time

sys.stdout.write("Stdout 1\n")
sys.stderr.write("Stderr 1\n")
time.sleep(1)
sys.stdout.write("Stdout 2\n")
sys.stderr.write("Stderr 2\n")
time.sleep(60)
sys.stdout.write("Stdout after waiting\n")
sys.stderr.write("Stderr after waiting\n")
