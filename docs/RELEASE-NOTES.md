# Release notes

## 1.7.0 — 2026-10-07

- **Commands.** `/ck-setup`, `/ck-help` and `/ck-add-session` (Codex: `$ck-…`;
  Gemini CLI: TOML wrappers). One standard-library script, `ck.py`, sits behind
  them. Everything previews first. Each command ends with one suggested next step
  chosen from the actual state, one alternative, and "stop here".
- **Capture that queues, then sweeps.** Hooks only record that a session changed
  and never open a transcript. A background sweep saves a session once it has been
  quiet for ten minutes or has ended, under an operating-system lock that cannot go
  stale. Nothing is copied per turn: a 60-turn session keeps state at most twice its
  transcript size. Sessions that change folders are kept and filed under the folder
  they started in. Capture runs on the stock macOS Python 3.9 with no packages. The
  hooks stay inert until `/ck-setup` writes this Mac's configuration and you switch
  capture on.
- **Conversation notes.** Each session becomes a short note (title of at most five
  words, category, topics, platform, machine, device when known, project, real
  dates, a summary block) plus a generated transcript. Your text and your changes to
  title, category and topics survive updates. A note from another Mac is never
  overwritten. A shorter transcript never replaces a longer one.
- **Safe display.** Chat text is written as inert Markdown. `dataviewjs`, `query`,
  `tasks` and other plugin code blocks, inline Dataview queries, wikilinks, embeds,
  remote images, tags, task boxes, comments and HTML show as plain text. The same
  applies to account-export imports.
- **Machine state outside the vault.** One configuration file per Mac at
  `~/.config/connected-knowledge/config.json`. A private state folder holds the
  queue, the manifest and one raw copy per session. The vault receives only notes,
  transcripts and an index file per machine.
- **Filesystem MCP in setup.** `/ck-setup apps` offers the optional Filesystem MCP
  connection, only for chat in the Claude desktop app. It previews the installer
  first, and installs nothing unless you agree.
- **New vault structure.** A full or minimal structure, with a `Templates/` folder
  or with every note shape in the Vault Guide. Home, Vault Guide, agent
  instructions, and a topic map per main topic. Seven new note templates. Existing
  vaults are adopted under their own property names (`type: reference` stays
  `type: reference`) without touching `.obsidian/`.
- **Importer labels.** Account-export notes use `source_platform`, `source_id` and
  `source_account`; ChatGPT epoch dates become ISO 8601. Archives are rewritten
  once on their next import. `ck.py migrate` turns 1.6.0 `ChatArchive/` folders
  into conversation notes: edited notes are reported and skipped, and a second run
  changes nothing.
- **Hygiene.** The Claude manifest has author, homepage and repository; the
  marketplace has a description; both pass `claude plugin validate` with no
  warnings. The plugin-root `CLAUDE.md` (never loaded by Claude Code) and the stale
  `docs/core-file-hashes.json` are removed. Packages contain only files git
  accepts, and a private-looking file stops the build. Every current version string
  in the docs is checked against the manifest.

