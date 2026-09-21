# issue-to-pr-agent

Write a GitHub issue. Comment `@claude`. Get a pull request.

This plugin installs that loop into any repository — and adapts it to *that*
repo's package manager, services and evidence commands rather than dumping
generic YAML on you.

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

One manual step remains, on purpose — the token should not pass through a chat:

```
claude setup-token                                    # on your own machine
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <owner/repo>
```

## What it installs

| File | Purpose |
|---|---|
| `.github/workflows/claude.yml` | The `@claude` worker. Triggers on issue, comment, review. |
| `.github/workflows/claude-code-review.yml` | `@claude-review` on a PR → inline review comments. |
| `CLAUDE.md` § *Opening a PR* | The rules that make the agent open the PR instead of stranding a branch. |
| `scripts/claude_billing.py` | Per-collaborator token routing. Optional — skip it on a solo repo. |

## Three decisions baked in

**1. Runs are restricted to OWNER / COLLABORATOR / MEMBER.**
Every run spends a human's Claude subscription. Without the author-association
guard, a stranger commenting `@claude` on a public issue spends yours.

**2. The review workflow triggers on `issue_comment`, never `pull_request`.**
A `pull_request` run executes the workflow file *as it exists on the PR branch*.
Any collaborator with write access could open a same-repo PR that edits that file
and exfiltrates the secret. `issue_comment` always runs the default-branch copy,
so a branch edit changes nothing. The cost: reviews are manual (`@claude-review`).
Branch protection on `.github/workflows/` is the other fix, but it is GitHub
Pro-only on private repos.

**3. `--allowedTools` includes Bash.**
Without it the agent gets git and nothing else — the package manager, test runner
and docker all come back "requires approval", so it cannot run a single
acceptance-criteria command. The runner is ephemeral and the token is scoped to
one repo, so unrestricted Bash is the right trade.

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

On a solo repo, skip `claude_billing.py` and use a plain
`${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.

With more than one person, each collaborator's turns should bill their own
subscription. `scripts/claude_billing.py add <github-login>` stores their token as
its own repo secret and rewrites the `github.actor` expression in both workflows.
They run `claude setup-token` on their own machine — you never see the token.

## License

MIT
