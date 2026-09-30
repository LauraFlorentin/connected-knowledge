# Local history and ongoing session capture

`session_capture.py` adapts observed Codex and Claude Code JSONL transcript formats
into the normalized importer. This does not access ordinary Claude/ChatGPT account
history, cloud-only Codex chats, other machines, or unavailable/deleted sessions.
Formats can change; the adapter rejects unsupported or ambiguous records. Read
this together with `history-import.md` and the selected vault's actual guide.

## Obtain past history

- Claude web/desktop: Settings → Privacy → Export data. Download the emailed file
  while its link is valid (currently 24 hours). Individual Free/Pro/Max accounts
  can export; organization export access belongs to the Primary Owner. Mobile
  cannot request the export. This is separate from local Claude Code transcripts.
- Codex local history: inspect the selected host's Codex home for `sessions/` and
  `archived_sessions/`. Select only transcript folders; do not copy the entire
  configuration home, which contains unrelated state and credentials. These paths
  are observed local storage, not a guaranteed portable export API. Check each host.
- Claude Code local history: inspect the selected host's `.claude/projects/`
  transcripts separately. The history command excludes nested `subagents/`.

The adapter can use the same account label for historical and ongoing capture.
Normalized conversation IDs include host and session ID, avoiding collisions
between Codex and Claude Code. Account-export Claude chats use different provider
identities; they are not automatically merged with Claude Code sessions.

## Configure privately and preview

Copy `config/capture.disabled.json` from the repository to private runtime storage.
Use one configuration per host (`codex` or `claude-code`). Select absolute
`transcript_roots`, exact `projects` working directories, a stable non-secret
`account` label, an absolute private `spool`, and a separate absolute archive
`destination`. The latter is a dedicated importer folder, never the vault root.
Do not store configuration, exports or snapshots in the public plugin repository.
The spool retains raw transcripts including tool/system records; generated Markdown
includes only observed user/assistant text. Choose source scope accordingly.

Paths in these examples are placeholders. Use the project's tested Python runtime
with the packaged requirements installed.

```sh
python /plugin/skills/zettelkasten-obsidian/scripts/session_capture.py --config /private/capture.json --history
python /plugin/skills/zettelkasten-obsidian/scripts/session_capture.py --config /private/capture.json --transcript /selected/session.jsonl
```

Preview does not write. Inspect parsed counts, rejected files and selected projects.
The batch command reports each result and continues past a failed file; it is not
an all-or-nothing import. Once the requested scope/destination is verified, set
`enabled` to true and add `--apply`. All repeated writes use importer identities,
source integrity checks, preserved revisions and human-edit conflict detection.

## Hook configuration

Codex and Claude Code document `Stop`/`SessionEnd` hooks with `session_id`,
`transcript_path` and `cwd`. Use the existing host hook configuration mechanism
and preserve all existing hooks. A representative command hook is:

```json
{
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "/absolute/python /absolute/plugin/skills/zettelkasten-obsidian/scripts/session_capture.py --config /private/capture.json --hook --apply"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "/absolute/python /absolute/plugin/skills/zettelkasten-obsidian/scripts/session_capture.py --config /private/capture.json --hook --apply"}]}]
  }
}
```

Quote actual command paths if they contain spaces. This JSON is a setup example,
a manual alternative to the bundled hooks. Do not register both. Codex requires review/trust for unmanaged hooks.
Validate the exact installed host/version before activation. Do not install hooks
just because someone imports old history.

Hook mode emits `{}` on stdout and never injects captured text or asks the agent to
continue. Errors use stderr and exit 1, not the Stop-blocking exit 2. A failed
capture is visible in host hook diagnostics; no autonomous retry daemon is included.
The next selected event or manual invocation can retry. Success metadata is written
to `last-result.json` in the spool. A failed run leaves earlier success metadata
unchanged; do not treat it as evidence that the latest event succeeded.

When a Stop payload supplies `last_assistant_message`, the adapter checks that it
matches the last observed assistant message. A transcript not yet flushed is
rejected until a later event/manual retry; the hook payload is not appended with
an invented message identity. Subagent events are skipped. History capture has
no Stop payload and cannot independently prove a session's final response exists.

## Integrity and known limits

