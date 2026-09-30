# Final review — 1.3.0 candidate, 2026-09-30

Reviewed merged source 3f311b8 for onboarding, ZIP preparation, import/graph
integrity, capture recovery and packaging. Used synthetic temporary data only.

## Reproduced issues and local fixes

1. **P1 — Output redirection.** The importer resolved its destination before
   checking for symlinks, so an existing destination/parent link redirected writes
   to another folder. Reject links before resolving, and apply the same root
   protection to graph/starter entry points. Regression tests cover rejection
   without writes; temporary test/demo roots use their actual canonical locations.
2. **P2 — Stale metadata after parser upgrades.** Fingerprints included source and
   settings, but no importer format version. An unchanged Claude export therefore
   retained old null reply parents even after the parser fix. Version fingerprints
   so the first reimport refreshes generated notes, preserves revisions and still
   refuses human edits. Subsequent imports remain no-ops.

Fixes are local pending commit/CI/merge. Review is not a claim of exhaustive
security assurance. Multi-file interruption still requires the documented manual
reconciliation; ZIP limits and attachment-association limits remain explicit.

Validation after fixes: all 97 local tests pass, plugin/skill validation passes,
the synthetic graph example has zero checker issues and zero repeat writes,
and the rebuilt package's 58 entries match source bytes and SHA-256 inventory.

## Hooks

The adapter exists; bundled registration and an opt-in launcher do not. Hooks are
unnecessary for imports and setup. Recommend adding a package-relative launcher
for Stop/SessionEnd before distributing automatic capture, with no transcript
reads/writes when configuration is absent or disabled, explicit private paths,
dependency checks and host selection. Keep private history outside plugin storage
that upgrades/uninstall may remove. Avoid duplicate manual/bundled registrations.

Codex and Claude Code document bundled hooks. Codex requires separate trust review.
OpenAI documents no plugin command hooks in cloud-orchestrated Work, even with
local execution. Live host registration/firing remains untested. Sources and
requirements are recorded in the session-capture reference.

## Hook implementation follow-up

Bundled Stop/SessionEnd definitions and a standard-library opt-in launcher now
implement the recommendation. Host-specific private config variables and explicit
enabled flags gate transcript access; excluded projects/subagents are skipped.
Tests execute the actual manifest command and check both hosts, disabled and
missing config, dependencies, host mismatch, failures and retries. The earlier
hook recommendation describes the pre-implementation review state.
