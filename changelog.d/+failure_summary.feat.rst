``asv run`` now prints a summary of failed benchmarks at the end of the run, in the
style of ``pytest``'s short test summary (#1201). Failures were previously only visible
at the point they occurred, which is easy to miss in a long log and is often truncated
away entirely by CI log size limits. A failed build is reported once rather than once
per benchmark.
