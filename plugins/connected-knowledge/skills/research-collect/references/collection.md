# Configure a reviewable inbox

Minimal disabled starting configuration:

```json
{
  "inbox": "/USER_SELECTED/research-inbox",
  "ongoing_enabled": false,
  "excluded_ids": [],
  "sources": []
}
```

Add only sources chosen by the user. IDs are stable configuration identities; changing one creates a separate import namespace.

```json
{"id":"selected-documents","kind":"local","enabled":true,"path":"/USER_SELECTED/documents","glob":"*.pdf","max_items":100}
```

```json
{"id":"selected-feed","kind":"feed","enabled":true,"url":"https://USER_SELECTED/feed.xml","allowed_hosts":["USER_SELECTED"],"max_items":100}
```

```json
{"id":"selected-page","kind":"url","enabled":true,"url":"https://USER_SELECTED/article","allowed_hosts":["USER_SELECTED"],"max_bytes":20971520}
```

Replace placeholders before use. Paths are resolved against the config file directory. Choose a separate inbox, not a parent/child of a local source folder. `glob` can be `**/*.pdf` when recursive scope is explicitly selected. Defaults process at most 100 entries per source; a reached cap is reported incomplete. Narrow the source or adjust the cap deliberately. No secrets or tokens belong in this config.

RSS/Atom collection retains entry XML and links only. Article retrieval is a separate selected URL source; automatic enclosure following is not implemented. URL captures retain the response bytes and resolved URL; inspect for login pages and incomplete/dynamic content. Local `.eml`, JSON chat exports and other files are preserved as raw files, not parsed into complete threads. Inspect their actual formats during later import with the foundation skill.

## Runtime choices

| Environment | What can run | What must be supplied |
| --- | --- | --- |
| Local Claude Code / Codex shell | All scripts with dependencies and authorized paths | Actual source config and a running computer |
| Claude Cowork / ChatGPT Work with execution | Scripts when its environment has files, dependencies and network | Authorized folder/connector access; durable destination |
| Claude or ChatGPT chat without execution | Instructions, pasted material, proposed notes | A capable execution environment or manual script run |
| Phone | Review, selected sharing/upload, supported connected workflows | A remote runtime/connector for ongoing collection; phone cannot run these desktop scripts by installation alone |
| Authenticated email/cloud research | Use existing authorized connector to export selected material | Connector, account permissions, query scope and stable message IDs |

Current installation support is in package platform instructions. Capabilities depend on actual tools, not the client label alone. No bundled connector can read all ChatGPT, Claude, Kimi or email account histories.

## Ongoing collection is opt-in

Resolve exact sources, filters, inbox, cadence/timezone, runtime, retention, exclusions, and whether only collection is automated. Start with a one-time preview. After the user selects ongoing behavior, set `ongoing_enabled: true` and separately configure an OS scheduler or an available platform task capable of executing the script against durable storage. Invocation: `python /absolute/path/collect.py --config /absolute/path/config.json --scheduled`.

On macOS a user-configured launchd job can invoke that command; cron or a job runner is another option where supported. This package creates none. Keep stdout/stderr and alert on a nonzero exit. A scheduled ChatGPT/Claude prompt needs its own durable connector/runtime and does not inherit a local laptop path. Do not promise it runs while a local computer is off. Changing a schedule to a reminder is not equivalent automation.

## Inspect outcomes

Each run writes a report under `runs/`; raw bytes under `raw/`; versioned provenance under `records/`; review receipts under `review/`. `state.json` maps source identity and content version to saved captures. Do not edit immutable raw bytes. Changed inputs create versions. Failed sources do not prevent independent sources from completing. Exclusions refer to the identity printed in receipts/reports. Missing or altered archived captures are failures, not silent reimports. Preserve state and exclusions together when moving the inbox.

The collector uses a single-writer lock. Following abnormal termination, verify that no run is active before removing a stale lock. Unindexed capture files indicate interrupted finalization and need inspection; no destructive recovery command is provided.
