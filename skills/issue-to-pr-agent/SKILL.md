---
name: issue-to-pr-agent
description: Install the "GitHub issue → @agent → background agent → PR" workflow into a repository, running on whichever model provider the repo chooses (Claude Code, OpenAI Codex, or any CLI agent). Copies and adapts the two workflows, the PR-opening rules for CLAUDE.md, and the per-collaborator billing script. Use when the user says "issue-to-pr-agent", "/issue-to-pr-agent", "set up @agent on this repo", "set up @claude on this repo", "copy the agent issue workflow here", "make background agents open PRs", or asks how to replicate the issue→PR automation from another repo.
---

# issue-to-pr-agent

Installs the loop: write a GitHub issue with the decisions and context → comment
`@agent` → Actions runs a coding agent on an ephemeral runner → it branches,
works, and opens the PR itself.

Provider-neutral. The workflow assembles a plain-text prompt and hands it to
whichever runner the repo variable `AGENT_RUNNER` selects.

Templates live in `templates/` next to this file.

## What gets installed

| File | Purpose | Adapt per repo? |
|---|---|---|
| `.github/workflows/agent.yml` | The `@agent` worker. Triggers on issue/comment/review. | Yes — owner, deps, services |
| `.github/workflows/agent-review.yml` | `@agent-review` on a PR → a review comment. | Owner login only |
| `CLAUDE.md` § "Opening a PR (background agents)" | Makes the agent open the PR instead of handing back a compare link. | Yes — evidence commands |
| `scripts/agent_billing.py` | Per-collaborator token routing. | Only if >1 person |

Plus two pieces of repo config, **not** files:

| Setting | Value | Why |
|---|---|---|
| secret `AGENT_TOKEN` | provider credential | What the runner authenticates with |
| variable `AGENT_RUNNER` | `claude` \| `codex` \| `custom` | Picks the runner **and** arms the workflow |
| variable `AGENT_COMMAND` | shell command | Only when `AGENT_RUNNER=custom` |

## Fail-closed, by design

Both workflows start with `if: vars.AGENT_RUNNER != ''`. On a repo where the
variable was never set, an `@agent` comment does nothing at all — no run, no
failing job, no red X on the issue. `AGENT_RUNNER` is therefore the **last**
thing you set, after the secret exists (step 7). Never set it earlier and never
remove that clause.

(The gate has to be a variable: the `secrets` context is not available in `if:`
conditions, job-level or step-level. A second, step-level check inside the job
catches a set-but-empty token and says so on the ticket.)

## Steps

1. **Confirm the repo.** `gh repo view --json nameWithOwner,visibility,defaultBranchRef`.
   If not a git repo with a GitHub remote, stop and say so.

2. **Pick the runner.** Ask which provider this repo should use, unless the user
   already said:
   - `claude` → `anthropics/claude-code-action@v1`, token from `claude setup-token`.
   - `codex` → `openai/codex-action@v1`, token is an OpenAI API key.
   - `custom` → anything else (Gemini CLI, aider, opencode, a local endpoint, or
     Claude Code pointed at an OpenAI-compatible gateway). Also needs the
     `AGENT_COMMAND` variable and a CLI install in the setup steps.

3. **Read the target repo.** You cannot fill in the templates without knowing:
   - Package manager / install command (`uv sync`, `npm ci`, `poetry install`, `go mod download`).
   - Whether tests need a service (Postgres, Redis) — check `docker-compose.yml`, test config.
   - The commands that prove work is done (test runner, linter, self-checks).
   - Whether any evidence command is **impossible on CI** (needs gitignored assets, GPU, local hardware). This matters — see step 6.

4. **Copy and adapt `templates/agent.yml`** → `.github/workflows/agent.yml`:
   - Replace `__OWNER_LOGIN__` with the repo owner's GitHub login (from step 1).
   - Replace the `__SETUP_STEPS__` comment block with that repo's real install
     steps — and, for `custom`, the agent CLI install too. Keep it minimal:
     install only what an agent turn needs, not the whole heavy test matrix. A
     turn runs on every `@agent` comment; a GB of ML deps per turn is wasted
     minutes. **This placeholder lives inside a YAML comment**, so forgetting it
     yields a valid workflow that installs nothing. Check it.
   - Delete the `services:` block and the `DATABASE_URL:` line if nothing needs
     a database; otherwise fill `__DB_USER__`, `__DB_PASSWORD__`, `__DB_NAME__`,
     `__DATABASE_URL__`.
   - Leave both `if:` gates alone.

