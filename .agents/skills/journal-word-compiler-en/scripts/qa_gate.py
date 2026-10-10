from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from common import dump_json, zip_integrity


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _read_xml(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def _story_texts(path: Path) -> dict[str, list[str]]:
    stories: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name == "word/document.xml"
            or name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}
        ]
        for name in names:
            root = _read_xml(archive, name)
            if root is None:
                continue
            paragraphs: list[str] = []
            for paragraph in root.iter(W + "p"):
                value = "".join(node.text or "" for node in paragraph.iter(W + "t"))
                if value:
                    paragraphs.append(value)
            stories[name] = paragraphs
    return stories


def _ooxml_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            root = _read_xml(archive, name)
            if root is None:
                continue
            for key, tag in {
                "pPrChange": W + "pPrChange",
                "rPrChange": W + "rPrChange",
                "ins": W + "ins",
                "del": W + "del",
                "commentReference": W + "commentReference",
                "footnoteReference": W + "footnoteReference",
                "endnoteReference": W + "endnoteReference",
                "bookmarkStart": W + "bookmarkStart",
                "drawing": W + "drawing",
                "object": W + "object",
                "field": W + "fldChar",
            }.items():
                counts[key] += sum(1 for _ in root.iter(tag))
    return counts


def _direct_emphasis(path: Path) -> Counter[tuple[str, str]]:
    emphasis: Counter[tuple[str, str]] = Counter()
    with zipfile.ZipFile(path) as archive:
        root = _read_xml(archive, "word/document.xml")
        if root is None:
            return emphasis
        for run in root.iter(W + "r"):
            text = "".join(node.text or "" for node in run.iter(W + "t"))
            if not text:
                continue
            properties = run.find(W + "rPr")
            if properties is None:
                continue
            flags = []
            bold = properties.find(W + "b")
            italic = properties.find(W + "i")
            false_values = {"0", "false", "off"}
            if bold is not None and str(bold.get(W + "val", "1")).lower() not in false_values:
                flags.append("bold")
            if italic is not None and str(italic.get(W + "val", "1")).lower() not in false_values:
                flags.append("italic")
            vertical = properties.find(W + "vertAlign")
            if vertical is not None:
                value = vertical.get(W + "val")
                if value in {"superscript", "subscript"}:
                    flags.append(value)
            if flags:
                structural_label = text.strip().lower().rstrip(".:")
                if flags == ["bold"] and structural_label in {
                    "abstract",
                    "keywords",
                    "key words",
                }:
                    continue
                emphasis[(text, "+".join(flags))] += 1
    return emphasis


def _find_soffice() -> str | None:
    candidates = [
        shutil.which("soffice.com"),
        shutil.which("soffice.exe"),
        shutil.which("soffice"),
        r"C:\Program Files\LibreOffice\program\soffice.com",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def render_docx(document: Path, render_dir: Path) -> dict[str, Any]:
    render_dir.mkdir(parents=True, exist_ok=True)
    soffice = _find_soffice()
    if not soffice:
        return {"ok": False, "error": "LibreOffice was not found"}
    completed = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(render_dir), str(document)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )
    pdf_path = render_dir / (document.stem + ".pdf")
    result: dict[str, Any] = {
        "ok": completed.returncode == 0 and pdf_path.is_file(),
        "exit_code": completed.returncode,
        "log": completed.stdout,
        "pdf": str(pdf_path) if pdf_path.is_file() else None,
        "pages": [],
        "blank_pages": [],
        "out_of_bounds_blocks": [],
    }
    if not result["ok"]:
        return result
    try:
        import fitz

        with fitz.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if not text and not page.get_images(full=True):
                    result["blank_pages"].append(page_number)
                for block in page.get_text("blocks"):
                    x0, y0, x1, y1 = block[:4]
                    rect = page.rect
                    if x0 < -1 or y0 < -1 or x1 > rect.width + 1 or y1 > rect.height + 1:
                        result["out_of_bounds_blocks"].append(
                            {"page": page_number, "box": [x0, y0, x1, y1]}
                        )
                pix = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
                image_path = render_dir / f"page-{page_number:02d}.png"
                pix.save(image_path)
                result["pages"].append(str(image_path))
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"PDF inspection failed: {exc}"
    return result


