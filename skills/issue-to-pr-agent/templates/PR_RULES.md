## Opening a PR (background agents)

One GitHub issue → one branch → one PR. Never push to `__DEFAULT_BRANCH__`.

**Open the PR yourself. Do not hand back a compare link.** The last action of
any issue-driven run is:

```bash
gh pr create --base __DEFAULT_BRANCH__ --title "<the issue's title, verbatim>" --body "Closes #<issue number>

<evidence, per the rules below>"
```

- **Title is the issue title, copied exactly.** Do not invent a title, do not
  append the branch name or a timestamp.
- **Body starts with `Closes #<n>`** so merging closes the issue.
- If `gh pr create` fails, say why in an issue comment. Never end a run with the
  work stranded on a branch.

The PR body must paste evidence, not claims:

- **Code changes**: run `__TEST_COMMAND__` and paste the tail.
- **Anything with a runnable self-check**: run it, paste the tail.
- __CI_IMPOSSIBLE_CARVE_OUT__
- If you could not run the evidence command, say so at the top of the PR body.
  Never open a silent PR.
