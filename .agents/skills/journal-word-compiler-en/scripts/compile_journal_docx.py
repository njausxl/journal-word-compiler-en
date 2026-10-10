from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_profile import build_profile
from build_rolemap import build_rolemap
from common import (
    dump_json,
    engine_root_default,
    ensure_engine,
    file_record,
    load_json,
    run_logged,
    utc_stamp,
    validate_ooxml_input,
)
from qa_gate import run_qa
from restore_emphasis import restore as restore_emphasis
from guide_compliance import evaluate as evaluate_guide_compliance


ATTRIBUTION = (
    "Formatting engine: Copyright 2026 KaguraNanaga; "
    "https://github.com/KaguraNanaga/format-agent-skill; "
    "PolyForm Noncommercial License 1.0.0."
)


def _copy_input(source: Path, destination_dir: Path, name: str | None = None) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / (name or source.name)
    shutil.copy2(source, target)
    return target


def _normalize_template(template: Path, inputs_dir: Path) -> Path:
    if template.suffix.lower() == ".docx":
        return _copy_input(template, inputs_dir, "journal-template.docx")
    if template.suffix.lower() != ".dotx":
        raise ValueError("Template must be .docx or .dotx")
    output = inputs_dir / "journal-template.docx"
    try:
        import win32com.client

        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        try:
            document = word.Documents.Open(str(template.resolve()), ReadOnly=True)
            try:
                document.SaveAs2(str(output.resolve()), FileFormat=16)
            finally:
                document.Close(False)
        finally:
            word.Quit()
    except Exception as word_error:
        soffice_candidates = [
            shutil.which("soffice.com"),
            shutil.which("soffice.exe"),
            r"C:\Program Files\LibreOffice\program\soffice.com",
        ]
        soffice = next(
            (item for item in soffice_candidates if item and Path(item).is_file()), None
        )
        if not soffice:
            raise RuntimeError(f"Unable to convert DOTX with Word; LibreOffice unavailable: {word_error}")
        completed = subprocess.run(
            [str(soffice), "--headless", "--convert-to", "docx", "--outdir", str(inputs_dir), str(template)],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=120,
        )
        converted = inputs_dir / (template.stem + ".docx")
        if completed.returncode != 0 or not converted.exists():
            raise RuntimeError(f"DOTX conversion failed: {completed.stdout}")
        if converted != output:
            converted.replace(output)
    validate_ooxml_input(output, {".docx"})
    return output


def _write_rolemap(
    document: Path,
    rolemap_path: Path,
    audit_path: Path,
    engine_root: Path,
    provided: Path | None,
    require_title: bool,
) -> dict[str, Any]:
    if provided:
        shutil.copy2(provided, rolemap_path)
        payload = {
            "document": str(document),
            "source": "user-provided",
            "warnings": [],
            "blockers": [],
            "role_counts": {},
        }
        dump_json(audit_path, payload)
        return payload
    rolemap, audit = build_rolemap(document, engine_root, require_title=require_title)
    dump_json(rolemap_path, {str(key): value for key, value in rolemap.items()})
    dump_json(audit_path, audit)
    return audit


def _preflight(
    python: str,
    main: Path,
    manuscript: Path,
    template: Path,
    diagnostics: Path,
    engine_root: Path,
) -> tuple[int, Path]:
    stub = diagnostics / "input_preflight.docx"
    command = [
        python,
        str(main),
        "--preflight-only",
        "--target",
        str(manuscript),
        "--template",
        str(template),
        "--out",
        str(stub),
    ]
    completed = run_logged(command, diagnostics / "preflight.log", cwd=engine_root)
    return completed.returncode, diagnostics / "input_preflight_preflight.json"


