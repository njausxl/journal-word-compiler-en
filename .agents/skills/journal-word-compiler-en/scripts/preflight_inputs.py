from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    dump_json,
    engine_root_default,
    ensure_engine,
    file_record,
    python_executable,
    run_logged,
    validate_ooxml_input,
)


def run_engine_preflight(
    target: Path,
    template: Path,
    output_stub: Path,
    engine_root: Path,
    log_path: Path,
) -> tuple[int, Path]:
    main = ensure_engine(engine_root)
    command = [
        python_executable(),
        str(main),
        "--preflight-only",
        "--target",
        str(target),
        "--template",
        str(template),
        "--out",
        str(output_stub),
    ]
    completed = run_logged(command, log_path, cwd=engine_root)
    report = output_stub.with_name(output_stub.stem + "_preflight.json")
    return completed.returncode, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight manuscript, template, and guide inputs.")
    parser.add_argument("--manuscript", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--guide", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--engine-root", type=Path, default=engine_root_default())
    args = parser.parse_args()

    validate_ooxml_input(args.manuscript, {".docx"})
    validate_ooxml_input(args.template, {".docx", ".dotx"})
    if args.guide.suffix.lower() not in {".pdf", ".docx", ".html", ".htm"}:
        raise ValueError("Guide must be PDF, DOCX, or saved HTML")
    if not args.guide.is_file():
        raise FileNotFoundError(args.guide)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    code, report_path = run_engine_preflight(
        args.manuscript,
        args.template,
        args.output_dir / "combined_preflight.docx",
        args.engine_root,
        args.output_dir / "preflight.log",
    )
    payload = {
        "inputs": {
            "manuscript": file_record(args.manuscript),
            "template": file_record(args.template),
            "guide": file_record(args.guide),
        },
        "engine_exit_code": code,
        "engine_report": str(report_path) if report_path.exists() else None,
    }
    if report_path.exists():
        payload["preflight"] = json.loads(report_path.read_text(encoding="utf-8"))
    dump_json(args.output_dir / "source-manifest.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