def run_qa(source: Path, clean: Path, tracked: Path, render_dir: Path) -> dict[str, Any]:
    zip_status = {}
    for path in (source, clean, tracked):
        ok, detail = zip_integrity(path)
        zip_status[path.name] = {"ok": ok, "detail": detail}

    source_text = _story_texts(source)
    clean_text = _story_texts(clean)
    tracked_text = _story_texts(tracked)
    compared_stories = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"]
    text_checks = {
        story: {
            "clean_exact": source_text.get(story, []) == clean_text.get(story, []),
            "tracked_exact": source_text.get(story, []) == tracked_text.get(story, []),
            "source_paragraphs": len(source_text.get(story, [])),
        }
        for story in compared_stories
    }

    source_counts = _ooxml_counts(source)
    clean_counts = _ooxml_counts(clean)
    tracked_counts = _ooxml_counts(tracked)
    protected_tags = [
        "commentReference",
        "footnoteReference",
        "endnoteReference",
        "bookmarkStart",
        "drawing",
        "object",
    ]
    protected_preserved = {
        tag: {
            "source": source_counts[tag],
            "clean": clean_counts[tag],
            "tracked": tracked_counts[tag],
            "ok": clean_counts[tag] >= source_counts[tag] and tracked_counts[tag] >= source_counts[tag],
        }
        for tag in protected_tags
    }
    revision_check = {
        "clean_pPrChange": clean_counts["pPrChange"],
        "clean_rPrChange": clean_counts["rPrChange"],
        "tracked_pPrChange": tracked_counts["pPrChange"],
        "tracked_rPrChange": tracked_counts["rPrChange"],
        "clean_has_no_format_revisions": clean_counts["pPrChange"] == 0 and clean_counts["rPrChange"] == 0,
    }
    source_emphasis = _direct_emphasis(source)
    clean_emphasis = _direct_emphasis(clean)
    tracked_emphasis = _direct_emphasis(tracked)
    missing_clean = {
        f"{text}|{flags}": count - clean_emphasis[(text, flags)]
        for (text, flags), count in source_emphasis.items()
        if clean_emphasis[(text, flags)] < count
    }
    missing_tracked = {
        f"{text}|{flags}": count - tracked_emphasis[(text, flags)]
        for (text, flags), count in source_emphasis.items()
        if tracked_emphasis[(text, flags)] < count
    }
    emphasis_check = {
        "source_direct_emphasis_runs": sum(source_emphasis.values()),
        "missing_in_clean": missing_clean,
        "missing_in_tracked": missing_tracked,
        "ok": not missing_clean and not missing_tracked,
    }
    render = render_docx(clean, render_dir)
    render_gate = (
        render.get("ok", False)
        and not render.get("blank_pages")
        and not render.get("out_of_bounds_blocks")
    )
    overall = (
        all(item["ok"] for item in zip_status.values())
        and all(item["clean_exact"] and item["tracked_exact"] for item in text_checks.values())
        and all(item["ok"] for item in protected_preserved.values())
        and revision_check["clean_has_no_format_revisions"]
        and emphasis_check["ok"]
        and render_gate
    )
    return {
        "overall_pass": overall,
        "zip_integrity": zip_status,
        "text_integrity": text_checks,
        "protected_objects": protected_preserved,
        "revisions": revision_check,
        "semantic_emphasis": emphasis_check,
        "render": render,
        "visual_review_required": True,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run DOCX integrity and render QA gates.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--clean", required=True, type=Path)
    parser.add_argument("--tracked", required=True, type=Path)
    parser.add_argument("--render-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run_qa(args.source, args.clean, args.tracked, args.render_dir)
    dump_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
