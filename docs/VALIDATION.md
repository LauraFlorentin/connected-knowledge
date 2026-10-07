# Validation and limits — updated 2026-10-07

## 1.7.0 commands, capture pipeline and vault structure

**Automated.** 263 tests pass with Python 3.12.14 on macOS (190 carried over, 73
new). The 46 tests in `test_capture_pipeline.py` and `test_ck_commands.py` also pass
with the stock macOS Python 3.9.6 and no third-party packages, and a test re-runs a
capture with `python -S` to prove that no package is imported. New coverage:

- hooks find this Mac's configuration with no environment variables; stay inert
  without it or with capture off; skip out-of-scope folders and subagents; and queue
  a session whose transcript is unreadable, which proves they never open it;
- state folders are 0700 and must lie outside the vault; files are 0600;
- a 60-turn synthetic session keeps state at most twice the transcript size and
  produces exactly one note and one transcript; the vault receives only notes,
  attachments, the index and a project note;
- a killed lock holder followed by a successful sweep; a crash between writes
  retried; two concurrent sweeps both exit 0; failing entries are parked after five
  attempts; a turn that ends during a capture stays queued; quiet sessions are
  noticed at the end of a turn elsewhere;
- a three-folder session is filed under its first folder; `isMeta`, wrapper and
  reminder rows are not shown as user text; title rows are used in order; Codex
  harness messages are skipped; a partly written last line is tolerated;
- labels per platform, file names, the per-machine index, remote-control devices;
  person edits, removed markers, shorter transcripts, edited transcripts, deleted
  notes, and notes from another machine;
- a 20-row escaping table, plus a vault check over a transcript containing all of
  it (no findings);
- both starter variants pass `vault_check --profile auto` with zero errors and
  zero warnings after one capture; full and minimal structures; topic names;
  custom categories;
- adoption of a synthetic `type`/`status` vault: the preview writes nothing,
  conversation notes use the vault's names with no parallel fields, and
  `.obsidian/` and existing notes are byte-identical afterwards;
- ChatGPT epoch dates to ISO 8601; ontology keys; graph tools read new and 1.6.0
  archives; migration of a 1.6.0 export archive (edited note reported, second run
  a no-op, old folder unchanged) and of a 1.6.0 session-capture archive (a later
  live capture continues it);
- every `doctor --next` state from the plan, add-session by ID, latest, path,
  current and all, previews that write nothing, topic maps, the capture switch,
  skill frontmatter, and the Gemini package contents;
- manifest versions and every current version string in the docs, manifest shape,
  hook registration, relative links in all docs, README host coverage, and the
  private-data packaging guard;
- the Filesystem answers file shown in `/ck-setup` previews without writing, then
  registers one Claude Desktop entry while keeping the other settings, through the
  real installer with downloads stubbed.

**Examples and packages.** The graph example (0 checker warnings, 0 repeat writes)
and the worked example pass. `package.py`, `package_gemini.py` and
`verify_package.py` pass; verification now also creates a new vault from the
extracted package, captures a synthetic session and runs the vault check with zero
findings. `claude plugin validate` passes for the plugin and the marketplace with
no warnings (Claude Code 2.1.291).

**Native, in a sandbox.** In Claude Code 2.1.291 with `--plugin-dir` and a
temporary configuration home: `/ck-help` showed status, the menu and `/ck-setup`
as the next step; `/ck-setup status` summarised a temporary vault; `/ck-add-session`
previewed, retitled and saved a synthetic session with a topic and category, then
offered the next step. No real vault, configuration or transcript was used.

**Not tested.** Codex (bundled hook discovery, `$ck-…` skills, `SessionStart` and
`SessionEnd` handling), Cowork, Claude chat and iPhone, ChatGPT desktop and iPhone,
Gemini CLI; marketplace installation by repository name; how the hooks behave in a
real long session with capture switched on; two real Macs on one synced vault;
Remote Control detection (devices come from setup or `--device`); the exact field
names of Claude Code title rows, which the reader accepts in several spellings.

## 1.6.0 unified install/update flow

