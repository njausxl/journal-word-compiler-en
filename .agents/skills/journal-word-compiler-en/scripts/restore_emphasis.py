from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree as ET

from common import dump_json


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{" + W_NS + "}"
def _run_text(run: ET.Element) -> str:
    return "".join(node.text or "" for node in run.iter(W + "t"))


def _semantic_properties(run: ET.Element) -> dict[str, str | bool]:
    properties = run.find(W + "rPr")
    if properties is None:
        return {}
    result: dict[str, str | bool] = {}
    text = _run_text(run).strip().lower().rstrip(".:")
    false_values = {"0", "false", "off"}
    italic = properties.find(W + "i")
    bold = properties.find(W + "b")
    if italic is not None and str(italic.get(W + "val", "1")).lower() not in false_values:
        result["italic"] = True
    if (
        bold is not None
        and str(bold.get(W + "val", "1")).lower() not in false_values
        and text not in {
        "abstract",
        "keywords",
        "key words",
        }
    ):
        result["bold"] = True
    vertical = properties.find(W + "vertAlign")
    if vertical is not None:
        value = vertical.get(W + "val")
        if value in {"superscript", "subscript"}:
            result["vertAlign"] = value
    return result


def _ensure_rpr(run: ET.Element) -> ET.Element:
    properties = run.find(W + "rPr")
    if properties is None:
        properties = ET.Element(W + "rPr")
        run.insert(0, properties)
    return properties


RPR_ORDER = {
    name: index
    for index, name in enumerate(
        "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint "
        "noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect "
        "bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange".split()
    )
}


def _insert_ordered(properties: ET.Element, child: ET.Element) -> None:
    child_name = child.tag.split("}")[-1]
    child_order = RPR_ORDER.get(child_name, len(RPR_ORDER) - 1)
    for index, existing in enumerate(list(properties)):
        existing_name = existing.tag.split("}")[-1]
        if RPR_ORDER.get(existing_name, len(RPR_ORDER)) > child_order:
            properties.insert(index, child)
            return
    properties.append(child)


def _apply_properties(run: ET.Element, semantic: dict[str, str | bool]) -> int:
    properties = _ensure_rpr(run)
    changed = 0
    false_values = {"0", "false", "off"}
    if semantic.get("bold"):
        bold = properties.find(W + "b")
        if bold is None:
            _insert_ordered(properties, ET.Element(W + "b"))
            changed += 1
        elif str(bold.get(W + "val", "1")).lower() in false_values:
            bold.set(W + "val", "1")
            changed += 1
    if semantic.get("italic"):
        italic = properties.find(W + "i")
        if italic is None:
            _insert_ordered(properties, ET.Element(W + "i"))
            changed += 1
        elif str(italic.get(W + "val", "1")).lower() in false_values:
            italic.set(W + "val", "1")
            changed += 1
    vertical_value = semantic.get("vertAlign")
    vertical = properties.find(W + "vertAlign")
    if vertical_value and (vertical is None or vertical.get(W + "val") != vertical_value):
        if vertical is None:
            vertical = ET.Element(W + "vertAlign")
            _insert_ordered(properties, vertical)
        vertical.set(W + "val", str(vertical_value))
        changed += 1
    return changed


def _paragraph_runs(paragraph: ET.Element) -> list[tuple[ET.Element, int, int]]:
    result = []
    offset = 0
    for run in paragraph.iter(W + "r"):
        text = _run_text(run)
        if not text:
            continue
        result.append((run, offset, offset + len(text)))
        offset += len(text)
    return result


def restore(source: Path, tracked: Path, output: Path) -> dict[str, int | bool]:
    with zipfile.ZipFile(source) as archive:
        source_root = ET.fromstring(archive.read("word/document.xml"))
    with zipfile.ZipFile(tracked) as archive:
        tracked_root = ET.fromstring(archive.read("word/document.xml"))

    source_paragraphs = list(source_root.iter(W + "p"))
    tracked_paragraphs = list(tracked_root.iter(W + "p"))
    if len(source_paragraphs) != len(tracked_paragraphs):
        raise ValueError("Paragraph counts differ; cannot safely restore semantic emphasis")

    restored = 0
    semantic_runs = 0
    for source_paragraph, tracked_paragraph in zip(source_paragraphs, tracked_paragraphs):
        source_text = "".join(node.text or "" for node in source_paragraph.iter(W + "t"))
        tracked_text = "".join(node.text or "" for node in tracked_paragraph.iter(W + "t"))
        if source_text != tracked_text:
            raise ValueError("Paragraph text differs; cannot safely restore semantic emphasis")
        tracked_runs = _paragraph_runs(tracked_paragraph)
        for source_run, start, end in _paragraph_runs(source_paragraph):
            semantic = _semantic_properties(source_run)
            if not semantic:
                continue
            semantic_runs += 1
            for tracked_run, tracked_start, tracked_end in tracked_runs:
                if tracked_end <= start or tracked_start >= end:
                    continue
                restored += _apply_properties(tracked_run, semantic)

    output.parent.mkdir(parents=True, exist_ok=True)
    if restored == 0:
        shutil.copy2(tracked, output)
        return {
            "semantic_source_runs": semantic_runs,
            "properties_restored": 0,
            "ok": True,
        }
    updated_xml = ET.tostring(
        tracked_root, encoding="utf-8", xml_declaration=True, standalone=True
    )
    fd, temporary_name = tempfile.mkstemp(suffix=".docx", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(tracked) as source_archive, zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED
        ) as target_archive:
            for item in source_archive.infolist():
                data = updated_xml if item.filename == "word/document.xml" else source_archive.read(item.filename)
                target_archive.writestr(item, data)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"semantic_source_runs": semantic_runs, "properties_restored": restored, "ok": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore semantic run emphasis in a tracked-format DOCX.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--tracked", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    result = restore(args.source, args.tracked, args.output)
    dump_json(args.audit, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
