# Connected Knowledge — 1.7.0

Connected Knowledge turns AI chats, coding sessions and documents into sourced,
linked notes in your Obsidian vault. It is an AI-host plugin, not an Obsidian
community plugin: Obsidian stays the place where you read and write.

## First steps

1. Install it for your host. [docs/INSTALL.md](docs/INSTALL.md) has one section per
   host; the README's [install table](README.md#install-per-host) is the summary.
2. Run `/ck-setup` (Codex: `$ck-setup`). It asks one question at a time:
   - an existing vault, or a new one with the full structure or a minimal start,
     with or without a templates folder, and your main topics;
   - a short name for this Mac and whether it is the hub that imports account
     exports;
   - which project folders' AI sessions to save.

   Every step shows a preview before anything is written.
3. Save this conversation as a trial with `/ck-add-session`, then open the note in
   Obsidian.
4. Switch capture on when you are happy with the trial. Until then the hooks do
   nothing.
5. Run `/ck-help` whenever you want to see the status and the next useful step.

## What goes where

- Your notes and conversation notes live in the vault, organised by the
  `Vault Guide.md` that setup creates or adapts.
- Settings, the capture queue and raw transcript copies live outside the vault, on
  each Mac, in folders only you can read. They are never synced or committed.
- Account exports from Claude and ChatGPT are imported on one Mac, the hub.

## The plugin's parts

- **Commands:** `/ck-setup`, `/ck-help`, `/ck-add-session`.
- **Develop Knowledge** (`zettelkasten-obsidian`): develop, explore, synthesize,
  review and check notes.
- **Collect Research** (`research-collect`): collect selected sources into a
  reviewable inbox, separately from note development.

Read [docs/USAGE.md](docs/USAGE.md) for commands and scripts, and
[docs/VALIDATION.md](docs/VALIDATION.md) for what was tested and what was not.
