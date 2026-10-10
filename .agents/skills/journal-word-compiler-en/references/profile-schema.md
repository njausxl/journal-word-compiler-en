# Journal profile and guide overrides

## Contents

1. Profile storage
2. Override contract
3. Common fields
4. Precedence and conflicts

## 1. Profile storage

Profiles are versioned by template, guide, and reviewed override hashes under `~/.codex/journal_profiles_en/<journal>/<version>/`. Never overwrite a different source version.

Each profile stores the official template and guide, their SHA-256 values, extracted guide text, conservative rule candidates, template RoleMap, final `profile.json`, and exceptions.

## 2. Override contract

A reviewed guide-rules file is a JSON object merged recursively into the template-derived FormatSpec. Include only explicit rules supported by a precise guide passage. Omitted properties keep the template value.

Example:

```json
{
  "page": {
    "margin": {
      "top_mm": 25.4,
      "bottom_mm": 25.4,
      "left_mm": 25.4,
      "right_mm": 25.4
    }
  },
  "roles": {
    "body": {
      "font_ascii": "Times New Roman",
      "font_eastasia": "Times New Roman",
      "size_pt": 12,
      "alignment": "justify",
      "line_spacing": {"type": "multiple", "pt": 2.0}
    }
  }
}
```

Do not use guide-rules to rewrite content, citation punctuation, author metadata, or reference metadata.

## 3. Common fields

- `page.size`: `A4`, `letter`, or another engine-supported page size.
- `page.orientation`: `portrait` or `landscape`.
- `page.margin.*_mm`: margins in millimetres.
- `roles.<role>.font_ascii`: Latin-script font.
- `roles.<role>.size_pt`: font size in points.
- `roles.<role>.alignment`: `left`, `center`, `right`, or `justify`.
- `roles.<role>.bold` and `italic`: explicit character emphasis.
- `roles.<role>.space_before_pt` and `space_after_pt`: paragraph spacing.
- `roles.<role>.line_spacing`: engine line-spacing object.
- `roles.<role>.keep_with_next`, `keep_together`, and `page_break_before`: pagination controls.
- `table`: ordinary table geometry and typography.
- `notes.footnote` and `notes.endnote`: note formatting.

## 4. Precedence and conflicts

Apply reviewed explicit guide overrides over the official Word template. Keep extracted candidates unapplied. If the guide and template explicitly disagree, stop and record the conflict instead of choosing silently.
