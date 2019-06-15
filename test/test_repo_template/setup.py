import os
from setuptools import setup

with open('asv_test_repo/build_time_env.py', 'w') as f:
    f.write("env = {{}}\n".format(repr(dict(os.environ))))

setup(name='asv_test_repo',
      version="{version}",
      packages=['asv_test_repo'],

      # The following forces setuptools to generate .egg-info directory,
      # which causes problems in test_environment.py:test_install_success
      include_package_data=True,
      )
