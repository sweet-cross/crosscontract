#!/usr/bin/env bash
# Run the tests against the lowest versions pyproject.toml allows for the direct
# dependencies, on the lowest supported Python. The environment is built in
# .venv-lowest, so .venv and uv.lock stay untouched.
#
# Usage, from the repository root: scripts/test_lowest_versions.sh [pytest args]
set -euo pipefail

uv venv .venv-lowest --python 3.11 --clear
uv pip install --python .venv-lowest/bin/python --resolution lowest-direct -e . --group dev
.venv-lowest/bin/python -m pytest "$@"
