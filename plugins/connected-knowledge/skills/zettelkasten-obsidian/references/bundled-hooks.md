# Bundled capture hooks

The package ships one `hooks/hooks.json` with `Stop`, `SessionEnd` and
`SessionStart` command hooks, all calling `hooks/capture.py`. Claude Code and Codex
discover the file by default; do not also declare it in a manifest, or capture can
run twice. Gemini CLI uses its own `integrations/gemini/hooks.json` (experimental,
unchanged in 1.7.0).

## What the hooks do

The hooks are inert until `/ck-setup` has written this Mac's configuration
(`~/.config/connected-knowledge/config.json`) and capture is switched on for this
host. Then:

| Event | Action | Cost |
| --- | --- | --- |
| `Stop` (every turn) | Write or refresh one small queue entry: host, session ID, transcript path, working folder. If another queued session has already ended or gone quiet, start a sweep in the background | A few milliseconds; the transcript is never opened |
| `SessionEnd` | Mark the entry ended, then start a sweep in the background | The hook returns at once |
| `SessionStart` | Start a sweep in the background for sessions that went quiet | The hook returns at once |

The sweep (`scripts/ck_sweep.py`) holds an operating-system lock that disappears
with its process, so a killed or timed-out capture can never block later ones. A
second sweep that finds the lock taken simply returns. Each queued session is
captured once it has been quiet for `idle_minutes` (default 10) or has ended: the
transcript is read once, one raw copy is kept in the private state folder (replaced
as the session grows), and one conversation note plus one transcript are written to
the vault. A failure leaves the queue entry for the next sweep; after five failures
it is parked in `failed/` and reported by `/ck-help`.

Sessions are queued only when their working folder is inside a capture folder and
not inside an excluded one. Subagent events are skipped. Stdout is always `{}`:
the hooks never inject text into the session and never block it. Errors go to
stderr with a content-free message and exit code 1.

The hook path uses only the Python standard library, so the stock macOS `python3`
(3.9) is enough. The command is `"${CONNECTED_KNOWLEDGE_PYTHON:-python3}"`; set
`CONNECTED_KNOWLEDGE_PYTHON` only if `python3` is not on the host's PATH. A
missing interpreter shows a shell error on every turn, so `/ck-setup` checks for it.

## Hosts

- **Claude Code** runs all three events. Remote Control sessions run on the Mac
  that hosts them, so that Mac captures them. Which device you typed on is not in
  the transcript; set `default_remote_device` in setup, or pass `--device` to
  `/ck-add-session`.
- **Codex** asks you to review and trust the hook in `/hooks`, again after every
  hook change. Its bundled-hook discovery and its handling of `SessionStart` and
  `SessionEnd` need a native re-test; Codex documents a short `SessionEnd` budget,
  which is why that hook only queues and hands off.
- **Cowork** reads the same file when its task runs on your computer; untested.
- **Chat apps** (Claude, ChatGPT, Gemini on any device) have no hooks. Their
  history arrives through account exports or selected saves.

## Turning capture on and off

```bash
python3 <plugin>/skills/zettelkasten-obsidian/scripts/ck.py capture on --apply
python3 <plugin>/skills/zettelkasten-obsidian/scripts/ck.py capture off --apply
```

Or run `/ck-setup capture`. Turning capture off stops new queue entries; queued
sessions stay until capture is on again or you run `/ck-add-session`.

## Older configurations (1.3–1.6)

Without a machine configuration, the hook keeps the earlier behaviour: it reads
the private JSON named by `CONNECTED_KNOWLEDGE_CODEX_CONFIG` or
`CONNECTED_KNOWLEDGE_CLAUDE_CODE_CONFIG` and, when that file says
`"enabled": true`, captures the session inside the hook through
`session_capture.py`. Once `/ck-setup` has written the machine configuration, that
configuration is used instead. Remove the old variables and any Codex project hook
for the same projects, so each session is captured once, and move the old archive
with `ck.py migrate`.

## Testing without a real vault

The regression suite runs the hook command in subprocesses with a temporary home
folder, a synthetic configuration, synthetic transcripts and a temporary vault.
It covers: no configuration, capture off, out-of-scope folders, subagents, an
unreadable transcript (the hook still queues, proving it never opens it), the
sweep's idle rule, a killed lock holder, a crash between writes, two sweeps at
once, and growth over 60 turns. No hook is registered in a real host by the tests.

Sources: [Claude Code hooks](https://code.claude.com/docs/en/hooks),
[Claude plugin reference](https://code.claude.com/docs/en/plugins-reference),
[Codex hooks](https://learn.chatgpt.com/docs/hooks).
