#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
python_bin="${PYTHON:-python3}"
skills_root="$codex_home/skills"
source_skill="$repo_root/.agents/skills/journal-word-compiler-en"
target_skill="$skills_root/journal-word-compiler-en"
engine_root="$skills_root/format-agent-skill"

if [[ ! -d "$source_skill" ]]; then
  echo "Skill source not found: $source_skill" >&2
  exit 1
fi
if [[ -e "$target_skill" ]]; then
  echo "Refusing to overwrite existing Skill: $target_skill" >&2
  exit 1
fi

mkdir -p "$skills_root"
"$python_bin" -m pip install -r "$repo_root/requirements.txt"

if [[ ! -d "$engine_root" ]]; then
  git clone https://github.com/KaguraNanaga/format-agent-skill "$engine_root"
fi

cp -R "$source_skill" "$target_skill"

if ! command -v soffice >/dev/null 2>&1; then
  echo "Warning: LibreOffice was not found. Install it before running rendered QA." >&2
fi

echo "Installed journal-word-compiler-en to $target_skill"
echo "Restart Codex if the Skill is not detected automatically."
