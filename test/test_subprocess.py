from asv import util
import subprocess

try:
    util.check_output(["./timeout.py"], timeout=5)
except util.ProcessError as e:
    assert len(e.stdout.strip().split('\n')) == 1

try:
    util.check_output(["./timeout_with_output.py"], timeout=5)
except util.ProcessError as e:
    assert len(e.stdout.strip().split('\n')) == 2
