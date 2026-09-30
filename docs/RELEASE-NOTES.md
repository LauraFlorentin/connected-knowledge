# Release notes

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
