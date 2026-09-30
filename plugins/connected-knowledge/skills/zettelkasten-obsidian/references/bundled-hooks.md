# Opt-in bundled capture hooks

The package includes one default `hooks/hooks.json`, with Stop and SessionEnd
command hooks, and `hooks/capture.py`. Do not also declare this file in the
Claude manifest: default discovery is sufficient and duplicate registrations can
invoke capture twice. Remove any manually configured duplicate only after reviewing
its identity and explicitly switching to bundled capture.

The launcher is tested with POSIX shell commands on macOS. Windows shells still require validation. Native Claude Code 2.1.214 bundled
capture and resume passed on macOS. Codex CLI 0.159.2 did not discover the bundled
hooks in the installed-host trial; use [project-hook setup](project-hooks.md), whose
new-session, continuation and restart/resume capture passed with the same script. Python 3.10+ and the core
requirements are needed for enabled capture. Installation does not install Python
or dependencies. A missing Python executable can produce a shell error even when
capture is unconfigured; the Python launcher itself is dependency-free when disabled.

## Configure privately after setup

First run the guided setup and a manual transcript preview. Keep all configuration,
spool and archives outside the installed plugin. Set these environment variables in
the environment that launches the host (a shell export does not necessarily reach
an already running desktop app):

- `CONNECTED_KNOWLEDGE_PYTHON`: absolute path to the Python environment with core
  dependencies installed. Defaults to `python3` on the host PATH.
- `CONNECTED_KNOWLEDGE_CODEX_CONFIG`: absolute path to the private Codex capture JSON.
- `CONNECTED_KNOWLEDGE_CLAUDE_CODE_CONFIG`: absolute path to the private Claude Code
  capture JSON. Set only the host(s) explicitly selected.

Paths may contain spaces. The bundled command quotes interpreter and plugin paths.
Codex supplies `PLUGIN_ROOT` as well as its Claude-compatible variables; the launcher
uses that to select Codex. Otherwise `CLAUDE_PLUGIN_ROOT` selects Claude Code.
It verifies the selected config's `host` before capturing. The private configuration
must set `enabled` to true explicitly and specify account, exact projects,
transcript roots, spool, destination and vocabulary. Guided setup leaves it false.

Missing host identity, an unset config variable, a missing config file, or a config
without literal `enabled: true` causes a no-op. Disabled runs do not read stdin,
transcripts or import third-party dependencies. Enabled runs skip subagents and
unselected projects before reading transcripts. Invalid enabled configurations,
missing dependencies and capture failures exit 1 with a content-free diagnostic.
Stdout is always `{}`; the launcher never requests continuation or outputs chat text.
Use a manual preview for detailed local diagnostics. Last-success metadata does
not establish that the latest hook invocation succeeded.

## Activation and testing

1. Exercise the packaged command against a synthetic event and temporary archive.
2. Verify the running host actually receives the selected environment variables.
3. Review/trust the hook definition in Codex when requested by the host; installation
   alone does not trust hooks. Enable only the chosen private configuration.
4. Verify a small synthetic conversation causes one archive write, then a no-op on
   repeat. Verify failure reporting and disable via `enabled: false`.

No global/user hook files are modified by this package. The separate project-hook
helper writes only a selected project hook file after explicit `--apply`. Native
trials used synthetic conversations and temporary archives; real capture stays opt-in. Plugin/local command hooks are not
supported in cloud-orchestrated Work, even when some tools run locally. Ordinary
Chat account history still requires supplied exports.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude plugin hooks](https://code.claude.com/docs/en/plugins-reference),
[Work cloud limits](https://learn.chatgpt.com/docs/config-file/config-reference).