190 local Python 3.12 tests pass on macOS, including 17 installer tests. Coverage
includes fresh setup, unchanged retries, legacy and managed upgrades, preservation
of private settings/templates/profiles/state, download and validation failures,
concurrent private edits, active-runtime locks, interrupted publication/retry,
host-entry conflicts and retry, TOML/JSON merges, unsafe Node archive members,
vendor checksum mismatch, and refusal before installation when disk space is low.
A real stdio test upgrades a synthetic legacy capture runtime, retries the original
capture unchanged and saves a new selection while retaining previous note bytes.
Candidate validation rejects unsupported templates before selecting new code.

A separate fresh macOS arm64 trial downloaded and installed a complete isolated
runtime: Python 3.12.14 dependencies (MCP 1.30.0, keyring 25.7.0, tomlkit 0.15.1),
official tunnel-client v0.0.15, Node 24.21.0 and Filesystem server 2026.8.31.
Vendor archive checksums passed. The installer performed its synthetic save/retry
and Filesystem read/write/outside-denial checks. A repeated install reused the
generation and host entry. Actual stable launchers passed private capture
save/retry, bridge tool discovery/convention reading, Filesystem scope inspection,
read/write and outside-scope denial. Host merging used only a temporary TOML file;
its unrelated setting and comment were retained. No account was connected and no
personal vault, credentials, host settings or installed plugin were changed.

