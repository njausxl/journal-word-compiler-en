---
name: journal-word-compiler-en
description: Compile or continue formatting English journal manuscripts in editable Word DOCX using an official DOCX/DOTX template and a supplied PDF/DOCX/HTML submission guide. Use for full formatting, partially formatted manuscript continuation, journal-template migration, clean plus tracked-format outputs, and auditable DOCX/render quality gates. Do not use to rewrite scientific content, repair citations, infer requirements from a journal name alone, or reproduce a PDF layout.
---

# English Journal Word Compiler

Produce an auditable clean DOCX, a tracked-format DOCX, and a formatting audit. Preserve scientific wording, citations, references, fields, comments, equations, images, and semantic emphasis.

## Required inputs

Require:

- manuscript `.docx`;
- official journal template `.docx` or `.dotx`;
- supplied submission guide `.pdf`, `.docx`, or saved `.html`;
- journal name.

Never overwrite the manuscript or template. Use `--mode resume` when the manuscript is already partly formatted; the compiler compares it with the target profile and records only necessary format changes.

## Workflow

1. Read [roles.md](references/roles.md) when role mapping is uncertain or the document uses unusual headings.
2. Extract the guide before compiling:

   ```powershell
   python scripts/extract_guide.py --guide GUIDE --text-out guide.txt --candidates-out rule-candidates.json
   ```

3. Review the extracted guide. Treat candidates as evidence, not rules. If the guide contains explicit rules that the template cannot express, create a reviewed FormatSpec override JSON following [profile-schema.md](references/profile-schema.md). Do not infer missing values.
4. Run the compiler in a new empty output directory:

   ```powershell
   python scripts/compile_journal_docx.py --journal "JOURNAL" --manuscript PAPER.docx --template TEMPLATE.docx --guide GUIDE.pdf --out-dir OUTPUT
   ```

   Add `--guide-rules reviewed-guide-rules.json` only after reviewing the guide. Add `--mode resume` for a partly formatted manuscript.
5. If role mapping stops on warnings or blockers, inspect `diagnostics/target-role-audit.json` and `diagnostics/target-rolemap.json`. Correct a copy and rerun with `--target-rolemap`; do not bypass a wrong title, abstract, heading, caption, or bibliography classification. Use `--allow-role-warnings` only when every warning is genuinely inapplicable.
6. Read [outputs-and-gates.md](references/outputs-and-gates.md). Deliver files only when `formatting-audit.json` and `integrity-report.json` both report pass, then visually inspect representative rendered pages.

## Safety rules

- Stop on unaccepted text insertions/deletions, macros, digital signatures, protection, unsafe structure, text loss, or critical low-confidence roles.
- Preserve compliant existing formatting in resume mode and retain semantic bold, italic, superscript, subscript, symbols, and equations unless an explicit reviewed journal rule overrides them.
- Move only complete approved front/back-matter blocks. Do not rewrite their text.
- Do not claim universal journal compliance. Report unresolved or conflicting requirements.
- Do not publish candidate files from `diagnostics/candidates` when a gate fails.

## Licensing and provenance

The formatting engine is source-available for permitted noncommercial use under PolyForm Noncommercial License 1.0.0.

Required Notice: Copyright 2026 KaguraNanaga. Original project: https://github.com/KaguraNanaga/format-agent-skill

Do not describe the engine as OSI-approved open source or licensed for commercial use. Preserve the notice and license terms in downstream distributions.
