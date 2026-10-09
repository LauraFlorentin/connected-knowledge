---
name: ck-help
description: Show what Connected Knowledge can do, its live status on this machine, and the most useful next step. Use when the user runs /ck-help or $ck-help, or asks what Connected Knowledge can do or how to use it.
argument-hint: "[topic]"
---

# Connected Knowledge help

Arguments: $ARGUMENTS

Run `python3 <path to ck.py> doctor --next`. The script is
`../zettelkasten-obsidian/scripts/ck.py`, relative to this skill's folder; it needs
no packages.

Show a two-line status, leaving out anything unknown:

```text
Connected Knowledge on mac-mini (hub) · vault: reachable · capture: on (2 hosts)
Saved: 412 conversations · 3 without a category · last Claude export: 34 days ago
```

If the result lists `attention` items, add one line for each with what to do.
Then show this menu:

1. Set up or change the vault — `/ck-setup`
2. Save this conversation now — `/ck-add-session`
3. Save older sessions from this Mac — `/ck-add-session all`
4. Import an account export (Claude, ChatGPT) — ask "import my Claude export"
5. Add a document or research source — ask "add this source"
6. Explore or check my notes — ask "what do my notes say about …"
7. Add a topic to the topic tree — ask "add a topic …"

On Codex the commands are skills: `$ck-setup`, `$ck-help`, `$ck-add-session`.
In a chat app without local files (Claude chat, a phone, ChatGPT web) the status
cannot be read: show the menu and explain that setup and capture run on the Mac
that holds the vault.

With a topic argument, answer that topic briefly using the core skill's
references, then show the menu.

## Finish

1. Use the `next` part of the doctor result you already have.
2. Offer `next.suggestion` first, `next.alternative` as one alternative, and
   "stop here".
3. Wait for the choice. Do not start the next task unasked.
