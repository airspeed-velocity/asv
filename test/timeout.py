#!/usr/bin/env python

import sys
import time

sys.stdout.write("Stdout before waiting\n")
sys.stderr.write("Stderr before waiting\n")
time.sleep(60)
sys.stdout.write("Stdout after waiting\n")
sys.stderr.write("Stderr after waiting\n")
