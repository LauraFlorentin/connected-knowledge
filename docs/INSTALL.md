# Installation and platform support

Package documentation updated 2026-10-07 for 1.7.0. Host instructions follow the
vendors' documentation as checked on 2026-10-06; rows marked untested were not run
for this release. See [validation](VALIDATION.md) for what was tested.

After installing on any host that can run local commands, run `/ck-setup`
(Codex: `$ck-setup`). Installing alone connects no vault, switches nothing on and
reads no account history.

## Requirements

- macOS or Linux on the Mac that holds the vault. Windows is not supported.
- Setup, the hooks, capture and the three commands use only the Python standard
  library and run on the `python3` that ships with macOS (3.9).
- Account-export import, PDF tools, vault checks and the private MCP server need
  Python 3.10 or later with the packaged requirements (see
  [Dependencies](#dependencies-and-local-scripts)).
- If `python3` is missing, an installed host shows a shell error on every turn.
  `/ck-setup` checks for it.

## Claude Code

Marketplace install (documented form; not run for this release):

```text
/plugin marketplace add LauraFlorentin/connected-knowledge
/plugin install connected-knowledge@connected-knowledge-local
```

For development, from a clone:

```bash
claude --plugin-dir ./plugins/connected-knowledge
```

Then run `/ck-setup`. The commands also answer to their long names, for example
`/connected-knowledge:ck-setup`. The plugin registers `Stop`, `SessionEnd` and
`SessionStart` hooks. They do nothing until `/ck-setup` writes this Mac's
configuration and you switch capture on. Remote Control sessions run on the Mac
that hosts them, so that Mac's hooks and transcripts apply whichever device you
type on.

Source: https://code.claude.com/docs/en/plugins-reference

## Claude web, desktop chat and Cowork

In Customize → Plugins, add this GitHub repository as a marketplace, or upload
`distribution/claude-plugin.zip` (build it with `python3 tools/package.py`). Ask for
`ck-help` or pick a command from the `/` menu. Chat runs skills only: no hooks and
no local scripts, so setup becomes guidance and the commands prepare Markdown
instead of saving it. Cowork can run hooks and scripts when the task runs on your
computer; that route is untested.

To let chat in the Claude desktop app read and write your vault, run
`/ck-setup apps` in Claude Code on the same Mac. It offers the optional
[Filesystem MCP](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/filesystem-option.md)
connection, previews it, and installs it only if you agree.

Sources: https://support.claude.com/en/articles/13837440-use-plugins-in-claude and
https://claude.com/docs/plugins/platform-support

## Claude iPhone app

Plugins follow your account, so the skills are available as guidance. The phone
cannot reach your vault or run scripts. Phone chats reach the vault through the
Claude account export, which you request on the web or desktop app.

## Codex CLI and ChatGPT desktop (local Work)

```bash
codex plugin marketplace add LauraFlorentin/connected-knowledge
```

Then install `connected-knowledge` from `/plugins`. Codex has no plugin slash
commands; the commands are skills: `$ck-setup`, `$ck-help`, `$ck-add-session`, or
pick them in `/skills`. Codex asks you to review and trust the plugin's Stop hook
in `/hooks`, again after each hook change. Plugin hooks do not run under
cloud-orchestrated Work. The marketplace command above is untested for this
release; a local path (`codex plugin marketplace add /absolute/path/to/connected-knowledge`)
was used in earlier releases.

Sources: https://learn.chatgpt.com/docs/plugins and https://learn.chatgpt.com/docs/hooks

## ChatGPT web and iPhone

This unlisted local plugin cannot be installed there. For selected saves, connect
the private MCP app through your own tunnel (see below). For guidance only, attach
`distribution/instruction-bundle.md` to a chat or project. Chat history arrives
through the ChatGPT account export.

## Gemini CLI (experimental)

```bash
python3 tools/package_gemini.py
mkdir -p ~/ck-gemini && unzip -o distribution/gemini-extension.zip -d ~/ck-gemini
gemini extensions install ~/ck-gemini
```

The extension includes the skills and the three commands (`/ck-setup`, `/ck-help`,
`/ck-add-session`) as TOML wrappers, plus the experimental per-turn capture hook.
Installing from the repository URL is not possible yet, because the extension
manifest is not at the repository root. Gemini CLI was not available for testing.

Source: https://geminicli.com/docs/extensions/reference/

## Gemini app

There is no plugin host. Google Takeout import is planned, not built.

## Private ChatGPT selected saves

Use the [guided install/update flow](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/install-update.md).
It prepares a permanent external runtime, supports your selected vault template,
and uses your own private tunnel. ChatGPT web selected save and retry were verified
in an earlier release; desktop and mobile are separate checks. No ChatGPT directory
app is published.

The same installer can install the Python dependencies, the private tunnel client
and an optional managed Node.js with the Filesystem MCP server, and upgrades
existing runtimes while keeping configuration and identities. For broader file
access only, see the [Filesystem MCP option](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/filesystem-option.md).

## Avoid duplicate activation

Version 1.1.1 renamed the plugin from `zettelkasten-research` to
`connected-knowledge` and the marketplace to `connected-knowledge-local`. Disable
or uninstall any earlier copy before enabling this one. Use one active copy of
Zettelkasten–Obsidian per host: the plugin, or a personal copy of the skill.

## Dependencies and local scripts

From the repository or package root, with Python 3.10 or later:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/requirements.txt
```

`requirements.txt` holds pypdf, PyYAML and defusedxml. `requirements-dev.txt`
also installs the MCP runtime and reportlab for the tests and the worked example.
There are no model API calls, scheduler services or database servers to configure.

## Account title instruction

The optional text in `docs/ACCOUNT-INSTRUCTIONS.md` labels chats; the plugin never
changes account instructions by itself.

## Updating to 1.7.0

Refresh the plugin through your host's plugin manager, or upload the 1.7.0 ZIP, and
keep one active copy. Then:

1. Run `/ck-setup`. It writes one configuration file for this Mac at
   `~/.config/connected-knowledge/config.json` and a private state folder, both
   outside the vault. Capture stays off.
2. If you used capture in 1.3–1.6 through `CONNECTED_KNOWLEDGE_*_CONFIG`
   variables: those configurations keep working until `/ck-setup` has written the
   new file. After that the new file wins. Remove the old variables and any Codex
   project hook for the same projects, so each session is captured once.
3. If earlier versions saved conversations into a `ChatArchive/` folder, preview
   `ck.py migrate <that folder>`, then apply. Each conversation becomes a
   conversation note plus transcript; notes you edited are reported and left
   alone; the old folder is not changed or deleted, and a second run does nothing.
4. Account-export archives created by `chat_import.py` are rewritten once on their
   next import with the ontology's property names (`source_platform`, `source_id`,
   `source_account`) and inert message text; earlier versions stay in `revisions/`.

The private ChatGPT runtime is separate from the plugin: stop it, then run the
[install/update wizard](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/install-update.md)
against the same runtime folder, as in 1.6.0.
