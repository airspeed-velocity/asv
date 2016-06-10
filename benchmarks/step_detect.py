try:
    from asv import step_detect
except ImportError:
    pass


class Simple:
    def setup(self):
        self.y = ([1]*20 + [2]*30)*50

    def time_detect_regressions(self):
        step_detect.detect_regressions(self.y)

    def time_solve_potts_approx(self):
        step_detect.solve_potts_approx(self.y, 0.3, p=1)
