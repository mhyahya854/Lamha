from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description="Print one bounded Lamha work-package prompt.")
    sub = parser.add_subparsers(dest="action", required=True)
    prompt = sub.add_parser("prompt")
    prompt.add_argument("work_package_id")
    args = parser.parse_args()
    path = ROOT / "04-work-packages" / "packets" / f"{args.work_package_id}.md"
    if not path.is_file():
        parser.error(f"unknown work package: {args.work_package_id}")
    print(path.read_text(encoding="utf-8"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
