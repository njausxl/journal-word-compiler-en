from __future__ import annotations

import compileall
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "journal-word-compiler-en"


def main() -> int:
    required = [
        SKILL / "SKILL.md",
        SKILL / "agents" / "openai.yaml",
        SKILL / "scripts" / "compile_journal_docx.py",
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "NOTICE",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        print("Missing required files:", ", ".join(missing), file=sys.stderr)
        return 1

    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print("SKILL.md has no YAML frontmatter", file=sys.stderr)
        return 1
    if not re.search(r"(?m)^name:\s*journal-word-compiler-en\s*$", text):
        print("Unexpected Skill name", file=sys.stderr)
        return 1
    if not re.search(r"(?m)^description:\s*\S", text):
        print("Skill description is missing", file=sys.stderr)
        return 1
    if not compileall.compile_dir(SKILL / "scripts", quiet=1):
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
