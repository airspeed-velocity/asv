from asv.environment import Environment

print("Imported custom environment")


class MyEnvironment(Environment):
    tool_name = "myenv"
    def __init__(self, conf, python, requirements, tagged_env_vars):
        """
        Parameters
        ----------
        conf : Config instance

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        self._python = python
        self._requirements = requirements
        self._channels = conf.conda_channels
        self._environment_file = None
        super(MyEnvironment, self).__init__(conf, python, requirements, tagged_env_vars)
