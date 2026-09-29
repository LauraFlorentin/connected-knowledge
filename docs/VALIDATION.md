# Validation and limits — updated 2026-09-28

## Session capture candidate — 2026-09-29

67 tests pass (55 existing plus 12 session-adapter tests). Covers read-only previews,
repeat/append behavior, raw preservation, project exclusions, disabled writes,
incomplete JSONL, shortened snapshots, identity/final-message checks, non-text
exclusions, symlinks, history batch reporting, human edits and hook exit behavior.
Local read-only format trials parsed 15 of 16 Codex transcript files and 4 of 10
main Claude Code files. Rejected files were empty, incomplete or had unclear
project identity; no coverage was inferred for them. No transcript contents are
included here, no actual history was imported, and no live hook was installed.

## Graph development candidate — 2026-09-29

55 synthetic tests pass (43 existing plus 12 graph workflow tests). Graph coverage
includes exact message citations, lexical search/limits, read-only preview,
idempotent apply, valid vault links, legacy property conventions, proposed decision
state, cross-note relationships, stale/missing evidence, invalid paths/categories,
human edits, revisions, symlinks and changes during proposal rendering. Import
archives remain byte-unchanged during graph writes. AI reasoning quality and real
history coverage are not established by these structural tests. No live vault,
account capture, scheduled process or plugin installation was modified.

## History import candidate — 2026-09-28

43 tests pass (30 existing plus 13 importer tests). Synthetic fixtures cover
preview with no writes, repeat imports, retained source/revision bytes, conflicts
with human edits, unchanged notes when unrelated chats change, absent/duplicate
IDs, account separation, branched ChatGPT messages, Claude content/attachments,
optional categories, existing-vault vocabulary, invalid links and exclusive locks.
Pre-merge regression checks also verify that missing/changed original exports
block repeat imports, including manifests written before original paths were
recorded.
The plugin validator passes. No personal export has been imported, no real-export
compatibility claim is made, and no continuous-capture adapter is installed.

## PR review fixes — 2026-09-28

30 synthetic unittest cases pass on Python 3.9.6, including regression coverage
for YAML date/mixed-type mapping keys through both CLIs, missing/non-directory
template paths from profiles and Obsidian settings, and overlapping template
folders. Unrepresentable JSON mappings retain typed keys in an explicit YAML
payload. Invalid template directories exit 2, and template files are inspected
once even when profile/settings paths overlap. No live-vault checks were repeated.

The system plugin validator now passes. Added Codex author and display metadata
and removed unsupported `policy.products` from the two skill agent files;
`allow_implicit_invocation` and skill instructions remain intact. This supersedes
the five packaging incompatibilities recorded below. Collection code and knowledge
note templates remain unchanged; the collection skill's agent metadata has changed.
The distribution was rebuilt and every ZIP entry matches source bytes.
Native installation, UI behavior and sync remain separate, unperformed checks.

## Version 1.2.0 existing-vault extension — 2026-09-28

27 unittest cases passed (12 existing, 15 new) using Python 3.9.6 on macOS.
The new tests cover configured enums/types in generic mode, identity field mapping
and role scope, repeated references, required role properties, configured template
folders, blank placeholders, unsupported expansion warnings, malformed YAML,
external/excluded/missing links, ambiguous excluded short names, symlinks,
comparison differences, concurrent changes, invalid profiles and CLI failure codes.
The documented Python 3.10+ minimum remains; this run is additional compatibility
evidence, not a supported-version matrix.

A read-only local check of an existing everyday vault passed: 5 non-template notes,
16 templates, no errors/warnings, unchanged file hashes. The preserved project pack
had 16 non-template notes and 14 configured templates, zero errors, two ambiguous
README warnings, and informational external/excluded links. Both inventories were
unchanged. These filesystem checks do not claim a UI trial or ongoing sync test.
Private reports remain outside this repository.

All four existing note templates and the complete research-collect skill are
byte-identical to 1.1.1. The primary skill passes the format validator. All three
manifest versions agree, and every distribution ZIP entry matches source bytes.
The current system plugin validator reports the same five metadata incompatibilities
on both the unmodified baseline and this candidate: missing author object,
longDescription and developerName, plus policy.products in each skill's agent
metadata. This release does not silently remove that existing product metadata;
full validation by that validator remains unresolved. No native install or hosted
release of this candidate is claimed by these tests.

