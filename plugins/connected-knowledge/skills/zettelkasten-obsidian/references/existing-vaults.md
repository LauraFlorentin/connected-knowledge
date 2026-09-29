# Existing-vault profiles and comparison

Read the actual shared guide before choosing a profile. Existing conventions take
priority over this plugin's default ontology. Never add a schema marker or rename
properties merely to obtain a clean report. These tools do not edit the vault.

## Choose a local profile

Start from `assets/profiles/existing-vault.json`, copying it outside the vault and
adapting it to the inspected guide. It is an example for a legacy `type`/`status`
vocabulary, not a universal required schema. There are no machine-specific paths.

- `fields` maps logical names to existing property names, reusing the checker's
  existing mapping mechanism. Enum, type, required and identity rules use it.
- `enums` explicitly validates allowed values in **all** checker modes, including
  generic. Unlike older releases, supplying an enum now enforces it in generic
  mode. Omit rules you have not established; do not guess activity-state values.
- `types` accepts string, integer, number, boolean, date (YAML date), list and
  string_list. A list of these names allows multiple types. Null optional values
  are allowed; use `required` to reject absent/null/empty values. `date` does not
  validate the format of a string; `string` permits any string.
- `roles` maps note-role values to local rules. Each role may have its own
  `identity`, `required`, `enums`, `types` and `references`. Global constraints and
  role constraints both apply. Roles are read through `fields.note_type` (default
  `note_type`). When roles are configured, only their declared identities are
  checked, scoped by role and field. Declare every role whose identity matters.
  Without roles, the existing single `fields.id` behavior remains.
- `references` documents shared references. They are not uniqueness constraints;
  a role cannot declare the same mapped field as both identity and reference.
- `guide` and `template_folders` are vault-relative. Saved core Templates settings
  contribute an additional template location. Missing paths or paths that are not
  directories fail with exit code 2; overlapping folders inspect each file once.
  Templates are excluded from note
  identity checks and checked separately. `exclude_dirs` retains the original
  directory-basename exclusion behavior (for example `Archive`, not a glob).

Example commands, with paths resolved relative to this skill:

```bash
python scripts/vault_check.py /chosen/vault --profile generic --config /chosen/profile.json
python scripts/vault_compare.py /chosen/vault --config /chosen/profile.json
python scripts/vault_compare.py /chosen/vault --compare /other/vault --config /chosen/profile.json --other-config /other/profile.json
```

Redirect JSON only to a location **outside both vaults**. If `--other-config` is
omitted, comparison uses the first profile for both vaults. Inspect each guide
before deciding that is appropriate. No report contains a migration plan unless
an assistant separately proposes one. The Markdown outlines in `assets/reports/`
help summarize JSON without conflating filesystem observations, prior reports,
user statements and an actual in-app trial.

## What is verified

Inventory reports contain relative file paths/hashes (including hidden settings,
excluding `.git` and symlinks), selected saved settings, property types and values,
scoped identities, template hashes and bounded substitution results. They compare
before/after inventories and flag concurrent changes rather than asserting that
a changing vault was preserved. Reports can contain private property values and
paths: keep them local unless sharing is explicitly authorized. Vocabulary values
use JSON strings; values containing YAML mapping keys that JSON cannot serialize
or sort are stored as a JSON object with a `yaml` string, preserving typed keys
without merging distinct keys such as `1` and `"1"`.

Template checks substitute `{{title}}`, `{{date}}`, `{{date:YYYY-MM-DD}}`,
`{{time}}` and `{{time:HH:mm}}` with fixed synthetic values, then parse YAML and
validate nonblank local properties. Required blank template placeholders are
intentional. Other formats/variables produce a warning; this is not the full
Moment formatter or a UI insertion test. It does not verify factual content.

Existing external paths and excluded targets are informational `external-link`
and `excluded-link` findings, not `broken-link` errors. External content and
excluded anchors are not read/validated. `file:` URLs are external references
whose availability is not tested. Missing relative targets remain errors.
Short-name ambiguity remains an error for links. Inline Markdown with angle-
bracket paths containing spaces is supported; complex reference links, escaping
and Obsidian-specific resolution still need manual review.

A comparison's `files` and `settings` sections list identical, changed and
one-sided relative keys. Workspace layout can differ legitimately; file hashes
include it, while semantic settings comparison omits workspace state. Hash equality
is not evidence of synchronized future edits or equal meaning under different paths.

Exit codes: checker 0 for no errors, 1 for errors (or warnings with `--strict`),
2 for execution/configuration failure. Inventory/comparison 1 means validation
errors or concurrent changes, 2 means failure, 0 means neither. Differences alone
are normal and do not fail comparison. Unsupported syntax and unavailable UI/sync
verification remain explicit limits even after exit 0.
