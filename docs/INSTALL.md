# Installation and platform support

Initial installation review: 2026-09-27. Mobile, connected-folder and hook guidance refreshed on 2026-09-28. Native host installation has not been exercised in this build environment: Claude Code and Codex binaries are unavailable, and no account settings or marketplace publication were changed. The supported file layouts are packaged and locally checked; host access and administrator policies still apply.

## Get the source

Clone the private repository while authenticated to a GitHub account with access:

```bash
git clone https://github.com/LauraFlorentin/connected-knowledge.git
cd connected-knowledge
python3 tools/package.py
```

The build creates the upload ZIP and instruction bundle used below. Repository access and plugin installation are separate steps.

## Claude web, Desktop Chat, and Cowork

In Customize > Plugins, use the custom-plugin upload option with `distribution/claude-plugin.zip`. The ZIP has `.claude-plugin/plugin.json` and `skills/` at its root. Select a bundled skill from the available skill/command menu. Ask: “Use Develop Knowledge (`zettelkasten-obsidian`) to onboard my existing vault” or “Use Collect Research (`research-collect`) to prepare a disabled source configuration.”

Official documentation supports custom plugins in Claude. Current Cowork surface documentation also lists skills/plugins on mobile; account rollout and runtime capabilities still apply. Phone installation of this package has not been tested. Installation alone does not establish Mac-vault access. Scripts require dependencies and authorized files. Connected-folder access from mobile/web depends on an open desktop app and a session started on desktop; remote MCP is a separate route.

Source: https://support.claude.com/en/articles/13837440-use-plugins-in-claude

Mobile/file-access source: https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile

## Claude Code: local native plugin

From the extracted package root, test with:

```bash
claude --plugin-dir ./plugins/connected-knowledge
```

For reusable local marketplace installation, use Claude Code's plugin marketplace flow with this package root (it contains `.claude-plugin/marketplace.json`), then select `connected-knowledge` from `connected-knowledge-local`. The direct `--plugin-dir` route avoids requiring marketplace publication. Local terminal execution can run all bundled scripts once dependencies are installed. No MCP server or hooks are declared.

Source: https://code.claude.com/docs/en/plugins-reference

## ChatGPT desktop / Codex: local native plugin

The package includes `.agents/plugins/marketplace.json`, pointing to `./plugins/connected-knowledge`, with a portable `plugin.json` and Codex compatibility manifest. On a supported local setup:

```bash
codex plugin marketplace add /absolute/path/to/connected-knowledge
```

Open the ChatGPT desktop Plugins directory, locate `connected-knowledge-local`, and install the plugin. Local source availability varies by surface; if it does not appear, use the instruction-bundle route below and check your app's local-plugin support. Registration alone is not installation or successful execution.

Source: https://developers.openai.com/plugins/build/plugins

## ChatGPT web and mobile

Official documentation supports plugin-bundled skills in Chat and Work on web, desktop and mobile. That does not make this unlisted local package available everywhere. A published/shared account-accessible plugin needs the appropriate distribution process; this delivery does not publish it. The existing personal Zettelkasten skill and companion collection skill are a separate installation route in this account, not proof of native plugin availability on every surface.

Where the local plugin is unavailable, attach `distribution/instruction-bundle.md` with selected source material and ask the model to follow it. This is an instruction/file bundle, not native installation; automatic activation is not promised. It contains the actual shared instructions and supporting references. For script work also provide the package ZIP to a code-capable session or execute locally. Uploading documents does not connect your Mac vault.

Sources: https://learn.chatgpt.com/docs/build-skills and https://learn.chatgpt.com/docs/projects

Current plugin documentation describes lifecycle hooks in the Codex runtime, including ChatGPT Work. Such hooks require trusted scripts deployed in the execution environment; web plugin installation alone does not deploy them. This package declares none. See https://learn.chatgpt.com/docs/plugins and https://learn.chatgpt.com/docs/hooks, and the core reference `future-chat-capture.md` for proposed capture routes and coverage limits.

## Avoid duplicate activation

Version 1.1.1 renames the plugin from `zettelkasten-research` to `connected-knowledge` and the marketplace to `connected-knowledge-local`. If the earlier package is installed, disable or uninstall that copy before enabling this one. The internal skills remain `zettelkasten-obsidian` and `research-collect`; their display names are now Develop Knowledge and Collect Research. This rename requires no vault migration.

Use one active copy of Zettelkasten–Obsidian in a given host: the updated personal skill or the bundled plugin copy. They share the same core; do not install standalone Zettelkasten Practice alongside this package to recreate the integration. If keeping both delivery forms, explicitly select the intended one and disable the duplicate where the host allows it.

## Dependencies and local scripts

From the package root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/requirements.txt
```

Use `.venv/bin/python` for the documented script commands. Windows: use the equivalent `.venv\Scripts\python.exe`. Python 3.10+ is required. Dependencies: pypdf, PyYAML, defusedxml. Only the fictional demo/test generation additionally needs reportlab (`requirements-dev.txt`). There are no model API calls, account credentials, OCR engine, scheduler service, or database server to configure.

## Account title instruction

Use the optional text in `docs/ACCOUNT-INSTRUCTIONS.md` in both accounts if desired. It distinguishes broad chat labels such as Research from vault categories Admin / Personal / Work. Plugin installation never changes account instructions automatically.