## Version 1.1.1 rename — 2026-09-28

Renamed the plugin and marketplace to Connected Knowledge and updated the two skill display names to Develop Knowledge and Collect Research. All core instruction, reference, template and script bytes were checked against the preceding package and preserved; only skill UI metadata changed. Internal skill names remain unchanged.

Both skills passed format validation. The twelve existing tool tests were rerun successfully from the renamed source path. The offline worked example also passed from that path: one initial capture, one unchanged duplicate, two PDF pages, three connected notes, zero checker errors or warnings, and unchanged vault bytes after checking. The package build, manifests, marketplace paths, core hashes, local Markdown links and ZIP contents were checked. Native host installation and live collection remain untested.

## Version 1.1.0 update — 2026-09-28

The updated canonical core passed the skill-format validator and local reference-link checks. Its main instructions remain about 1,400 words, with the added detail routed to references. The relevant starter-vault gate test passed after installing the declared defusedxml dependency; a temporary fixture verified the exact new vault guide and four templates. The full twelve-test suite below belongs to the 1.0.0 validation; unchanged collection/PDF/checker code was not retested unnecessarily.

An independent forward exercise applied the updated skill to an inaccessible Mac vault, remembered budget information conflicting with a documented decision, and a later Claude export. It preserved the evidenced decision and unresolved proposal, marked memory and duplicate checks as provisional, reused supplied identities, avoided replacing the vault, and distinguished supported hooks from universal native-app capture. This is an instruction exercise, not a test of a real connector or semantic-deduplication engine.

The rebuilt archive passed manifest/version, shared-source hash, distribution-ZIP and archive-integrity checks. No actual vault, account capture, native installation or scheduler was connected. Platform guidance now distinguishes documented Work/Codex hooks, Claude Code hooks and Claude's connected-folder/mobile requirements. The bulk history parser and semantic search engine remain unimplemented.

## Executed

- Both canonical skills passed the skill-format validator before packaging.
- Twelve unittest cases passed: PDF page extraction/cache/source preservation; cache drift; malformed/encrypted PDFs; image-only scanned page warning; repeat/versioned local collection; partial source failures; disabled ongoing runs; RSS limits and provenance; Atom; unsafe XML rejection; exclusions; missing archive detection; collector lock; private-URL rejection; duplicate identifiers; YAML duplicate keys; broken links; invalid PDF pages; missing headings; generic-schema compatibility; configured field mapping; inconsistent metadata types and source-hash drift; explicit starter gating and refusal of existing targets. Several behaviors share a single test case.
- Offline end-to-end worked example: 1 capture, 1 unchanged repeat, 2 extracted pages, 3 connected example notes, 0 vault errors/warnings, read-only checking verified by byte hashes.
- Independent instruction exercise: an inaccessible existing Mac vault did not trigger replacement; unspecified feeds/email and schedules remained disabled; chat title labels stayed separate from vault categories; all-chat collection was not claimed.
- Package checks verify JSON manifests, local marketplace paths, identical shared skill copies, required distribution ZIP entries and archive readability.

Runtime used: Python 3.12, pypdf 6.10.0, PyYAML 6.0.3, defusedxml 0.7.1, reportlab 4.4.9. Requirements allow compatible major-version ranges; other versions and operating systems were not run here.

## Not exercised or not included

- Native Claude/ChatGPT plugin installation, UI rendering and account-wide availability were not tested. Installation documentation was checked against current official pages. Neither Claude Code nor Codex CLI is installed in this validation environment.
- Live feed/URL HTTP retrieval was not exercised; feed parsing was tested with controlled responses. DNS, network permissions, redirects, rate limits, login walls and individual sites may affect actual captures.
- No email/cloud authentication, account chat-history access, live vault connection or recurring scheduler was configured. Those depend on your selected source, destination, permissions and trigger.
- No OCR or automated visual PDF interpretation. Sparse/image-only pages are flagged, and figures/tables need inspection.
- Checker is read-only and structural, not a complete Obsidian parser or evidence verifier. See its reported limits; no silent repair is available.
- Collection is for a trusted single-user runtime with a single-writer lock. It is not an internet-facing service. A hard crash may leave a stale lock or unindexed files; recovery is manual and non-destructive.

## Rerun tests

```bash
python -m unittest discover -s plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/tests -v
```

Tests use temporary synthetic files. They do not read your real vault or accounts.
