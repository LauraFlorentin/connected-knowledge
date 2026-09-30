# Release notes

## 1.3.0 — 2026-09-30

- Bundle Stop/SessionEnd hooks with a host-specific opt-in launcher, disabled
  without private configuration; no user/global hook files are modified.

- Reject symlinked output roots before resolution; version import fingerprints
  so corrected metadata reaches existing archives while preserving revisions.
- Add a terminal wizard and assistant-driven first-run plan for vault choice,
  selected history, optional categories and disabled capture configurations.
- Add bounded ZIP inspection/preparation, selected attachment byte preservation,
  a linked attachment index, original ZIP retention and hash-verified repeat runs.
- Allow new starter templates without forced default categories. Existing vaults
  remain unchanged.
- Test both capture hook command interfaces and interruption/retry behavior with
  synthetic data; reject modified normalized snapshots and symlinked output parents.

Setup saves a plan only. Attachment associations are not inferred, URLs are not
followed and bundled hooks stay inactive without explicit private configuration. Live-host activation remains a
separate test.

## 1.2.1 — 2026-09-30

- Preserve Claude `parent_message_uuid` reply relationships, including alternate
  replies, with the older `parent` field as a fallback.
- Add synthetic compatibility coverage for text blocks, parent-field precedence,
  preview, original preservation and repeat imports.
- Align installation, usage and capability documentation with the implemented
  history importer, graph workflow and opt-in local session adapter.
- Synchronize all three plugin manifests at 1.2.1.

No vault-schema migration is required. Existing importer archives retain their
identities; reimporting the same Claude snapshot may update generated metadata
to include reply references, preserving the prior note as a revision. Human-edited
notes still produce conflicts.

Personal exports, notes and runtime configuration are not release contents.
Capture is disabled unless separately configured. ZIP/attachment extraction and
automatic account-history access remain unsupported.

These files prepare a source/package release; they do not themselves publish a
GitHub release, submit to a plugin directory or update an installed copy.
