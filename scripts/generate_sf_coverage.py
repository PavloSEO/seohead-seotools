#!/usr/bin/env python3
"""Write or verify docs/COVERAGE_SF_ISSUES.md, generated from sf_issue_map.

python scripts/generate_sf_coverage.py            # regenerate
python scripts/generate_sf_coverage.py --check    # exit 1 if it is stale (CI)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seohead.sf.core.sf_coverage_reference import render  # noqa: E402

TARGET = ROOT / "docs" / "COVERAGE_SF_ISSUES.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify instead of writing")
    args = parser.parse_args()
    rendered = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if current != rendered:
            print(f"{TARGET} is stale: run scripts/generate_sf_coverage.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
