# Outputs and quality gates

## Contents

1. Primary deliverables
2. Hard gates
3. Render review
4. Failure handling

## 1. Primary deliverables

- `manuscript_clean.docx`: clean formatted manuscript.
- `manuscript_tracked.docx`: formatting-property revisions.
- `formatting_audit.md`: human-readable audit.

Machine evidence includes `preflight.json`, `rolemap.json`, `format-spec.json`, `integrity-report.json`, `formatting-audit.json`, and rendered PDF/page images.

## 2. Hard gates

Require valid DOCX ZIP packages, exact body/footnote/endnote/comment text preservation, no loss of protected objects, no format revisions in the clean file, successful PDF rendering, no blank pages, and no text blocks outside the PDF page bounds.

The tracked file may contain zero format changes when a resume-mode manuscript was already compliant. Otherwise inspect its `w:pPrChange` and `w:rPrChange` counts.

## 3. Render review

The automated renderer checks page creation, blank pages, and out-of-bounds text. A human or vision model must still inspect the title page, the first body page, a page containing a table or figure, and the final references page for clipping, crowding, and unwanted pagination.

## 4. Failure handling

Failed runs keep logs and candidate files under `diagnostics/` and write `failure.json`. Do not rename or copy diagnostic candidates into the primary deliverable names. Resolve the documented cause and rerun into a new empty output directory.