def _markdown_audit(payload: dict[str, Any]) -> str:
    qa = payload.get("qa", {})
    guide_compliance = payload.get("guide_compliance", {})
    lines = [
        "# English journal Word formatting audit",
        "",
        f"- Status: **{'PASS' if payload.get('overall_pass') else 'FAIL'}**",
        f"- Journal: {payload.get('journal')}",
        f"- Mode: {payload.get('mode')}",
        f"- Profile: `{payload.get('profile_dir')}`",
        f"- Engine exit code: {payload.get('engine_exit_code')}",
        f"- Text integrity: {'PASS' if qa.get('overall_pass') else 'FAIL'}",
        f"- Visual review required: {qa.get('visual_review_required', True)}",
        "",
        "## Role mapping",
        "",
        f"- Manuscript warnings: {len(payload.get('manuscript_role_audit', {}).get('warnings', []))}",
        f"- Manuscript blockers: {len(payload.get('manuscript_role_audit', {}).get('blockers', []))}",
        f"- Template warnings: {len(payload.get('template_role_audit', {}).get('warnings', []))}",
        "",
        "## QA gates",
        "",
        f"- DOCX ZIP integrity: {'PASS' if all(v.get('ok') for v in qa.get('zip_integrity', {}).values()) else 'FAIL'}",
        f"- Clean file has no format revisions: {qa.get('revisions', {}).get('clean_has_no_format_revisions')}",
        f"- Tracked pPrChange: {qa.get('revisions', {}).get('tracked_pPrChange')}",
        f"- Tracked rPrChange: {qa.get('revisions', {}).get('tracked_rPrChange')}",
        f"- Rendered pages: {len(qa.get('render', {}).get('pages', []))}",
        f"- Blank pages: {qa.get('render', {}).get('blank_pages', [])}",
        f"- Out-of-bounds text blocks: {len(qa.get('render', {}).get('out_of_bounds_blocks', []))}",
        "",
        "## Submission-guide content checks",
        "",
        f"- Observed abstract words: {guide_compliance.get('observed', {}).get('abstract_words')}",
        f"- Observed keyword count: {guide_compliance.get('observed', {}).get('keyword_count')}",
        f"- Unresolved content warnings: {len(guide_compliance.get('warnings', []))}",
        "",
        "## Scope and limitations",
        "",
        "- Formatting and approved block placement only; scientific wording and reference metadata were not rewritten.",
        "- Automatically extracted guide candidates were not applied unless a reviewed guide-rules JSON was supplied.",
        "- Render images must still receive a human or vision-model spot check before submission.",
        f"- {ATTRIBUTION}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile an English manuscript to an official journal Word template.")
    parser.add_argument("--journal", required=True)
    parser.add_argument("--manuscript", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--guide", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--mode", choices=("fresh", "resume"), default="fresh")
    parser.add_argument("--target-rolemap", type=Path)
    parser.add_argument("--template-rolemap", type=Path)
    parser.add_argument("--guide-rules", type=Path)
    parser.add_argument("--profile-store", type=Path, default=Path.home() / ".codex" / "journal_profiles_en")
    parser.add_argument("--engine-root", type=Path, default=engine_root_default())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--allow-risky-structure", action="store_true")
    parser.add_argument("--allow-role-warnings", action="store_true")
    args = parser.parse_args()

    args.manuscript = args.manuscript.resolve()
    args.template = args.template.resolve()
    args.guide = args.guide.resolve()
    args.out_dir = args.out_dir.resolve()
    args.profile_store = args.profile_store.resolve()
    args.engine_root = args.engine_root.resolve()
    if args.target_rolemap:
        args.target_rolemap = args.target_rolemap.resolve()
    if args.template_rolemap:
        args.template_rolemap = args.template_rolemap.resolve()
    if args.guide_rules:
        args.guide_rules = args.guide_rules.resolve()

    validate_ooxml_input(args.manuscript, {".docx"})
    validate_ooxml_input(args.template, {".docx", ".dotx"})
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    inputs = args.out_dir / "inputs"
    diagnostics = args.out_dir / "diagnostics"
    candidates = diagnostics / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    main_script = ensure_engine(args.engine_root)

    manuscript = _copy_input(args.manuscript, inputs, "manuscript-source.docx")
    template = _normalize_template(args.template, inputs)
    guide = _copy_input(args.guide, inputs, "submission-guide" + args.guide.suffix.lower())

    manifest = {
        "created_utc": utc_stamp(),
        "journal": args.journal,
        "mode": args.mode,
        "inputs": {
            "manuscript": file_record(args.manuscript),
            "template": file_record(args.template),
            "guide": file_record(args.guide),
        },
        "attribution": ATTRIBUTION,
    }
    dump_json(args.out_dir / "source-manifest.json", manifest)

    preflight_code, preflight_path = _preflight(
        args.python, main_script, manuscript, template, diagnostics, args.engine_root
    )
    if preflight_code != 0:
        failure = {**manifest, "overall_pass": False, "stage": "preflight", "exit_code": preflight_code}
        dump_json(args.out_dir / "failure.json", failure)
        return preflight_code

    target_rolemap = diagnostics / "target-rolemap.json"
    target_role_audit_path = diagnostics / "target-role-audit.json"
    target_audit = _write_rolemap(
        manuscript,
        target_rolemap,
        target_role_audit_path,
        args.engine_root,
        args.target_rolemap,
        require_title=True,
    )
    template_rolemap = diagnostics / "template-rolemap.json"
    template_role_audit_path = diagnostics / "template-role-audit.json"
    template_audit = _write_rolemap(
        template,
        template_rolemap,
        template_role_audit_path,
        args.engine_root,
        args.template_rolemap,
        require_title=False,
    )
    blockers = target_audit.get("blockers", []) + template_audit.get("blockers", [])
    if blockers:
        dump_json(args.out_dir / "failure.json", {**manifest, "stage": "rolemap", "blockers": blockers})
        return 6
    if not args.allow_role_warnings and target_audit.get("warnings"):
        dump_json(
            args.out_dir / "failure.json",
            {**manifest, "stage": "rolemap", "warnings": target_audit.get("warnings"), "action": "Review RoleMap or rerun with --allow-role-warnings"},
        )
        return 6

    profile_dir = build_profile(
        args.journal,
        template,
        guide,
        template_rolemap,
        args.profile_store,
        args.engine_root,
        args.guide_rules,
    )
    spec_path = profile_dir / "profile.json"
    guide_compliance = evaluate_guide_compliance(
        manuscript,
        target_rolemap,
        profile_dir / "rule-candidates.json",
        args.engine_root,
    )
    dump_json(args.out_dir / "guide-compliance.json", guide_compliance)
    candidate_clean = candidates / "manuscript_clean.docx"
    engine_report = diagnostics / "engine-report.md"
    bridge = Path(__file__).with_name("engine_bridge.py")
    command = [
        args.python,
        str(bridge),
        "--engine-root",
        str(args.engine_root),
        "--spec-json",
        str(spec_path),
        "--template",
        str(template),
        "--template-rolemap-json",
        str(template_rolemap),
        "--rolemap-json",
        str(target_rolemap),
        "--target",
        str(manuscript),
        "--out",
        str(candidate_clean),
        "--report",
        str(engine_report),
    ]
    if args.allow_risky_structure:
        command.append("--allow-risky-structure")
    completed = run_logged(command, diagnostics / "format-agent.log", cwd=args.engine_root)
    candidate_tracked = candidates / "manuscript_clean_tracked.docx"
    if completed.returncode != 0 or not candidate_clean.exists() or not candidate_tracked.exists():
        dump_json(
            args.out_dir / "failure.json",
            {**manifest, "stage": "format", "engine_exit_code": completed.returncode, "log": str(diagnostics / "format-agent.log")},
        )
        return completed.returncode or 7

    restored_tracked = candidates / "manuscript_tracked_emphasis_restored.docx"
    emphasis_restore = restore_emphasis(manuscript, candidate_tracked, restored_tracked)
    restored_tracked.replace(candidate_tracked)
    dump_json(diagnostics / "semantic-emphasis-restore.json", emphasis_restore)

    qa = run_qa(manuscript, candidate_clean, candidate_tracked, args.out_dir / "render")
    dump_json(args.out_dir / "integrity-report.json", qa)
    audit_payload = {
        **manifest,
        "overall_pass": bool(qa.get("overall_pass")),
        "engine_exit_code": completed.returncode,
        "profile_dir": str(profile_dir),
        "preflight": str(preflight_path),
        "manuscript_role_audit": target_audit,
        "template_role_audit": template_audit,
        "semantic_emphasis_restore": emphasis_restore,
        "guide_compliance": guide_compliance,
        "qa": qa,
    }
    dump_json(args.out_dir / "formatting-audit.json", audit_payload)
    (args.out_dir / "formatting_audit.md").write_text(_markdown_audit(audit_payload), encoding="utf-8")
    shutil.copy2(target_rolemap, args.out_dir / "rolemap.json")
    shutil.copy2(spec_path, args.out_dir / "format-spec.json")
    if preflight_path.exists():
        shutil.copy2(preflight_path, args.out_dir / "preflight.json")

    if not qa.get("overall_pass"):
        dump_json(args.out_dir / "failure.json", {**audit_payload, "stage": "qa"})
        return 3

    shutil.copy2(candidate_clean, args.out_dir / "manuscript_clean.docx")
    shutil.copy2(candidate_tracked, args.out_dir / "manuscript_tracked.docx")
    print(json.dumps({"status": "PASS", "output": str(args.out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
