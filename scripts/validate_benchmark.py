"""Backward-compatible benchmark validation command used by CI/Makefile."""

from __future__ import annotations

import json

from validate_evaluation_assets import validate


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