Validation: 263 tests pass on Python 3.12 (macOS); the 46 capture and command tests
also pass on the stock macOS Python 3.9.6 without packages. All three commands ran
natively in Claude Code 2.1.291 in a sandbox with a temporary vault. Codex, Cowork
and Gemini CLI were not trialled. See [validation](VALIDATION.md#170-commands-capture-pipeline-and-vault-structure).

Upgrading: run `/ck-setup`. Configurations from 1.3–1.6 that use
`CONNECTED_KNOWLEDGE_*_CONFIG` variables keep working until the new machine
configuration exists. See [updating](INSTALL.md#updating-to-170).

## 1.6.0 — 2026-10-05

- Add one guided installation/update flow for selected private connection and
  Filesystem components. The earlier private wizard opens this same flow.
- Upgrade legacy copied runtimes and managed installations while preserving
  private settings, notes, account/archive/tunnel identities, templates, profiles,
  credentials, spool and bridge state.
- Stage and validate isolated code/dependency generations before switching stable
  entry points; retain previous versions and support interrupted-update retries.
- Optionally install verified Node.js and a pinned Filesystem MCP server, then
  merge one selected Codex or Claude Desktop connection with a private backup,
  preserving unrelated host settings. Filesystem remains opt-in.

Validation: 190 tests pass locally; the macOS/Linux Python 3.10/3.12 matrix and
package checks run on [PR #16](https://github.com/LauraFlorentin/connected-knowledge/pull/16).
A fresh synthetic macOS installation downloaded all selected dependencies and
passed capture save/retry, bridge discovery, Filesystem scope/read/write/denial,
host merging and unchanged-repeat checks. Both builders and all 101 extracted
plugin entries pass verification.

Python 3.10+ is still required. Account authorization, host restart and optional
startup remain separate. Updating the plugin does not itself run a migration,
start a connection or activate new scope. Windows is unsupported; native-host
activation and cross-device access remain separate checks. See
[installation and updating](INSTALL.md#updating-to-160) and [validation](VALIDATION.md).

## 1.5.0 — 2026-10-05

- Add scoped guide/template reads, keyword note search and linked-note previews to
  the optional private vault bridge.
- Add separately enabled saving of the exact previewed proposal, with source and
  identity checks, conflict detection, verified receipts and interrupted-batch recovery.
- Add guided optional Filesystem MCP setup for chosen folders, a pinned upstream
  version, and Codex, Claude Desktop or generic local stdio connection settings.
  Setup prepares private files; the server is a separate connection and is not bundled.
- Preserve the default capture-only tool set and all existing private identities,
  vault conventions and source originals. Updating the plugin activates none of
  the new tools and does not update a separately installed private runtime.

Validation: 173 local Python 3.12 tests, both package builders and extracted-package
checks passed. A separate upstream Filesystem MCP protocol trial passed using only
temporary synthetic folders. Native-host activation, live-vault save/navigation,
web/mobile access and Windows remain separate verification tasks. Multi-note saves
are resumable, not one atomic transaction; external editors and cloud sync do not
share the bridge lock. See [validation](VALIDATION.md) and [updating](INSTALL.md#updating-to-160).

## 1.4.2 — 2026-10-02

- Add a guided starting menu for explicit invocation without a concrete task.
- Guide vault setup, selected past/current conversation saves, documents and vault exploration one unresolved step at a time, reusing known choices.
- After completion, suggest a relevant next task and wait for the user to choose it; then guide that task in turn.
- Preserve direct-task execution, source scope, existing templates and honest access/coverage limits. These are assistant instructions, not a native wizard.

## 1.4.1 — 2026-10-02

- Make a clear reusable entry point, connected source documents and readable summaries the completion standard for assistant-guided saves.
- Distinguish maintained originals from dated attachment snapshots; reuse source identities and unchanged copies.
- Require valid table links and an Obsidian navigation/display check when UI access is available.
- Update source/map templates and the adaptable vault guide. Keep capture runtimes, permissions and automatic collection unchanged.

Update your installed plugin to receive these instructions. Existing vault guides and templates remain authoritative; adapt them rather than replacing them wholesale.

## 1.4.0 — 2026-10-01

- Add private selected-save MCP with explicit message schema, content-free errors,
  returned note names, coverage labels and stable retry/revision identities.
- Add macOS/Linux private setup wizard: existing vault, selected source template,
  isolated permanent environment and checksum-verified official tunnel-client.
- Support vault source/conversation-review templates and bundled capture templates;
  preserve property vocabulary and originals, append exact selected messages, and
  protect human edits. Arbitrary template code is never executed.
- Use readable filenames while retaining existing archive paths and stable identities.
- Add OS-keyring credential option, loopback health status and opt-in user startup
  files. Startup after login is distinct from unattended recovery after reboot.
- Add Gemini CLI AfterAgent extension packaging, marked experimental; regular Gemini
  Apps remain selected-text/supplied-export routes.
- Replace POSIX importer sentinel locking with process-released OS locking;
  retain fail-closed handling of legacy sentinel locks.

Synthetic development tests cover message schema, setup boundaries, template
preservation, replay/revisions, human edits, concurrent saves and killed-process
recovery. Native ChatGPT web selected save/retry succeeded in a separate private
connection trial. Desktop/mobile, native Gemini CLI, Linux credential-store/startup
operation and Windows private runtime are not claimed as verified. No personal
content, credentials, account IDs or vault configuration are in this release.

## 1.3.1 — 2026-09-30

- Add guided Codex project-hook setup with separate preview/apply, disabled capture,
  normal host trust review, and one capture route per selected project.
- Preserve unrelated project hooks and back up existing JSON; reject conflicting
  capture commands, malformed files and symlink destinations. Identical repeats
  make no changes.
- Document synthetic activation, upgrade/relocation and removal steps.
- Verify 111 tests, including generated hook commands and onboarding-to-hook setup.

Native macOS trials with the unchanged 1.3.0 capture script verified Codex CLI
0.159.2 project-hook capture, continuation and restart/resume without duplicates.
Bundled Codex hook discovery remained unsuccessful. Claude Code 2.1.214 bundled
capture and resume passed. These trials do not establish every host's support.

Updating does not enable capture or import history. Refresh the installed plugin,
then run guided setup from that copy; keep private data and configuration outside
plugin code. Existing project-hook paths require review after upgrades.

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