Both builders pass, and all 101 extracted plugin entries match source. Extracted
unified preview, existing Filesystem preparation, capture save/retry/edit protection,
vault preview and linked-save checks pass. The core skill validator and local
documentation link checks pass. The graph example has zero checker issues and
zero repeat writes. All four version manifests are synchronized at 1.6.0.
Hosted release checks are recorded on [PR #16](https://github.com/LauraFlorentin/connected-knowledge/pull/16);
package creation alone does not update installed copies.

Python remains a prerequisite. The full dependency-download trial ran on macOS;
hosted tests cover Python 3.10/3.12 on macOS and Linux. Native Codex/Claude Desktop activation, actual account association,
OS keyring access, startup and cross-device synchronization were not tested here.
The wizard stages versions and recovers via explicit retry; it does not update in
the background, start connections, remove old generations or automatically roll back.
Third-party editors do not share installer locks. The live vendor download trial
is separate from the network-free test suite and package verification.

## 1.5.0 optional Filesystem MCP setup

173 local Python 3.12 tests pass on macOS. Ten added setup tests cover no-write
previews, all three connection formats, path/argument quoting, exact version
selection, folder boundaries and aliases, protected output locations, private
file modes, existing/concurrent setup preservation, and the command-line wizard.
The helper uses only the standard library and prepares settings without installing
or activating a server. Both builders pass; all 94 extracted plugin entries match
source, including the new setup preview/apply check. Existing capture, vault
preview and linked-save extracted checks pass. The graph example has zero checker
issues and repeat writes.

The separate opt-in `tools/verify_filesystem_mcp.py` trial passed with the official
`@modelcontextprotocol/server-filesystem@2026.8.31`, Node 24.18.0 and npm 11.16.0.
It downloaded dependencies into a temporary cache and used synthetic temporary
folders only. Actual stdio checks covered discovery, read/search/write, edit
preview and readback, move, denial of outside/traversal/symlink paths, and client
Roots replacing the command-line folders. npm reported package integrity
`sha512-kKaFkyAh6oipvc9+EAbJ552JafnMnOq5nzmzWkp1jJdBhTAAGpmIpWihUG1+rfNhmEFM98gUZDdCHCDD4v6a7Q==`.
Transitive dependencies are not locked by the setup helper. This trial is opt-in
and is not run by normal tests or package builds.

Host fragments follow current upstream and official Codex documentation. Native
Codex/Claude Desktop connection activation, Windows, web/mobile and live-vault
trials remain unverified. No personal connection, vault or host configuration was
changed. The tested path cases do not establish a complete filesystem sandbox;
the upstream server and client Roots govern effective access. All four version
manifests are synchronized at 1.5.0. Hosted release checks are recorded on the
release pull request; the evidence below describes local feature development.


## 1.5.0 linked-note saving

163 local Python 3.12 tests pass on macOS. The 20 added save tests cover real stdio
preview/save/retry and write revocation, unchanged read-only previews, changed
preview inputs and scope, preserved record IDs and previous bytes, custom identity
fields, duplicate IDs, human edits after save and during recovery, original capture
integrity/coverage, output symlink swaps, concurrent save locking, journal corruption,
file modes and new files created during a save. A subprocess exits immediately after
publishing a file to verify recovery of an interrupted atomic-link operation.

Both builders pass. The extracted package's 92 entries match source bytes; capture
save/retry/edit protection, vault preview and linked-note save/retry checks pass.
These are synthetic local checks, not a hosted CI or native-host trial of the save
stage. The feature was initially validated before the 1.5.0 release version bump.
No live vault, runtime configuration, guide/template or connection identity changed.

Saving requires its own private switch and external journal directory. Multi-note
saves can be incomplete and resumed; they are not a single atomic filesystem
transaction. Other editors and cloud-sync processes do not share the bridge's lock.
Previous note bytes are retained privately; there is no automatic rollback or
unrestricted edit/delete operation. Template compliance, complex links/anchors,
factual accuracy and native rendering remain separate checks.

## Vault bridge — preceding read and preview milestone

143 local Python 3.12 tests pass on macOS, including 17 new vault bridge tests.
New tests exercise the real stdio MCP discovery/read/search/preview path, runtime
revocation, unchanged default capture tool discovery, no-write previews, source
changes before/during preview, occupied targets and stale target hashes, scoped
paths, symlinks/hardlinks, ambiguous links, entry-point reachability, filename
handling, and bounded searches. All fixtures are synthetic temporary vaults.

Both distribution builders pass. The portable/Claude archive's 90 entries match
source bytes; extracted capture save/retry/human-edit protection and the new
read-only vault preview pass. The existing graph example reports zero checker
issues and zero repeat writes. The four manifests retained the published 1.4.2
version at that earlier development milestone; these tools are now included in 1.5.0.

That preceding milestone exposes no developed-note writer. Filesystem MCP is a documented optional
connection, not installed, bundled or activated. No personal vault, live guide,
template, connection identity or runtime configuration was changed. Native-host
vault-tool trials and hosted CI for this change have not run. Simple link checks
do not certify anchors, complex Markdown, original-source integrity, template
compliance, factual accuracy or Obsidian rendering.

## 1.4.0 release checks

126 local Python 3.12 tests pass. New coverage includes explicit MCP message schema,
template preservation and unsupported-code rejection, readable filename identity,
private setup boundaries, official binary variant/checksum verification, startup
file argument isolation, loopback-only status, and release of archive locks after
process termination. Existing source/import/graph/hook compatibility checks remain.
Both skills validate; extracted package save/retry/human-edit checks run in CI.

A clean extracted macOS package trial creates its own permanent-style external
runtime and Python environment, installs runtime dependencies, and exercises
synthetic selected saves. Official tunnel-client v0.0.15 Darwin arm64 download
checksum verified. Native ChatGPT web tool discovery/save/retry succeeded in a
separate user-private connection trial. No personal content or configuration is
included in the package or test fixtures.

CI covers Python 3.10/3.12 on Ubuntu and macOS, including the extracted package.
Hosted results are recorded with the final release rather than inferred from local
success. User startup files are generated/tested without activating a real service;
OS keyring access, native startup/reconnection after login, desktop/mobile selected
saves, cross-device vault sync and native Gemini CLI remain separate host checks.
Gemini CLI is experimental. Windows private capture is unsupported. Regular Gemini
Apps use selected text/supplied exports; no inferred Takeout schema or universal
all-chat capture is implemented. The downloadable release is not a published
ChatGPT directory service.

Historical evidence below describes its original versions; it does not override
this release's implemented behavior or remaining limits.

## Release — 1.3.0

### Bundled hook follow-up

105 local tests pass after the integrity-review fixes and bundled launcher addition.
The eight launcher tests execute the actual hooks.json command with synthetic
Codex/Claude Code events and cover disabled/missing configuration, host mismatch,
project/subagent exclusion, absent dependencies, Stop/SessionEnd repeats and failed
transcript retry. The launcher uses only standard-library imports before opt-in.
Plugin and skill validation pass. No installed host was configured or observed
firing a hook; shell testing is POSIX/macOS, not Windows or cloud Work.

### Earlier candidate evidence

All 93 local tests pass (69 existing plus 24 setup, bundle and recovery tests).
Plugin and primary skill validation pass; the existing graph example has zero
checker issues and zero repeat writes. The rebuilt ZIP's 58 entries match source
bytes and SHA-256 inventory, and all three manifests report 1.3.0. These are local
checks, not hosted CI results for this uncommitted candidate.

Guided setup combines explicit vault/history/category/capture choices in a saved
plan. Saving never runs planned commands or enables capture. The synthetic end-to-end
test executes starter creation, ZIP preparation, attachment preservation, import
preview/apply and no-op repeat in temporary storage. The wizard subprocess is also
exercised. Separate recovery tests invoke both host adapters through hook stdin.

ZIP support is selected-file preservation and a linked index, not automatic
provider attachment association, OCR, remote download or in-vault asset copying.
Safety coverage includes path/link/collision rejection, limits, exclusive locks,
byte preservation, changed output detection and cleanup after a simulated disk error.
Capture coverage includes incomplete/unflushed retry, checkpoint-write recovery,
locks, snapshot corruption and fail-closed note/manifest interruption. Real installed
host events, scheduler recovery and cross-device behavior remain untested.

No private export or actual vault was used. Publication is handled separately from validation. Installed-host trials remain
pending; no installed copy was changed during these checks.

## Published release — 1.2.1

Includes supplied-JSON history import, assistant-proposed graph development, local
session adapters and the Claude reply-reference fix. The 69-test suite covers
these tools with synthetic fixtures. PR #5 passed hosted checks on Python 3.10
and 3.12 before this documentation/version cleanup. A redacted conversation
structure parsed in memory; that is not full-export or attachment validation.

No automatic account-history fetching, ZIP/attachment extraction, semantic-search
service, registered hooks or scheduler is included. Installed-host end-to-end
execution, live capture/recovery, mobile and cross-device behavior remain separate
checks. No personal history was imported for this release.

### Release cleanup checks — 2026-09-30

- All 69 local tests pass; plugin and both skill validators pass.
- Synthetic import-to-graph example produces one archive note, two graph notes,
  three edges, zero checker errors/warnings and zero writes on repeat.
- Rebuilt Claude ZIP contains 51 tracked plugin source files. Every entry matches
  its source bytes and SHA-256 inventory; all three manifests report 1.2.1.
- Personal exports and runtime data are outside the packaged source. No installed
  copy was refreshed and no live capture or personal-vault test was performed.

## Historical validation records

The dated sections below describe their original versions and environments.
Statements about missing features, binaries or installation in those sections
are historical; the current release summary above takes precedence.

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

## Next-version development checks — September 30, 2026

119 tests pass locally on Python 3.12, including shared private capture, concurrent duplicate saves, interrupted-import recovery, human-edit protection, bounded/disabled inputs, path separation, Gemini event replay/continuation and a real MCP stdio client discovery/save/retry test. MCP SDK 1.30.0 tested. Both development packages build. Extracted Gemini ZIP command successfully saved/replayed a synthetic event with exactly one resulting record; this tests packaging and process invocation, not Gemini native hook discovery.

Gemini CLI is absent on the inspected host. ChatGPT account/tunnel association and ordinary desktop/mobile selected saves have not been tested. No live vault, personal exports, personal runtime capture, remote service, tunnel, scheduler, cost-bearing API call or release was used. New private capture runtime is POSIX-only. Existing released host evidence remains dated; it was not rerun. Hosted CI was not run for this local development branch.
