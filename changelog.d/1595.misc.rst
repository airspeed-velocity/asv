Require ``asv-runner>=0.2.5`` so environments get timeraw stderr capture,
SHA-256-compatible default benchmark versions with optional token
``version_alts`` backfill, and ``setup_cache``/skip/``env`` fixes.
Avoids 0.2.2–0.2.4 regressions (swallowed timeraw stderr; token-only
``version`` breaking discovery tests / result identity).
