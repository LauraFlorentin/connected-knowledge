# Research tools

Use scripts from this skill's `scripts/` directory, resolved relative to this SKILL.md, not the current working directory. They also run independently from any extracted package. Python 3.10+ and `pip install -r scripts/requirements.txt` are required. No model API keys are needed.

## PDF extraction

`python scripts/extract_pdf.py INPUT.pdf --output /chosen/extractions`

Read-only input; writes a SHA-256/version/threshold cache containing `document.md` and `metadata.json`. Each section uses physical PDF page numbers. Metadata reports every page, source hash, coverage and extraction warnings. Reruns verify/reuse the cache. Exit 0: text extracted; 1: sparse/unreadable pages need review; 2: failure. No OCR is bundled. Sparse pages may be blank or scanned; this heuristic is not a scan classifier. Inspect rendered originals for figures, tables, equations and reading-order issues even when extraction succeeds. Use an available PDF rendering tool for visual review. Never cite unreadable text as inspected evidence. Preserve originals byte-for-byte separately; extraction itself does not archive them. Record `source_file` (vault-relative) and `source_sha256` when the original is retained inside the vault.

## Vault checker

`python scripts/vault_check.py /path/to/vault --profile auto > /outside/vault/report.json`

Never rewrites notes. It checks YAML (including duplicate keys), duplicate IDs, metadata types, required fields/enums for our schema, basic links/anchors, PDF page bounds and optional source hashes. `auto` applies our schema only to `schema_version: 1` notes; `generic` avoids imposing it; `zettelkasten` explicitly applies it to all checked notes. Templates and hidden directories are skipped as notes. Configured templates are now validated separately; see [existing-vaults.md](existing-vaults.md). `--strict` treats warnings as failure. Exit 0: no errors; 1: findings; 2: execution failure. A clean report is not factual validation. Complex Markdown reference links, escaped syntax and renderer-specific anchors need manual review.

Optional JSON config: `{"fields":{"id":"uid","note_type":"type"},"required":["id","title"],"exclude_dirs":["Archive"],"enums":{"category":["Admin","Personal","Work"]}}`. Explicit config enums apply in all modes, including generic; role rules and local types are documented in [existing-vaults.md](existing-vaults.md). Fields map canonical to existing names; do not edit legacy metadata merely to pass a check. Keep output outside the vault so it cannot overwrite a note.

## Collection

`python scripts/collect.py --config /chosen/collection.json --once`

Supports explicit local files/directories with glob, public HTTP(S) responses, RSS 2.0 and Atom entries. Feeds preserve entry XML and references, not full articles or attachments. Config paths are relative to the config file. The output inbox has immutable raw content, versioned records, Markdown review receipts, state, and per-run reports. Stable identity is source-config ID plus provider ID/path/URL; byte hashes distinguish versions. Different configured source IDs remain distinct. Unchanged repeats skip, changed content creates a new version, missing archived captures are reported rather than silently restored. `excluded_ids` prevents deliberate reimports. Renamed local paths without provider IDs are distinct sources; semantic deduplication remains a later step.

No account history access, OAuth, email connector, scheduler, or watcher is bundled. Treat HTML/PDF responses as retrieved bytes, not verified complete articles; login walls can return HTTP 200. Failed sources and max-item truncation appear in reports; nonzero exit exposes attention needs. A lock rejects concurrent runs. After a crash inspect any stale lock or unindexed capture; do not delete user material automatically. Public URL allowlists reject private addresses and redirect hosts outside the allowlist. This is a trusted single-user collector, not a hardened multi-tenant fetch service; no adversarial DNS guarantee is claimed.

`--scheduled` is only a scheduler entrypoint and refuses unless `ongoing_enabled` is true. It does not install a scheduler. Select exact sources, inbox, cadence/timezone, scope, retention and runtime before enabling one. See the Research Collection skill for the workflow and platform differences.
