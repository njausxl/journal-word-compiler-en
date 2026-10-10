from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from common import dump_json, engine_root_default, ensure_engine


EXACT_HEADINGS = {
    "abstract": "abstract_heading",
    "summary": "abstract_heading",
    "keywords": "keywords",
    "key words": "keywords",
    "references": "bibliography_heading",
    "bibliography": "bibliography_heading",
    "literature cited": "bibliography_heading",
    "works cited": "bibliography_heading",
    "acknowledgments": "heading_1",
    "acknowledgements": "heading_1",
    "author contributions": "heading_1",
    "funding": "heading_1",
    "conflict of interest": "heading_1",
    "conflicts of interest": "heading_1",
    "competing interests": "heading_1",
    "data availability": "heading_1",
    "data availability statement": "heading_1",
    "supplementary materials": "heading_1",
    "introduction": "heading_1",
    "materials and methods": "heading_1",
    "methods": "heading_1",
    "results": "heading_1",
    "discussion": "heading_1",
    "conclusions": "heading_1",
    "conclusion": "heading_1",
}

TITLE_PLACEHOLDERS = {
    "title",
    "article title",
    "manuscript title",
    "title of manuscript",
    "insert title here",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).strip(" :.-").lower()


def _load_paragraphs(document: Path, engine_root: Path) -> list[dict[str, Any]]:
    ensure_engine(engine_root)
    sys.path.insert(0, str(engine_root))
    try:
        from core.extract import extract_paragraphs

        return extract_paragraphs(str(document))
    finally:
        try:
            sys.path.remove(str(engine_root))
        except ValueError:
            pass


def _style_heading_level(paragraph: dict[str, Any]) -> int | None:
    style = str(paragraph.get("style_name") or "").lower()
    outline = paragraph.get("outline_level")
    if isinstance(outline, int) and 0 <= outline <= 3:
        return outline + 1
    match = re.search(r"(?:heading|head|title)[ _-]*([1-4])", style)
    if match:
        return int(match.group(1))
    return None


def _numbered_heading_level(text: str) -> int | None:
    match = re.match(r"^\s*(\d+(?:\.\d+){0,3})[.)]?\s+\S", text)
    if not match:
        return None
    return min(match.group(1).count(".") + 1, 4)


def build_rolemap(
    document: Path, engine_root: Path, require_title: bool = True
) -> tuple[dict[int, str], dict[str, Any]]:
    paragraphs = _load_paragraphs(document, engine_root)
    editable = [
        p
        for p in paragraphs
        if p.get("editable", True) and not p.get("in_table", False)
    ]
    rolemap: dict[int, str] = {}
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []

    nonempty = [p for p in editable if str(p.get("text") or "").strip()]
    first_idx = nonempty[0]["idx"] if nonempty else None
    bibliography_mode = False
    abstract_mode = False
    title_idx: int | None = None
    abstract_seen = False
    keywords_seen = False

    for p in editable:
        idx = int(p["idx"])
        text = str(p.get("text") or "").strip()
        norm = _norm(text)
        style = str(p.get("style_name") or "").lower()
        role = "body" if text else "other"
        confidence = "medium"
        reason = "default body fallback" if text else "empty paragraph"

        if bibliography_mode and text:
            role, confidence, reason = (
                "bibliography_entry",
                "high",
                "after bibliography heading",
            )
        elif re.match(r"^(fig(?:ure)?\.?\s*\d+|supp(?:lementary)?\.?\s*fig)", text, re.I):
            role, confidence, reason = "figure_caption", "high", "caption prefix"
        elif re.match(r"^(table\s*\d+|supp(?:lementary)?\.?\s*table)", text, re.I):
            role, confidence, reason = "table_caption", "high", "caption prefix"
        elif norm in EXACT_HEADINGS:
            role = EXACT_HEADINGS[norm]
            confidence, reason = "high", "exact academic heading"
            if role == "bibliography_heading":
                bibliography_mode = True
                abstract_mode = False
            elif role == "abstract_heading":
                abstract_mode = True
                abstract_seen = True
            elif role == "keywords":
                abstract_mode = False
                keywords_seen = True
        elif re.match(r"^abstract\s*[:.—-]", text, re.I):
            role, confidence, reason = "abstract_body", "high", "inline abstract prefix"
            abstract_mode = True
            abstract_seen = True
        elif re.match(r"^(key\s*words?|keywords?)\s*[:.—-]", text, re.I):
            role, confidence, reason = "keywords", "high", "keywords prefix"
            abstract_mode = False
            keywords_seen = True
        elif abstract_mode and text:
            role, confidence, reason = "abstract_body", "high", "abstract section continuation"
        else:
            heading_level = _style_heading_level(p) or _numbered_heading_level(text)
            if heading_level:
                role = f"heading_{heading_level}"
                confidence, reason = "high", "heading style/numbering"
                abstract_mode = False
            elif (
                idx == first_idx
                and ("title" in style or norm in TITLE_PLACEHOLDERS or p.get("alignment") == "center")
            ):
                role, confidence, reason = "title", "high", "first title-like paragraph"
                title_idx = idx
            elif norm in TITLE_PLACEHOLDERS:
                role, confidence, reason = "title", "high", "title placeholder"
                title_idx = idx
            elif "author" in style or "byline" in style or norm in {"authors", "author names"}:
                role, confidence, reason = "byline", "high", "author style/placeholder"
            elif "affiliation" in style or norm in {"affiliation", "affiliations", "author affiliation"}:
                role, confidence, reason = "affiliation", "high", "affiliation style/placeholder"
            elif re.match(r"^(corresponding author|correspondence)\b", text, re.I):
                role, confidence, reason = "correspondence", "high", "correspondence prefix"
            elif title_idx is not None and idx > title_idx and not abstract_seen:
                if p.get("alignment") == "center" and len(text) <= 250:
                    previous_roles = [rolemap.get(q["idx"]) for q in editable if q["idx"] < idx]
                    role = "byline" if "byline" not in previous_roles else "affiliation"
                    confidence, reason = "medium", "centered front-matter paragraph"

        rolemap[idx] = role
        evidence.append(
            {
                "idx": idx,
                "role": role,
                "confidence": confidence,
                "reason": reason,
                "text_preview": text[:160],
                "style": p.get("style_name"),
            }
        )

    if require_title and editable and "title" not in rolemap.values():
        blockers.append("No high-confidence manuscript title was identified.")
    if not abstract_seen:
        warnings.append("No explicit Abstract heading or inline Abstract prefix was identified.")
    if not keywords_seen:
        warnings.append("No explicit Keywords paragraph was identified.")
    if "bibliography_heading" not in rolemap.values():
        warnings.append("No bibliography heading was identified.")

    audit = {
        "document": str(document.resolve()),
        "paragraph_records": len(paragraphs),
        "mapped_editable_non_table": len(editable),
        "role_counts": dict(Counter(rolemap.values())),
        "warnings": warnings,
        "blockers": blockers,
        "evidence": evidence,
    }
    return rolemap, audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic English academic RoleMap.")
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--engine-root", type=Path, default=engine_root_default())
    parser.add_argument("--allow-missing-title", action="store_true")
    args = parser.parse_args()

    rolemap, audit = build_rolemap(
        args.document, args.engine_root, require_title=not args.allow_missing_title
    )
    dump_json(args.output, {str(k): v for k, v in rolemap.items()})
    dump_json(args.audit, audit)
    print(json.dumps({"output": str(args.output), "blockers": audit["blockers"]}, ensure_ascii=False))
    return 2 if audit["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
