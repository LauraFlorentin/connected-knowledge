# Optional Filesystem MCP

Use the focused [vault bridge](vault-bridge.md) for the normal connected-note
workflow. Offer Filesystem MCP when the user requests broader file management or
chooses an existing general file connection. This is an opt-in setup option;
Connected Knowledge does not install, bundle, register or activate it by default.

The upstream [Filesystem MCP server documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
describes a local Node.js server with file reading, writing, searching and moving
tools. Its access comes from selected command-line directories or client-provided
MCP Roots. Client Roots replace the command-line directory list; check the effective
scope with `list_allowed_directories` after connecting and whenever Roots change.
A selected folder is not a read-only permission: the server includes write tools.

## Set up the selected option

1. Reuse an existing Filesystem connection when it already has the user's intended
   scope. Inspect the actual host's connection configuration before changing it.
2. For a new connection, select the local host, exact folders and a reviewed package
   version. Use the [install/update wizard](install-update.md) to install its
   managed Node.js/server and optionally register one host entry. Reuse choices already
   supplied; ask only for missing selections. Read the actual vault guide before
   proposing changes to notes. Setup does not need to read note contents.
3. Inspect the effective allowed directories and test one harmless selected file.
   Limit access to the selected folders; do not use the home directory as a default.
4. Follow the existing guide, templates, source, identity and revision conventions.
   Preview requested changes and use existing task authorization; do not ask for
   redundant approval for an already authorized save. Verify actual saved files.

## Complete installation

The [unified installer](install-update.md) offers Filesystem as an optional component.
It downloads a managed Node.js and pinned server into the private runtime, validates
synthetic file access, and can merge the selected connection into the host settings.
Existing unrelated connections and approval policies are retained. This route does
not require a separately installed Node or npx. It is an unreleased source addition;
the 1.5.0 release contains the configuration-only helper described below.

## Configuration-only setup helper

On macOS/Linux with Python 3.10+, run from the extracted plugin root:

```sh
python3 skills/zettelkasten-obsidian/scripts/filesystem_setup.py --wizard
```

The wizard asks for a local host and one or more existing folders. It prints a
no-write preview with the exact package version, resolved folders and connection
settings. It does not install Node, download the server, edit host settings, read
notes, or activate a connection. This helper uses only Python's standard library.

For assistant-supplied choices, use explicit arguments instead of interactive input.
Replace these example paths with the selected values:

```sh
python3 skills/zettelkasten-obsidian/scripts/filesystem_setup.py \
  --host codex \
  --directory "/absolute/selected/Notes" \
  --version 2026.8.31 \
  --output "/absolute/private/filesystem-setup"
```

Repeat `--directory` for separate folders. Add `--apply` to save the reviewed setup
files only. The output needs an existing parent and a fresh destination outside
the selected folders and plugin repository. Existing and interrupted setups are
preserved. The output contains `setup.json`, a host fragment and `SETUP.md`; keep
these private because they include local paths. Directory/file permissions are
700/600. No personal paths belong in the distributed plugin.

The helper resolves folder aliases, collapses duplicates and rejects missing
folders, overlapping selections, the whole home directory and its ancestors.
Select a narrower scope if rejected. A folder allowlist is not a read-only mode.
Exact stable versions are required; `latest`, ranges and shell commands are refused.
The default is the tested **2026.8.31**, not a floating latest release. Changing
`--version` requires reviewing and testing that version separately.

## Add the selected connection

The host machine needs Node.js and npx. The preview uses the local npx path when
available; `--npx /absolute/path/to/npx` can supply it explicitly. Ensure Node is
also available to the desktop host's environment. The first authorized launch
downloads the pinned npm package and dependencies, with install scripts disabled.
Only the top-level package is pinned; transitive dependencies may resolve
differently. This helper does not provide an offline or locked runtime.

| Host choice | Prepared settings | Activation |
| --- | --- | --- |
| `codex` | `codex.fragment.toml` | Review and merge only the named table into the existing host configuration. It starts with `enabled = false`; enable it when connection activation is authorized and restart the host. |
| `claude-desktop` | `claude-desktop.fragment.json` | Review and merge only the named `mcpServers` entry into the existing desktop configuration. Adding it and restarting the host activates it. |
| `stdio` | `stdio.fragment.json` | A command and separate arguments for another local stdio-capable host. Follow that host's current configuration instructions. |

Preserve existing settings; never replace a whole host configuration with a
fragment. The default entry name is `connected-knowledge-filesystem`; `--name`
can select another name when needed. Inspect existing entries first to avoid a
duplicate connection. Consult [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
or [upstream Claude Desktop instructions](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem#usage-with-claude-desktop).
No tool-approval policy is changed by these fragments.

After connection, inspect `list_allowed_directories` and compare the effective
folders with the user's selection before accessing files. Correct a mismatch
first. Client Roots can replace the requested startup scope, so repeat this check
when they change. For a write trial, use a harmless selected temporary note, preview
the intended content, save under existing authorization, and read it back.

Local settings do not establish ChatGPT web/mobile access. Do not add the server
to plugin manifests, reuse private capture tunnel credentials, or expose a new
endpoint as part of selecting this option. Windows users should consult upstream
setup instructions; this helper and its native Windows host behavior are unsupported.
To disconnect, disable or remove only this named connection and restart the host.
Keep notes and unrelated settings.

A general file tool does not itself supply Connected Knowledge's duplicate,
source-preservation or conflict handling. Those checks remain part of the assisted
workflow. The vault bridge has its own separately enabled save operation. Documenting this
optional server enables neither connection nor writer. If saving is requested
and no authorized write route is available, report the prepared result accurately.

## Verification

Upstream behavior checked October 5, 2026. Development coverage and native-host
limits are recorded in the repository's `docs/VALIDATION.md`. The repository also
includes an explicit networked trial:

```sh
python3 tools/verify_filesystem_mcp.py --version 2026.8.31
```

Run it with the development dependencies and Node/npx installed. It downloads and
executes the selected upstream package with an isolated temporary npm cache, uses
only synthetic temporary files, and checks tool discovery, read/search/write,
edit preview/readback, move, denied out-of-scope access and client Roots replacement.
It creates no host connection. Ordinary tests and package builds use no npm network
access. A successful protocol trial does not establish native host or live-vault
access; verify the effective scope in the intended host before use.
