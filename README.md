# Journal Word Compiler for English Manuscripts

An auditable Codex Skill for formatting English journal manuscripts from an
official Word template and a supplied submission guide.

It supports both complete reformatting and continuation from a partially
formatted manuscript. The compiler preserves manuscript text and produces:

- `manuscript_clean.docx` — clean formatted document;
- `manuscript_tracked.docx` — formatting changes recorded with Word revisions;
- `formatting_audit.md` and JSON diagnostics;
- rendered PDF/PNG pages for layout review.

## Important scope

This project formats documents. It does not rewrite scientific claims, repair
citations, or guarantee acceptance by a journal. Automatically extracted guide
rules remain candidates until reviewed. Final rendered pages still require a
human visual check.

The formatting engine is licensed under the PolyForm Noncommercial License
1.0.0. Use this repository only for purposes allowed by that license. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

## Requirements

- Codex CLI, Codex app, or another agent that supports filesystem Skills;
- Python 3.11 or newer;
- Git;
- [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)
  available as `soffice` for DOCX rendering and QA;
- [format-agent-skill](https://github.com/KaguraNanaga/format-agent-skill),
  installed at `~/.codex/skills/format-agent-skill` by default;
- Python packages listed in [requirements.txt](requirements.txt).

Microsoft Word is optional on Windows. It is preferred when converting `.dotx`
templates; LibreOffice is used as the fallback. `.docx` templates do not need
Word.

The current release has been end-to-end tested on Windows 11 with Word and
LibreOffice. The code detects `soffice` on Linux/macOS, but those platforms have
not yet received the same full visual regression test.

## Install

### Windows PowerShell

```powershell
git clone https://github.com/njausxl/journal-word-compiler-en.git
cd journal-word-compiler-en
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

### Linux or macOS

Install LibreOffice with your operating system's package manager, then run:

```bash
git clone https://github.com/njausxl/journal-word-compiler-en.git
cd journal-word-compiler-en
bash scripts/install.sh
```

The installers deliberately stop if `journal-word-compiler-en` already exists;
they do not overwrite a local Skill. Restart Codex if the newly installed Skill
does not appear immediately.

### Repository / Codex Cloud use

This repository already stores the Skill at:

```text
.agents/skills/journal-word-compiler-en/
```

Codex can discover repository Skills from that location. For a cloud task,
configure the environment first:

```bash
python -m pip install -r requirements.txt
git clone https://github.com/KaguraNanaga/format-agent-skill "$HOME/.codex/skills/format-agent-skill"
```

Also install LibreOffice in the cloud image if rendered QA is required. Merely
connecting the repository does not install system packages automatically.

## Use with Codex

Attach or place these inputs in the workspace:

1. manuscript `.docx`;
2. official journal template `.docx` or `.dotx`;
3. submission guide `.pdf`, `.docx`, or saved `.html`;
4. journal name.

Then ask:

```text
Use $journal-word-compiler-en to format my English manuscript from the supplied
official template and submission guide. Produce clean, tracked, and audit files.
```

For a manuscript that is already partly formatted:

```text
Use $journal-word-compiler-en in resume mode and continue the existing formatting.
Preserve compliant formatting and record only the necessary format changes.
```

## Direct command-line use

```bash
python ~/.codex/skills/journal-word-compiler-en/scripts/compile_journal_docx.py \
  --journal "Journal Name" \
  --manuscript paper.docx \
  --template journal-template.docx \
  --guide author-guide.pdf \
  --out-dir output
```

Add `--mode resume` for a partially formatted manuscript. Add
`--guide-rules reviewed-guide-rules.json` only after reviewing the extracted
guide candidates.

The output directory must be new or empty. Input manuscripts and templates are
never overwritten.

## Validation behavior

The compiler checks:

- DOCX ZIP integrity;
- exact preservation of visible manuscript, footnote, endnote, and comment text;
- preservation of protected objects and semantic emphasis;
- clean-versus-tracked revision state;
- blank pages and out-of-page text blocks after rendering;
- selected submission-guide constraints such as abstract word count and keyword
  count.

A formatting `PASS` can coexist with content warnings. For example, an abstract
may exceed the journal limit while the document formatting itself passes. The
compiler reports that condition but does not shorten the abstract.

## Repository layout

```text
.agents/skills/journal-word-compiler-en/  Codex Skill
scripts/install.ps1                       Windows installer
scripts/install.sh                        Linux/macOS installer
scripts/validate_repository.py            lightweight repository validation
requirements.txt                          Python dependencies
```

## License and attribution

This repository is distributed under the PolyForm Noncommercial License 1.0.0.

Required upstream notice:

> Copyright 2026 KaguraNanaga. Original project:
> https://github.com/KaguraNanaga/format-agent-skill

The upstream engine remains a separate dependency and retains its own copyright
and license terms.
