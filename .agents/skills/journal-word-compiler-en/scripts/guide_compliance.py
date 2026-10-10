from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from common import load_json


def _paragraphs(document: Path, engine_root: Path) -> list[dict[str, Any]]:
    sys.path.insert(0, str(engine_root))
    try:
        from docx import Document
        from core.extract import iter_main_paragraphs

        # format-agent's public extractor intentionally truncates ``text`` to
        # 80 characters because its records are prompts for role inference.
        # Compliance checks need the complete paragraph text, but must retain
        # exactly the same body/table reading order used by the role map.
        doc = Document(str(document))
        return [
            {"idx": idx, "text": paragraph.text.strip()}
            for idx, (paragraph, _depth) in enumerate(iter_main_paragraphs(doc))
        ]
    finally:
        try:
            sys.path.remove(str(engine_root))
        except ValueError:
            pass


def evaluate(
    document: Path,
    rolemap_path: Path,
    candidates_path: Path,
    engine_root: Path,
) -> dict[str, Any]:
    rolemap = {int(key): value for key, value in load_json(rolemap_path).items()}
    paragraphs = {int(item["idx"]): str(item.get("text") or "") for item in _paragraphs(document, engine_root)}
    abstract = " ".join(paragraphs[idx] for idx, role in rolemap.items() if role == "abstract_body")
    abstract = re.sub(r"^\s*abstract\s*[:.—-]\s*", "", abstract, flags=re.I)
    abstract_words = len(re.findall(r"\b[A-Za-z0-9][A-Za-z0-9'’-]*\b", abstract))
    keyword_text = " ".join(paragraphs[idx] for idx, role in rolemap.items() if role == "keywords")
    keyword_text = re.sub(r"^\s*key\s*words?\s*[:.—-]\s*", "", keyword_text, flags=re.I)
    keyword_count = len([item for item in re.split(r"[;,]", keyword_text) if item.strip()])

    checks = []
    for candidate in load_json(candidates_path):
        captures = candidate.get("captures", [])
        kind = candidate.get("kind")
        if kind == "abstract_words_max" and captures:
            maximum = int(float(captures[0]))
            checks.append(
                {
                    "kind": kind,
                    "observed": abstract_words,
                    "required": {"maximum": maximum},
                    "pass": abstract_words <= maximum,
                    "source_excerpt": candidate.get("source_excerpt"),
                    "action": "Author review required; content is not automatically shortened.",
                }
            )
        elif kind == "keywords_range" and len(captures) >= 2:
            minimum, maximum = int(captures[0]), int(captures[1])
            checks.append(
                {
                    "kind": kind,
                    "observed": keyword_count,
                    "required": {"minimum": minimum, "maximum": maximum},
                    "pass": minimum <= keyword_count <= maximum,
                    "source_excerpt": candidate.get("source_excerpt"),
                    "action": "Author review required; keywords are not automatically added or removed.",
                }
            )
        elif kind == "keywords_max" and captures:
            maximum = int(captures[0])
            checks.append(
                {
                    "kind": kind,
                    "observed": keyword_count,
                    "required": {"maximum": maximum},
                    "pass": keyword_count <= maximum,
                    "source_excerpt": candidate.get("source_excerpt"),
                    "action": "Author review required; keywords are not automatically removed.",
                }
            )
    return {
        "observed": {"abstract_words": abstract_words, "keyword_count": keyword_count},
        "checks": checks,
        "warnings": [check for check in checks if not check["pass"]],
        "all_checked_constraints_pass": all(check["pass"] for check in checks),
        "note": "These checks report content constraints but do not rewrite manuscript content.",
    }
