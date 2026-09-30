# Codex project-hook setup

Use this route for selected local Codex projects when bundled-plugin hooks are not
discovered. On macOS with Codex CLI 0.159.2, the installed 1.3.0 capture script was
verified through a project Stop hook: a new exchange, continuation and restart/resume
updated one Markdown note without duplicate conversations. Bundled-hook discovery
failed in that trial, including explicit manifest declarations. This does not verify
other Codex versions, Windows, cloud Work, or every desktop launch mode.

## Guided setup

Select Codex capture in the first-run wizard. `hook_setup: "project"` is the default
for Codex answer files; `"bundled"` remains an explicit alternative. Claude Code
continues to use bundled hooks. Setup saves disabled configs and separate preview
commands only. It does not register or trust a hook, import history, or enable capture.

After saving setup, run each generated project-hook preview. The helper uses the
plugin copy from which it runs, so run onboarding from the installed plugin and the
Python environment with its dependencies installed. Example placeholders:

```sh
/private/python/bin/python /plugin/skills/zettelkasten-obsidian/scripts/project_hook.py --project /private/project --config /private/setup/capture-codex.json --python /private/python/bin/python
```

Review the displayed `.codex/hooks.json` destination and complete command. Add
`--apply` to that same command only when ready to install the selected project hook.
The helper requires a disabled Codex config that explicitly selects this project.
It preserves unrelated JSON hook settings, backs up an existing file beside the
private config, and does nothing on an identical repeat. Malformed files, symlink
paths and conflicting capture commands are rejected for manual review.

Keep the generated hook file and setup files private and out of version control:
commands contain machine-specific paths. The helper does not edit Git ignore rules,
user/global hooks, inline TOML hooks, installed plugin files or Codex trust settings.
Review `/hooks` for capture registrations from those other sources too: the helper
can only detect duplicates within the target JSON file.

## Activate and verify

1. Keep `enabled: false`. Launch Codex in the chosen project. Open `/hooks`, review
   the exact project Stop command, and trust it using the normal host UI. Project
   configuration must also be trusted by Codex. No trust bypass is needed.
2. Use one Connected Knowledge capture route per project. If a bundled or other
   capture hook is active, disable that duplicate in `/hooks` before proceeding.
3. First use a separate synthetic project/config, temporary archive and transcript
   root. Enable only that test config. Verify a test exchange, continuation and
   restart/resume produce one updated Markdown note. Disable it afterward.
4. Review the real config's exact projects, transcript roots, spool and destination.
   Set its `enabled` to `true` only for the selected real capture scope. Registration
   and trust alone leave capture off. Set it back to `false` to stop capture.

The command embeds the private config path and Python interpreter, so it does not
rely on an already-running desktop app inheriting shell exports. It invokes the same
packaged capture bootstrap and project/transcript checks as bundled capture.
Only Stop is installed by this helper; abrupt process termination before Stop is not
covered. Use selected-history preview/recovery if a turn was missed.

After a plugin upgrade, relocation or Python change, disable capture, inspect the
old command and backup, and replace only the identified capture registration before
regenerating. The helper deliberately refuses to overwrite a conflicting command.
Review/trust the new definition and repeat a synthetic test. To remove the project
hook, delete only its identified Stop handler, preserving other handlers; restore a
backup only after checking that no newer unrelated changes would be lost.

See [official Codex hook documentation](https://learn.chatgpt.com/docs/hooks) for
project discovery and trust, and [session capture](session-capture.md) for recovery.
