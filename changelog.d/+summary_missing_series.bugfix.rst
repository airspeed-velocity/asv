The landing-page summary graph no longer drops a series from its geometric mean when that series misses a commit.
Before, a slow machine that stopped running read as a speedup.
A short interior gap is still interpolated.
Any other gap after the first sample repeats the last measured value on later commits of the same branch.
A series stays empty until its first sample, and the fill never repeats a 0.
A retired machine or environment keeps its last value in the summary.
So does a parameter value that is still declared but no longer measured.
That held value can dilute a later real step.
Only real samples reach the per-machine graphs and regression detection.
