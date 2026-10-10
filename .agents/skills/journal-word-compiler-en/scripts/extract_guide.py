from __future__ import annotations

import argparse
from pathlib import Path

from build_profile import extract_guide_text, extract_rule_candidates
from common import dump_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract submission-guide text and conservative rule candidates.")
    parser.add_argument("--guide", required=True, type=Path)
    parser.add_argument("--text-out", required=True, type=Path)
    parser.add_argument("--candidates-out", required=True, type=Path)
    args = parser.parse_args()
    text = extract_guide_text(args.guide)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.write_text(text, encoding="utf-8")
    dump_json(args.candidates_out, extract_rule_candidates(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
