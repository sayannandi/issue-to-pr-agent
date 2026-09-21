---
name: issue-to-pr-agent
description: Install the "GitHub issue → @claude → background agent → PR" workflow into a repository. Copies and adapts the two Claude Code Action workflows, the PR-opening rules for CLAUDE.md, and the per-collaborator billing script. Use when the user says "issue-to-pr-agent", "/issue-to-pr-agent", "set up @claude on this repo", "copy the claude issue workflow here", "make background agents open PRs", or asks how to replicate the issue→PR automation from another repo.
---

# issue-to-pr-agent

Installs the loop: write a GitHub issue with the decisions and context → comment
`@claude` → Actions runs Claude Code on an ephemeral runner → it branches, works,
and opens the PR itself.

Templates live in `templates/` next to this file.

## What gets installed

| File | Purpose | Adapt per repo? |
|---|---|---|
| `.github/workflows/claude.yml` | The `@claude` worker. Triggers on issue/comment/review. | Yes — deps + services |
| `.github/workflows/claude-code-review.yml` | `@claude-review` on a PR → inline review comments. | Rarely |
| `CLAUDE.md` § "Opening a PR (background agents)" | Makes the agent open the PR instead of handing back a compare link. | Yes — evidence commands |
| `scripts/claude_billing.py` | Per-collaborator token routing. | Only if >1 person |

## Steps

1. **Confirm the repo.** `gh repo view --json nameWithOwner,visibility`. If not a
   git repo with a GitHub remote, stop and say so.

2. **Read the target repo first.** You cannot fill in the templates without knowing:
   - Package manager / install command (`uv sync`, `npm ci`, `poetry install`, `go mod download`).
   - Whether tests need a service (Postgres, Redis) — check `docker-compose.yml`, test config.
   - The commands that prove work is done (test runner, linter, self-checks).
   - Whether any evidence command is **impossible on CI** (needs gitignored assets, GPU, local hardware). This matters — see step 5.

3. **Copy and adapt `templates/claude.yml`** → `.github/workflows/claude.yml`:
   - Replace `__OWNER_LOGIN__` with the repo owner's GitHub login (from step 1).
   - Replace the `__SETUP_STEPS__` block with that repo's real install steps. Keep it
     minimal: install only what an agent turn needs, not the whole heavy test matrix.
     A turn runs on every `@claude` comment; a GB of ML deps per turn is wasted minutes.
   - Delete the `services:`/`env:` block entirely if nothing needs a database.
   - Leave the `if:` guard alone. It restricts runs to OWNER/COLLABORATOR/MEMBER —
     without it any stranger's `@claude` spends the token owner's subscription.

4. **Copy `templates/claude-code-review.yml`** → `.github/workflows/claude-code-review.yml`,
   same `__OWNER_LOGIN__` substitution. Usually no other change.

5. **Append `templates/PR_RULES.md`** to the repo's `CLAUDE.md` (create it if absent),
   filling the `__…__` placeholders with the repo's real commands from step 2.
   This file is what makes the loop actually close — without it the agent tends to
   stop at a branch. Keep the "Open the PR yourself" paragraph verbatim.
   If step 2 found evidence that CI cannot produce, write that carve-out explicitly:
   name the work, say a background agent must not open that PR, and say it needs a
   local session instead. A silently unverified PR is worse than no PR.

6. **Copy `templates/claude_billing.py`** → `scripts/claude_billing.py` only if more
   than one person will use `@claude`. Solo repo: skip it, and simplify the token
   line in both workflows to plain `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.

7. **Set the secret.** The token comes from `claude setup-token` run on the token
   owner's own machine. Tell the user to run:
   ```
   claude setup-token            # copy the token it prints
   gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <owner/repo>
   ```
   Never ask them to paste the token into the chat. Do not run `claude setup-token`
   yourself — it is interactive and belongs to them.

8. **Commit on a branch and open a PR**, per the rules you just installed.

9. **Print the smoke test**, exactly this shape:
   ```
   Test: open an issue titled "chore: add a LICENSE file",
   body "MIT, author <name>. @claude"
   Then watch: gh run watch
   ```

## Rules that must survive adaptation

- **Author-association guard.** Every run bills a human's Claude subscription.
  Never widen the `if:` to unauthenticated triggers.
- **Review workflow triggers on `issue_comment`, never `pull_request`.** A
  `pull_request` run executes the workflow file *as it exists on the PR branch*,
  so a collaborator could edit it on a branch and exfiltrate the secret.
  `issue_comment` always runs the default-branch copy. The cost is that reviews
  are manual (`@claude-review`). That trade is deliberate — keep it.
- **`--allowedTools` must include Bash.** Without it the agent gets git and nothing
  else, and cannot run a single acceptance-criteria command. The runner is
  ephemeral and the token is repo-scoped, so unrestricted Bash is the right trade.
- **`contents: write` + `pull-requests: write`** or the agent cannot push or open
  the PR.

## Writing issues that work

The loop's quality is set by the issue, not the workflow. Tell the user: an issue
that works reads like a ticket handed to a new contractor — the decision already
made, the acceptance criteria listed, the files named. An issue that says "fix the
upload bug" produces a guess. Stable IDs (from a gap register or ADR) in the title
make the PR traceable back to the plan.
