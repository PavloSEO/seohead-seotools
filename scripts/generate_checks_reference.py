#!/usr/bin/env python3
"""Write or verify docs/CHECKS.md, generated from seohead.sf.core.registry.CHECKS.

    python scripts/generate_checks_reference.py            # regenerate docs/CHECKS.md
    python scripts/generate_checks_reference.py --check     # exit 1 if it is stale (CI)

The rendering logic lives in seohead.sf.core.checks_reference so the same code path
that produces the committed file is what tests/test_docs_drift.py compares it against.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Run as a plain script (sys.path[0] is scripts/, not ROOT), so an editable
# install elsewhere on the machine could otherwise shadow this checkout's package.
sys.path.insert(0, str(ROOT))

from seohead.sf.core.checks_reference import render  # noqa: E402

TARGET = ROOT / "docs" / "CHECKS.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; fail if the committed file differs from what the registry produces",
    )
    args = parser.parse_args()

    content = render()
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None

    if args.check:
        if content != current:
            print(f"{TARGET} is stale: run 'python {sys.argv[0]}' and commit the result")
            return 1
        return 0

    if content != current:
        TARGET.write_text(content, encoding="utf-8")
        print(f"wrote {TARGET}")
    else:
        print(f"{TARGET} already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
