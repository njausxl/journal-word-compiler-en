from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run format-agent with a reviewed spec and template structure.")
    parser.add_argument("--engine-root", required=True, type=Path)
    parser.add_argument("--spec-json", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--template-rolemap-json", required=True, type=Path)
    parser.add_argument("--rolemap-json", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--allow-risky-structure", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(args.engine_root.resolve()))
    try:
        from core.agent import Agent
        from core.safe_output import write_json_atomic

        spec = json.loads(args.spec_json.read_text(encoding="utf-8"))
        rolemap = {
            int(key): value
            for key, value in json.loads(args.rolemap_json.read_text(encoding="utf-8")).items()
        }
        template_rolemap = {
            int(key): value
            for key, value in json.loads(
                args.template_rolemap_json.read_text(encoding="utf-8")
            ).items()
        }

        def event_printer(event):
            print(f"[{event.get('status', 'run')}] {event.get('step')}: {event.get('message')}")

        result = Agent(on_event=event_printer).run(
            target_path=str(args.target),
            out_path=str(args.out),
            spec=spec,
            template_path=str(args.template),
            template_rolemap=template_rolemap,
            rolemap=rolemap,
            report_path=str(args.report),
            cleanup_mode="preserve_emphasis",
            allow_risky_structure=args.allow_risky_structure,
        )
        base = os.path.splitext(str(args.out))[0]
        write_json_atomic(base + "_formatspec.json", result["spec"])
        write_json_atomic(
            base + "_rolemap.json",
            {str(key): value for key, value in sorted(result["rolemap"].items())},
        )
        write_json_atomic(base + "_stylemap.json", result["stylemap"])
        preflight = dict(result["preflight"])
        preflight["input_conversion"] = result.get("input_conversion")
        write_json_atomic(base + "_preflight.json", preflight)
        if result.get("issues"):
            write_json_atomic(base + "_issues.json", result["issues"])
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
