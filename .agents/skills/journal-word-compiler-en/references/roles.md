# English manuscript roles

## Contents

1. Critical roles
2. Deterministic evidence
3. Resume-mode protections
4. Manual correction

## 1. Critical roles

Critical roles are `title`, `abstract_heading`, `abstract_body`, `keywords`, headings, captions, `bibliography_heading`, and `bibliography_entry`. A wrong critical role can apply the wrong journal style to a large block, so inspect low-confidence mappings before compiling.

## 2. Deterministic evidence

The mapper prefers explicit Word styles, outline levels, numbered headings, exact academic headings, `Abstract:` and `Keywords:` prefixes, caption prefixes, and the region after `References`. It uses centered front matter only as medium-confidence evidence for author and affiliation lines.

Missing Abstract, Keywords, or References produces a warning because some article types legitimately omit them. Missing a recognizable title is a blocker unless the user supplies a reviewed RoleMap.

## 3. Resume-mode protections

Do not infer roles from whichever format is most common in a half-formatted manuscript. Determine roles from semantics and the official profile, then preserve already compliant paragraphs. Retain local semantic emphasis such as gene italics, superscripts, subscripts, bold labels, and special symbols.

Existing text insertions/deletions are blockers. Do not mix an editor's old text revisions with a new formatting revision layer without an explicit user decision.

## 4. Manual correction

`target-rolemap.json` is an object whose keys are engine paragraph indices and whose values are valid role names. Preserve complete coverage of every editable non-table paragraph. Correct a copied file and pass it with `--target-rolemap`; keep the generated audit beside it.
