from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "size": stat.st_size,
        "modified_utc": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "sha256": sha256_file(path),
    }


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "journal"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def zip_integrity(path: Path) -> tuple[bool, str | None]:
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
        return bad is None, bad
    except (OSError, zipfile.BadZipFile) as exc:
        return False, str(exc)


def validate_ooxml_input(path: Path, allowed: Iterable[str]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in set(allowed):
        raise ValueError(f"Unsupported input type: {path.suffix} ({path})")
    if path.suffix.lower() in {".docx", ".dotx"}:
        ok, detail = zip_integrity(path)
        if not ok:
            raise ValueError(f"Invalid OOXML ZIP: {path}: {detail}")


def run_logged(
    command: list[str], log_path: Path, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout or "", encoding="utf-8")
    return completed


def engine_root_default() -> Path:
    return Path.home() / ".codex" / "skills" / "format-agent-skill"


def ensure_engine(engine_root: Path) -> Path:
    main = engine_root / "main.py"
    if not main.is_file():
        raise FileNotFoundError(
            f"format-agent main.py not found at {main}. Install format-agent first."
        )
    return main


def python_executable() -> str:
    return sys.executable
