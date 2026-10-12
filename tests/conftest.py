"""Hypothesis profiles.

CI is **derandomized**: the same examples every run, so a red check means a real regression
rather than a new seed. Locally the seeds vary, so a failure is a fresh sample to shrink.
`CI` is set by GitHub Actions.
"""

from __future__ import annotations

import os

from hypothesis import settings

# Only `derandomize` differs from the tests' own settings; everything a test states
# explicitly (max_examples, deadline, suppressions) still wins.
settings.register_profile("ci", derandomize=True)
settings.register_profile("local")
settings.load_profile("ci" if os.environ.get("CI") else "local")
