# Guided installation and runtime updates

Use this flow when the user requests installation, an update of an existing private
runtime, or installation of the optional Filesystem MCP. Reuse choices and task
authorization already supplied. Read the actual vault guide before choosing its
templates or note conventions. Plugin development alone does not authorize changing
the user's installed copy, private runtime, host settings or account connection.

Version 1.6.0 replaces the earlier fresh-install wizard with this shared flow. Downloading or
updating a plugin alone does not execute it. Run it from the new source/package on
the machine that has access to the selected vault.

## One entry point

On macOS/Linux, with Python 3.10+ already installed, run from the extracted plugin:

```sh
python3 skills/zettelkasten-obsidian/scripts/install.py --wizard
```

In a repository checkout, prefix the script path with `plugins/connected-knowledge/`.
The older `private_setup.py --wizard` entry point opens this same flow. Its explicit
non-wizard arguments remain a low-level fresh-setup interface.

The wizard selects a private runtime folder, then reuses its existing configuration
or asks for an existing vault, vocabulary, source template, non-secret account label
and tunnel ID. Scoped vault reading/previews, developed-note saving, and broader
Filesystem access each require their own selection. Existing bridge and Filesystem
settings are retained during an upgrade. It shows a plan before applying it.

The installer provides:

- An isolated Python environment and the required Python packages.
- The official OpenAI tunnel client, with the vendor archive checksum checked,
  when the private connection is selected.
- Its own Node.js **24.21.0** and pinned Filesystem server **2026.8.31**, when selected.
  Node's vendor checksum is checked; npm install scripts are disabled, and the
  resolved dependency lock is retained in that runtime generation.
- Optional registration of one named Filesystem entry in the selected Codex TOML
  or Claude Desktop JSON file, with a backup and unrelated settings preserved.
  A matching entry is reused, including its enabled state and approval settings.

Keep at least 1 GiB free for staging and retained versions; large dependency
changes may need more. The installer checks available space before downloading.
It does not install system Python, Obsidian, a desktop host, account authorization,
background collection or a startup service. Windows is unsupported. A fresh
private connection uses a fresh capture archive; an existing archive must be
updated through its original runtime to retain source identities.

## Existing runtime

Stop the existing connection, including automatic startup if enabled. Use the
stop instructions in [private setup](private-setup.md). Restart Filesystem host
connections after applying an update so their processes load the selected version.
From the new package, preview and then apply:

```sh
python3 skills/zettelkasten-obsidian/scripts/install.py \
  --runtime "/absolute/private/Runtime"
python3 skills/zettelkasten-obsidian/scripts/install.py \
  --runtime "/absolute/private/Runtime" --apply
```

This upgrades earlier copied runtimes as well as managed installations. It keeps
the existing account/archive/tunnel identities, credentials, templates, profiles,
spool, bridge journal and configuration. A deliberate bridge change is the only
private configuration update supported by the answers format below; omit it to
preserve the original bytes. Do not move or rename the runtime during an upgrade:
its stable path is part of credential and startup identity.

Each update stages complete code and dependencies, validates the selected settings
without writing vault notes, and performs synthetic save/retry checks in temporary
storage. A selected Filesystem server is tested against temporary folders for read,
write and outside-scope denial. Only after validation does the runtime select the
new generation. The preceding generation and replaced entry points/configuration
are retained. Repeating an unchanged setup reuses the installed generation.

This is an explicitly invoked migration, not a background auto-updater. Dependency
versions within supported Python ranges and npm transitive dependencies may differ
between installations; receipts and the generated npm lock record the installation.

## Assistant-supplied choices

For a noninteractive session, save the selected values to a private JSON file
outside the plugin. These examples are placeholders, not installation defaults:

```json
{
  "runtime": "/absolute/private/Runtime",
  "private": {
    "vault": "/absolute/Existing Vault",
    "account": "personal-chatgpt",
    "tunnel_id": "tunnel_00000000000000000000000000000000",
    "vocabulary": "existing",
    "template": "/absolute/Existing Vault/Templates/Source.md"
  },
  "filesystem": {
    "host": "codex",
    "directories": ["/absolute/Existing Vault/Knowledge"],
    "name": "connected-knowledge-filesystem",
    "version": "2026.8.31",
    "register": true,
    "host_config": "/absolute/host/config.toml"
  }
}
```

Omit `private` on upgrades to preserve existing identities. Omit `filesystem` to
retain a managed selection or leave it uninstalled on a new runtime. A Filesystem-only
installation is supported. Set `register` to false (or omit it) to prepare a command
without modifying host settings; `stdio` is available for other local hosts.
Omit `template` on a fresh setup to use the bundled source template.

An optional top-level `bridge` object uses the settings documented in
[vault-bridge.md](vault-bridge.md), without the outer `vault_bridge` key. Supply
only explicitly selected scope, guide/templates and write permission. Existing
settings remain unchanged when it is omitted. Do not put secrets in the answers file.

```sh
python3 skills/zettelkasten-obsidian/scripts/install.py --answers "/private/setup.json"
python3 skills/zettelkasten-obsidian/scripts/install.py --answers "/private/setup.json" --apply
```

The first command previews without downloads, runtime writes or host changes.
The second applies the selected setup; do not add another consent prompt when the
user's task already authorizes those actions. Report any host connection still pending.

## Connection and recovery

Use the printed private `connect_command`, then complete the account association
in [private setup](private-setup.md). Keys stay in a hidden local prompt or the
existing OS credential store. No key is requested by this installer. The connection
is not started automatically. Refresh the host's tool discovery after reconnecting.

Filesystem registration can cause the host to launch that server when it reloads
its configuration. Close its settings editor while applying changes. Inspect
`list_allowed_directories` before accessing files: client MCP Roots can replace
the startup directory list. Selected folders permit writing as well as reading.
Follow [Filesystem scope checks](filesystem-option.md). Local registration does
not establish ChatGPT web/mobile access.

If downloading or validation fails, the previous generation remains selected.
Unselected staging folders may remain for diagnosis. If interruption occurs during
the brief publication step, stable launchers refuse to run while
`install-pending.json` exists. Rerun the same setup with the original selections
to complete it; retain the journal, previous generations and private data. There
is no automatic rollback or generation cleanup command.

If a different host entry already uses the chosen name, the runtime installation
finishes but reports `host_connection.status: pending` and exits 3. It leaves that
entry unchanged. Resolve the conflict or select another name and rerun. A retry
with unchanged selections can complete host registration without reinstalling
dependencies. Other failures exit 2. `install-receipt.json` records the latest result.

Keep backups private. A successful synthetic check establishes local runtime
behavior, not account eligibility, native host discovery, live-vault access or
cross-device synchronization. These require a separately authorized connection trial.
