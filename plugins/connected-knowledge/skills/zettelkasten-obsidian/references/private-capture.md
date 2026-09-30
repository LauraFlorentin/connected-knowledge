# Private capture — development capability

Released baseline: 1.3.1. These additions are unreleased and inactive. Save explicitly selected content from ordinary chats or project chats through the same private inbox. Archiving is a source stage; use the existing graph workflow separately to propose developed notes.

## Choose your route

| Surface | Route | Evidence and limit |
| --- | --- | --- |
| ChatGPT ordinary/project chats, desktop/mobile | `save_selected_capture` through a separately connected private MCP server | Local MCP protocol tested. Official docs support account-available plugins on desktop/mobile; actual account connection and each target app remain unverified. No universal chat-end event or history feed. |
| Codex | Existing scoped project Stop hook | Prior native test passed; bundled discovery was not proven. |
| Claude Code | Existing opt-in bundled capture | Prior native test passed. |
| Gemini CLI | Development extension AfterAgent hook | Synthetic event/process tests pass; native extension discovery and invocation unverified. One archive record per completed event, not a fabricated full-session transcript. |
| Regular Gemini apps | Explicit text/file save through manual private interface, or supplied Takeout activity | No native Gemini Apps MCP connection or automatic trigger implemented. Takeout export schema not inferred; normalize selected material explicitly before capture. |
| Claude ordinary apps | Supplied exports or selected text through private interface | No automatic all-account capture. |

ChatGPT source review: [plugin surfaces](https://learn.chatgpt.com/docs/plugins), [connect and test](https://developers.openai.com/plugins/deploy/connect-chatgpt), [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels). Gemini: [AfterAgent contract](https://geminicli.com/docs/hooks/reference/), [extension packaging](https://geminicli.com/docs/extensions/reference/), [Apps data export](https://support.google.com/gemini/answer/16920332?hl=en). Reviewed September 30, 2026. These contracts do not prove this package has been installed or enabled in those hosts.

## Private runtime configuration

Keep configuration, credentials, spool, archives and all supplied content outside the source checkout and installed package. The new interface rejects symlinks and overlapping spool/archive directories. Use a dedicated empty archive, never the live vault root. Read the actual shared vault guide before any later knowledge work. Select vocabulary `existing` for type/status or `default` for note_type/review_status; retain the user's schema. No default category is imposed.

Create a private configuration manually after selecting destinations; example values below are placeholders, not activated settings:

```json
{
  "enabled": false,
  "account": "non-secret-stable-label",
  "spool": "/absolute/private/capture-spool",
  "destination": "/absolute/private/source-archive",
  "vocabulary": "existing"
}
```

New capture runtime requires Python 3.10+ on POSIX (macOS/Linux; `fcntl` locking). Windows is not supported by this new interface yet. Install `scripts/requirements-mcp.txt` for MCP; core-only capture needs the existing requirements. No model API inference is performed.

## Selected save

`private_capture.py --config /absolute/private/config.json` reads a bounded JSON object from stdin and previews without writes. Add `--apply` only for an authorized save with enabled configuration. Disabled configurations consume no supplied content. Payload:

```json
{
  "source": "chatgpt",
  "conversation_id": "caller-stable-conversation-label",
  "capture_id": "caller-stable-selection-label",
  "title": "Fictional orchard",
  "coverage": "excerpt",
  "messages": [{"id": "selected-message-1", "role": "user", "text": "Fictional pears."}]
}
```

Use real host IDs only if available; otherwise clearly label caller-assigned identities. Do not invent provider IDs or pretend a summary is a transcript. Retain these labels in subsequent calls. Reuse capture_id for retry/revision of the same selection; a new selection uses a new capture_id. The same source/conversation/selection maps to one stable importer record. Distinct selections remain separate so partial excerpts cannot overwrite a full archive. Original supplied JSON and provenance are retained; human-edited archive notes cause a conflict. Payload limit is 1 MiB; attachments and remote URL downloads are unsupported.

## ChatGPT connection preparation

Run `capture_mcp.py` with `CONNECTED_KNOWLEDGE_PRIVATE_CONFIG` pointing to the external configuration. It uses the official Python MCP SDK 1.x and stdio only; it opens no listening HTTP/vault endpoint. It exposes one write tool, `save_selected_capture`, with accurate write/idempotency annotations and no caller-controlled account, destination or file access. Supply only content the user asked to save. Tool errors disclose a content-free error type.

Recommended first private connection: Secure MCP Tunnel, subject to account/workspace eligibility and an explicit setup decision. It requires a Platform tunnel association, runtime credential and a running tunnel client. Limit the association/access to the intended private owner; this server is single-owner, not a multi-user hosted service. Never connect it to a shared workspace/identity pool that should not access that archive. Authentication/access controls belong to the selected tunnel; stdio itself is not remote authentication. Do not expose this server through an unauthenticated forwarding service. Public OAuth hosting is a separate architecture, not implemented here.

Verify tool discovery, selected-save authorization, coverage, retries and private archive delivery separately in ordinary desktop and mobile chats. Do not claim universal capture from installation or from local protocol tests. No tunnel, account connection, capture configuration or public release is created by this package.

## Gemini CLI extension

Build `python tools/package_gemini.py`, extract `distribution/gemini-extension.zip` into a development directory, and install using the documented Gemini extension flow only when authorized. The Gemini ZIP has its own `hooks/hooks.json`; the Claude/Codex source hook registrations are unchanged. The manifest alone does not register hooks.

Set `CONNECTED_KNOWLEDGE_PYTHON` to an absolute dependency-equipped Python and `CONNECTED_KNOWLEDGE_GEMINI_CONFIG` to external private config. Add `"host": "gemini-cli"` and `"projects": ["/absolute/selected/workspace"]` to that config, retaining disabled state until selection/activation is authorized. Bash-compatible command environment required; Windows unverified.

AfterAgent supplies prompt, prompt_response, session_id, cwd and timestamp. Only exact selected workspaces and completed, non-retry events are accepted. No transcript file or full local history is read. Identity uses session_id plus timestamp; identical event replay is unchanged, later events create separate records. Separate events with different timestamps are intentionally distinct, including repeated wording. A failed event can be manually replayed with its original timestamp; process-level locking releases on termination. SessionEnd is best effort and intentionally unused. Full-session assembly and history import remain separate future work.

## Regular Gemini app history

Google documents export of Gemini Apps activity through Takeout, under My Activity > Gemini Apps; Gems export is separate. This does not establish a stable conversation/message schema or a full transcript guarantee. Retain exports privately. No Takeout parser was added based on an invented structure. Explicitly supplied normalized text can use `source: gemini-app`; a summary remains a summary. The CLI extension does not capture the regular app.
