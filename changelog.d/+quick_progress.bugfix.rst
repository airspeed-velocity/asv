``asv run --quick`` no longer stops the progress report short of 100%. ``--quick``
forces one round per benchmark, but the progress total was still scaled by the
benchmarks' declared ``rounds``, so a completed run capped at 50% with the default
of two rounds.