5. **Copy `templates/agent-review.yml`** → `.github/workflows/agent-review.yml`,
   same `__OWNER_LOGIN__` substitution. Usually no other change.

6. **Append `templates/PR_RULES.md`** to the repo's `CLAUDE.md` (create it if
   absent), filling `__DEFAULT_BRANCH__`, `__TEST_COMMAND__` and
   `__CI_IMPOSSIBLE_CARVE_OUT__`. This file is what makes the loop actually
   close — without it the agent tends to stop at a branch. Keep the "Open the PR
   yourself" paragraph verbatim.
   For `__CI_IMPOSSIBLE_CARVE_OUT__`: if step 3 found evidence CI cannot produce,
   name the work, say a background agent must not open that PR, and say it needs
   a local session instead. A silently unverified PR is worse than no PR. If
   there is no such work, replace the line with a plain "All evidence commands
   run on CI."

7. **Copy `templates/agent_billing.py`** → `scripts/agent_billing.py` only if more
   than one person will use `@agent`. Solo repo: skip the file.
   Either way, **leave the generated `AGENT_TOKEN:` expression in both workflows
   exactly as it is.** Do not flatten it to a bare `${{ secrets.AGENT_TOKEN }}` —
   the script parses the actor clauses back out of that line, and a flattened
   line would silently drop the owner the first time a collaborator is added.

8. **Verify no placeholder survived** before committing:
   ```
   grep -rn '__[A-Z_]*__' .github/workflows/ CLAUDE.md scripts/ && echo "UNSUBSTITUTED"
   ```
   It must print nothing.

9. **Hand off the credential and arm the workflow.** The token is minted on the
   token owner's own machine. Tell the user to run, in order:
   ```
   claude setup-token                       # claude runner; or mint an OpenAI key
   gh secret set AGENT_TOKEN --repo <owner/repo>
   gh variable set AGENT_RUNNER --repo <owner/repo> --body claude
   # custom runner only:
   gh variable set AGENT_COMMAND --repo <owner/repo> --body '<invocation>'
   ```
   Never ask them to paste the token into the chat. Do not run `claude
   setup-token` yourself — it is interactive and belongs to them. The
   `AGENT_RUNNER` line goes last: until it runs, the repo is inert.

10. **Commit on a branch and open a PR**, per the rules you just installed.

11. **Print the smoke test**, exactly this shape:
    ```
    Test: open an issue titled "chore: add a LICENSE file",
    body "MIT, author <name>. @agent"
    Then watch: gh run watch
    ```

## Rules that must survive adaptation

- **The `vars.AGENT_RUNNER != ''` gate.** It is the fail-closed guarantee: no
  configuration, no run. Removing it means every unconfigured repo shows a red
  X on every issue.
- **Author-association guard.** Every run bills a human's subscription or API
  credit. Never widen the `if:` to unauthenticated triggers.
- **Review workflow triggers on `issue_comment`, never `pull_request`.** A
  `pull_request` run executes the workflow file *as it exists on the PR branch*,
  so a collaborator could edit it on a branch and exfiltrate the secret.
  `issue_comment` always runs the default-branch copy. The cost is that reviews
  are manual (`@agent-review`). That trade is deliberate — keep it.
- **The prompt carries the ticket number, never the ticket text.** Interpolating
  `github.event.issue.body` into a `run:` block is a script-injection hole; the
  agent reads the ticket itself with `gh`.
- **For the claude runner, `--allowedTools` must include Bash.** Without it the
  agent gets git and nothing else, and cannot run a single acceptance-criteria
  command. The runner is ephemeral and the token is repo-scoped, so unrestricted
  Bash is the right trade.
- **`contents: write` + `pull-requests: write`** on `agent.yml`, and
  **`pull-requests: write`** on `agent-review.yml` — posting the review is the
  entire point of that job, and `read` silently breaks it.

## Writing issues that work

The loop's quality is set by the issue, not the workflow. Tell the user: an issue
that works reads like a ticket handed to a new contractor — the decision already
made, the acceptance criteria listed, the files named. An issue that says "fix the
upload bug" produces a guess. Stable IDs (from a gap register or ADR) in the title
make the PR traceable back to the plan.
