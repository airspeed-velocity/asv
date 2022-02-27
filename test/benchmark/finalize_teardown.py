# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst


class FinalizeTeardownSetupTest:
    def setup(self, n):
        raise ValueError("Setup fails")

    def time_it(self, n):
        pass

    def finalize_teardown(self, exc_type, exc, trace):
        assert exc_type == ValueError
        assert str(exc) == "Setup fails"
        assert trace is not None


class FinalizeTeardownTeardownTest:
    def teardown(self, n):
        raise NotImplementedError("Teardown fails")

    def time_it(self, n):
        pass

    def finalize_teardown(self, exc_type, exc, trace):
        assert exc_type == NotImplementedError
        assert str(exc) == "Teardown fails"
        assert trace is not None