Snapshots in `raw/` retain selected JSONL bytes; `normalized/` retains converted
snapshots. Per-session checkpoints prevent shortened/reordered histories from
replacing longer archives after compaction. Stable provider IDs are used where
available; Codex falls back to recorded ordinals or physical line numbers, so
rewritten/rotated transcripts may need manual reconciliation. No message text is
used as an identity. System/developer content, reasoning and tool calls are not
rendered as user conversation; non-text blocks are reported as excluded. Other
unsupported host records remain only in the raw snapshot.

Raw snapshots remain outside the vault in the private spool; the normalized source
records reference them. There is no automatic pruning, cloud transfer, attachment
extraction, ontology classification or graph generation in a hook. Use the graph
workflow on captured material after collection. Hook execution cannot establish
cross-device sync or complete account-history coverage.

Locks and atomic individual writes protect normal operation, not a multi-file
transaction. Inspect interrupted runs, raw snapshots and importer manifests before
recovery; never clear an active lock or discard human edits. Spool raw data can grow
with repeated whole-session snapshots; retention needs a separately chosen policy.

## Verified scope and sources (2026-09-29)

Synthetic regression tests cover preview, repeated/appended sessions, raw retention,
project allowlists, disabled writes, incomplete JSONL, shrinking history, session
mismatch, unflushed final messages, UUID/parent handling, non-text exclusion and
hook error behavior. Read-only local format trials also parsed existing transcript
files; no hook has been installed or observed firing in a live host by this change.

- [Claude export instructions](https://support.claude.com/en/articles/9450526-export-your-claude-data)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks): transcript format is not a stable interface.
- [Claude Code hooks](https://code.claude.com/docs/en/hooks): event fields and host behavior.

## Synthetic runtime and recovery checks — 2026-09-30

The regression suite invokes the actual command-line hook interface in subprocesses
with synthetic Codex and Claude Code events and temporary transcripts. It checks
Stop → append → SessionEnd → repeat, incomplete JSONL retry, unflushed final-message
retry, checkpoint-write failure after a completed import, existing locks, changed
normalized snapshots, and an interrupted note/manifest pair. These are adapter
runtime tests, not evidence that an installed host fired the hook. No live hooks
are registered by the tests.

Recovery rules:

- Incomplete/unflushed transcript: wait for the selected writer to finish, then
  retry the same session. Do not invent the missing message.
- Checkpoint failure after a completed import: retry the complete same transcript;
  importer identity makes the archive update a no-op and restores the checkpoint.
- Existing lock: first establish the writer is stopped. Preserve state before
  removing only a confirmed abandoned lock. The adapter never clears it automatically.
- Changed snapshot or human-edited note: stop and preserve the file; reconcile
  against original evidence. Never overwrite to make the test pass.
- Interrupted note/manifest pair: automatic retry stops. Back up the archive,
  manifest, spool and note. Inspect the mismatch and explicitly reconcile it, or
  rebuild into a new empty archive from preserved sources. Do not delete the old
  archive or reconstruct human edits from a generated transcript.

`last-result.json` describes the last successful invocation only. Use the current
hook exit status/stderr to detect failure. A retry daemon, automatic lock expiry,
transactional multi-file recovery and storage retention policy are not included.

## Bundled hooks: release-review decision (2026-09-30)

Both [Codex](https://learn.chatgpt.com/docs/hooks) and
[Claude Code](https://code.claude.com/docs/en/plugins-reference) support a bundled
`hooks/hooks.json`. The package now ships default registration with an opt-in launcher; see [bundled hooks](bundled-hooks.md). Manual history
import and guided setup need no hooks. For convenient ongoing local capture, the
bundled launcher returns without reading transcripts when its private
configuration is absent or disabled. Validate host, Python dependencies, selected
projects and destinations before enabling it. Package-relative script paths avoid
stale installation-cache paths. Never package personal paths or chat data.

Use one registration per host; remove duplicate manually configured capture hooks
when deliberately switching to bundled registration. Codex requires trust of the
current hook definition even after installation. Synthetic adapter tests do not
prove registration, host firing or runtime dependencies. Test those separately.

[OpenAI configuration documentation](https://learn.chatgpt.com/docs/config-file/config-reference)
currently states that plugin/local command hooks are unsupported under cloud
orchestration, even with local tools. Supported local-only Work/Codex sessions are
a separate route. This plugin cannot promise all-chat capture from ordinary Chat
or cloud Work. Keep private history outside plugin installation/data directories
that may be removed during upgrade/uninstall.
