# issue-to-pr-agent

Write a GitHub issue. Comment `@agent`. Get a pull request.

This plugin installs that loop into any repository — adapted to *that* repo's
package manager, services and evidence commands, and running on whichever model
provider you pick.

## Install

```
/plugin marketplace add sayannandi/issue-to-pr-agent
/plugin install issue-to-pr-agent@issue-to-pr-agent
```

Then, from inside the repo you want to set up:

```
/issue-to-pr-agent
```

It reads the repo first, fills in the templates, commits on a branch and opens
the PR.

Two manual steps remain, on purpose — the token should not pass through a chat:

```
gh secret set   AGENT_TOKEN  --repo <owner/repo>   # from claude setup-token, or an OpenAI key
gh variable set AGENT_RUNNER --repo <owner/repo> --body claude
```

## What it installs

| File | Purpose |
|---|---|
| `.github/workflows/agent.yml` | The `@agent` worker. Triggers on issue, comment, review. |
| `.github/workflows/agent-review.yml` | `@agent-review` on a PR → a review comment. |
| `CLAUDE.md` § *Opening a PR* | The rules that make the agent open the PR instead of stranding a branch. |
| `scripts/agent_billing.py` | Per-collaborator token routing. Optional — skip it on a solo repo. |

## Pick your model

`AGENT_RUNNER` selects the runner. The workflow builds one plain-text prompt and
hands it to whichever you choose; nothing else in the file is provider-specific.

| `AGENT_RUNNER` | Runs | `AGENT_TOKEN` is |
|---|---|---|
| `claude` | `anthropics/claude-code-action@v1` | output of `claude setup-token` |
| `codex` | `openai/codex-action@v1` | an OpenAI API key |
| `custom` | your `AGENT_COMMAND` | whatever that command needs |

`custom` is the escape hatch, with `$AGENT_PROMPT` and `$AGENT_TOKEN` in the
environment. Install the CLI in the workflow's setup steps, then:

```
gh variable set AGENT_COMMAND --body 'npx @google/gemini-cli -p "$AGENT_PROMPT" --yolo'
gh variable set AGENT_COMMAND --body 'uvx aider --message "$AGENT_PROMPT" --yes'
gh variable set AGENT_COMMAND --body 'npx @anthropic-ai/claude-code -p "$AGENT_PROMPT" --allowedTools "Bash,Read,Edit,Write,Glob,Grep"'
```

That last form, with `ANTHROPIC_BASE_URL` pointed at a LiteLLM or
OpenAI-compatible gateway, runs the Claude Code agent loop against a
non-Anthropic model.

## Four decisions baked in

**1. Nothing runs until you arm it.**
Both jobs gate on `vars.AGENT_RUNNER != ''`. Install the workflows on a repo and
comment `@agent` before setting that variable, and *nothing happens* — no run,
no failing job, no red X. The gate has to be a variable rather than the secret
itself: GitHub does not expose the `secrets` context to `if:` conditions at job
or step level. A step-level check inside the job catches the set-but-empty case
and says so on the ticket rather than dying in the provider action.

**2. Runs are restricted to OWNER / COLLABORATOR / MEMBER.**
Every run spends a human's subscription or API credit. Without the
author-association guard, a stranger commenting `@agent` on a public issue
spends yours.

**3. The review workflow triggers on `issue_comment`, never `pull_request`.**
A `pull_request` run executes the workflow file *as it exists on the PR branch*.
Any collaborator with write access could open a same-repo PR that edits that file
and exfiltrates the secret. `issue_comment` always runs the default-branch copy,
so a branch edit changes nothing. The cost: reviews are manual
(`@agent-review`). Branch protection on `.github/workflows/` is the other fix,
but it is GitHub Pro-only on private repos.

**4. The prompt carries the ticket number, not the ticket text.**
`${{ github.event.issue.body }}` inside a `run:` block is a script-injection
hole — anyone who can comment can write shell. The workflow interpolates only
the issue *number*, and the agent reads the ticket itself with `gh`. That also
happens to be what makes one prompt string work across every runner.

## The CLAUDE.md rules are the load-bearing part

The workflows only start an agent. What makes the loop *close* is the block
appended to `CLAUDE.md`: open the PR yourself, title is the issue title verbatim,
body starts with `Closes #n`, and paste evidence rather than claims.

It also asks you to name evidence that **CI cannot produce** — tests needing
gitignored assets, a GPU, or local hardware. Those tickets get an explicit
carve-out telling the agent to stop and ask for a local session. A confidently
unverified PR is worse than no PR.

## Issues that work

The loop's quality is set by the issue, not the workflow. An issue that works
reads like a ticket handed to a new contractor: the decision already made, the
acceptance criteria listed, the files named. "Fix the upload bug" produces a
guess.

## Per-collaborator billing

On a solo repo, skip `agent_billing.py` — the generated one-clause expression
already works.

With more than one person, each collaborator's turns should bill their own
account. `scripts/agent_billing.py add <github-login>` stores their token as its
own repo secret and rewrites the `AGENT_TOKEN:` expression in both workflows.
They mint the token on their own machine — you never see it.

Do not hand-edit that line. The script parses the existing actor clauses back
out of it, and refuses to run against a flattened one rather than silently
dropping whoever it can no longer see.

## License

MIT
