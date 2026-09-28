# Future chat capture: select an actual route

Capability review: 2026-09-28. Recheck the named host/version, account, runtime and tool permissions at setup time. The package currently contains collection scripts and instructions; it does not contain a deployed MCP service, registered logging hook or ChatGPT/Claude account-history importer.

## Separate capture from delivery

A vault connection answers “where can we search, read and write?” It does not by itself answer “which conversation messages can we obtain, and what triggers capture?” A title/settings instruction supplies neither connection nor reliable trigger. An Obsidian community plugin is a different host component from this AI-host plugin.

| Route | What can be automated | Required implementation or user step |
| --- | --- | --- |
| Selected save in a native chat | On “save this,” the assistant can prepare available context and call an authorized destination tool. | Connect the actual vault or an inbox; label summary/excerpt coverage; verify the write. An instruction does not guarantee an automatic save after every chat. |
| ChatGPT Work / Codex lifecycle | Official plugin docs describe hooks in the Codex runtime, including Work. Hooks can send logs or summaries at supported events. | Deploy trusted scripts in that runtime, verify event payloads and transcript availability, add an idempotent adapter and test that exact surface. A web plugin installation alone does not deploy scripts. |
| Claude Code lifecycle | Documented hooks expose session identity and a transcript path, with turn/session events. | Implement and register an adapter for the actual runtime; verify completeness and failure handling. Do not infer equal coverage for all Claude consumer-app conversations or every Cowork surface. |
| Periodically supplied account exports | Local collection can preserve exports after they arrive; an importer could reconcile conversations. | User requests/downloads exports; platform-specific bulk parsers are still missing. A watcher cannot cause an unsupported export to happen. |
| Own multi-model chat client | Log messages sent through that client at creation time. | Build/use an API-based client, pay applicable API usage and accept that chats conducted elsewhere are outside its capture scope. |
| Browser capture extension | Potentially capture supported browser conversations. | Select and assess a specific extension. It is not evidence of capture inside the native phone/desktop apps. |

No verified universal all-conversation endpoint or cross-app “chat finished” event was established for personal ChatGPT + Claude accounts in this review. Keep this an explicit coverage gap, not an assertion that no integration could ever exist. Enterprise compliance access is a separate plan/admin-controlled route, not a personal API-key feature.

## Destination for desktop and phone

Prefer the user's existing compatible file tools. For a new reusable connector, require scoped search, read and create-or-update by stable ID, version-checked writes, duplicate request handling and clear success/error results. Reuse a suitable existing service before building an MCP server. Never expose an unauthenticated vault write endpoint.

For phone/cloud use, a local path or localhost server is insufficient by itself. Options include an authenticated reachable inbox plus a transfer worker, or supported remote access to a connected desktop folder. Choose one authoritative write destination and reconcile sync conflicts; Obsidian sync alone does not give the assistant file access. Verify arrival at the vault separately from acceptance by an inbox.

Current Claude Cowork docs describe connected-folder access from web/mobile through an open desktop app for a session started on desktop. Claude remote MCP instead connects from Anthropic's infrastructure to a reachable server. These are different routes. ChatGPT plugins available to an account can work on mobile, but Desktop-only components do not; validate the particular plugin and runtime instead of assuming parity.

## Before enabling unattended collection

Establish selected accounts/projects, inclusions/exclusions, source coverage (raw messages versus summaries), trigger, durable destination, runtime, retention and processing policy. Provide a preview and verify one capture. Then test: repeated event; revised conversation; interrupted/ambiguous write; offline destination; attachment/branch gaps; excluded record. Keep failure reports visible and retry safely by identity/version. Raw capture must not automatically generate a permanent note for every utterance.

Prefer turn-completion capture with stable IDs when the host supports it, rather than assuming closing a UI fires a session event. Codex transcript format is not a stable interface. Claude Code documents that the final assistant message may not yet be in the transcript at Stop time on all versions; account for that before claiming a complete transcript. Store source versions and flag incompleteness rather than infer missing text.

This is a setup specification. No selected source, trigger, connector or unattended logging behavior has been enabled by reading it.

## Official references checked

- [ChatGPT plugins](https://learn.chatgpt.com/docs/plugins): supported surfaces, Desktop-only limitations, Work/Codex hook runtime and deployment requirements.
- [Codex hooks](https://learn.chatgpt.com/docs/hooks): lifecycle, session identity, transcript path and format caveat; switching away is not immediate SessionEnd.
- [Claude Code hooks](https://code.claude.com/docs/en/hooks): event data and Stop transcript caveat.
- [Claude Cowork surfaces](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile): connected-folder dependencies across surfaces.
- [Claude remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp): connection origin and reachability.
- [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state): persistence for API-created conversations; this page does not establish consumer-app account-history access.

The adapter, duplicate-handling contract and suggested architecture above are our implementation design, not claims that these components already ship or that a documentation page recommends this vault workflow.
