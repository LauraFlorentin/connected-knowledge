# Private ChatGPT setup

This release provides a guided private installation on macOS/Linux with Python 3.10+.
It saves explicitly selected text into your own existing vault. Installing the plugin
alone does not activate capture. Windows private runtime is unsupported.

## One guided installation

Use the [install/update wizard](install-update.md). From the extracted plugin root:

```sh
python3 skills/zettelkasten-obsidian/scripts/install.py --wizard
```

The wizard installs the selected local components and upgrades existing private
runtimes while retaining their settings, identities, templates and state. Optional
vault tools and Filesystem MCP are selected separately. It previews before applying.
System Python 3.10+ is a prerequisite. Account authorization is completed below.
The machine running the connection must have access to the vault and stay available.
The released 1.5.0 package has the earlier fresh-install-only wizard; the unified
installer is currently an unreleased source change.

## Account connection

Create a private tunnel in [Platform settings](https://platform.openai.com/settings/organization/tunnels)
using your own organization/account. Runtime permissions are **Tunnels Read + Use**;
creating the tunnel requires **Read + Manage**. ChatGPT developer-mode eligibility
is separate. Select the intended organization/workspace explicitly; do not guess
unidentified workspace IDs. See [official tunnel setup](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

Run the connection command printed by the wizard. It asks for the restricted key
through a hidden local prompt and keeps it in memory. Never paste keys into a chat.
In ChatGPT Plugins choose Add → Create MCP App → Tunnel and enter your tunnel ID.
Use no additional MCP authentication for this single-owner stdio server: access is
controlled by your private tunnel association. Do not share it with other accounts.
Give the connection a useful name, such as Connected Knowledge.

Ask the connected tool to save one harmless sentence. Check its returned note name
and open it in `Inbox/ChatGPT Captures`. This is the only onboarding save check;
users do not repeat the plugin's development suite.

## Templates

Read the actual vault guide first. Choose a source-note or conversation-review
template from the configured Obsidian Templates folder. The original template is never modified. If you leave this blank,
the plugin uses its bundled capture template for the selected property vocabulary.

Supported plain Markdown placeholders: `{{title}}`, `{{date}}`,
`{{date:YYYY-MM-DD}}`, `{{id}}`, `{{source_file}}`, and `{{capture}}`.
Other placeholders fail during preview. Templater JavaScript, Dataview and other
community-plugin code are never evaluated. Without `{{capture}}`, exact supplied
messages and provenance are appended under Captured source. Static template sections
remain available for later human review. Source capture does not fill derived ideas,
decisions, entities or task commitments automatically.

Template properties remain, with source provenance filled from the capture.
New notes use `status: auto` or `review_status: draft`; capture never certifies
review. Existing `type/status` and default `note_type/review_status` remain separate.
Unknown source dates stay unknown. Filenames combine a readable title and stable
identity suffix. Retries and title revisions reuse the original filename. Human
edits and missing/changed preserved originals block replacement.

## Connection status and optional startup

Use the runtime's Python, not your system Python, for these commands. Substitute
the private runtime path printed by your wizard:

```sh
RUNTIME="$HOME/.local/share/connected-knowledge"
"$RUNTIME/venv/bin/python" "$RUNTIME/scripts/private_runtime.py" status --runtime "$RUNTIME"
"$RUNTIME/venv/bin/python" "$RUNTIME/scripts/private_runtime.py" store-key --runtime "$RUNTIME"
"$RUNTIME/venv/bin/python" "$RUNTIME/scripts/private_runtime.py" startup --runtime "$RUNTIME"
```

`store-key` uses a hidden local prompt and stores the key only in macOS Keychain or
supported Linux Secret Service/KWallet. Plaintext backends are refused. Linux needs
an available unlocked credential store; otherwise use foreground mode.
`startup` previews a user LaunchAgent or systemd unit. Add `--apply` to write it,
then run the displayed activation command. Startup runs after user login; recovery
without login/unlocking is not promised. Do not activate startup while another
foreground connection is running. Ctrl-C stops foreground mode.

To stop automatic startup, use `launchctl bootout gui/$(id -u) <printed plist path>`
on macOS, or `systemctl --user disable --now connected-knowledge-private.service`
on Linux. Keep notes and preserved originals when uninstalling. Revoking the runtime
key or disconnecting the ChatGPT app revokes its connection; do not delete unrelated
credentials or services. For an interrupted unified installation, retain the runtime
and rerun the same setup as described in [installation recovery](install-update.md).

## Coverage

ChatGPT selected-save MCP and extracted installer paths are tested with synthetic
content. Native ChatGPT web save/retry succeeded during development; desktop/mobile
verification is separate. Account eligibility and availability vary. The Gemini CLI
AfterAgent extension is experimental until its native host is verified; synthetic
extension execution passes. Ordinary Gemini/Claude apps use supplied exports or
selected text; no automatic all-account capture is implemented. Native Codex project
and Claude Code hook evidence remains documented in their own references.

The private tunnel is for user-managed private connections, not public ChatGPT
directory distribution. Downloadable packages are distributed through this repository.
No multi-user hosted service, inference API billing, or public vault endpoint is installed.
