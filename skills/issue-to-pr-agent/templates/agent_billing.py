#!/usr/bin/env python3
"""Onboard a collaborator so their @agent runs bill their own model account.

Every GitHub Actions run of `agent.yml` / `agent-review.yml` spends somebody's
model subscription or API credit. The workflows pick the credential by
`github.actor` on a single `AGENT_TOKEN:` line, so each person needs their own
repo secret and their own clause in that expression. This script maintains both.

    scripts/agent_billing.py add <github-login> [--grant]
    scripts/agent_billing.py --self-test

`add` prompts for the collaborator's token (from `claude setup-token`, an
OpenAI API key, or whatever AGENT_RUNNER needs — obtained on *their* machine, so
you never see it in a chat), stores it as AGENT_TOKEN_<LOGIN>, and rewrites the
token expression in both workflows.  `--grant` also gives them write access
to the repo first.

The workflow line is the only state: existing clauses are parsed back out of it,
so there is no map file to keep in sync. Do not hand-flatten that line — see
`rewrite`. Commit the workflow changes afterwards; the comment-triggered
workflows only ever run the copy on the default branch.
"""

from __future__ import annotations

import argparse
import getpass
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = [
    REPO_ROOT / ".github/workflows/agent.yml",
    REPO_ROOT / ".github/workflows/agent-review.yml",
]

# The generated line, e.g.
#   AGENT_TOKEN: ${{ github.actor == 'x' && secrets.Y || ... || '' }}
TOKEN_LINE = re.compile(r"^(?P<indent>[ \t]*)AGENT_TOKEN:.*$", re.M)
CLAUSE = re.compile(r"github\.actor == '(?P<login>[^']+)' && secrets\.(?P<secret>[A-Za-z0-9_]+)")


def secret_name(login: str) -> str:
    """GitHub secret names allow only alphanumerics and underscore."""
    return "AGENT_TOKEN_" + re.sub(r"[^A-Za-z0-9]", "_", login).upper()


def parse_clauses(line: str) -> list[tuple[str, str]]:
    """Existing (login, secret) pairs, in order, from a generated token line."""
    return [(m["login"], m["secret"]) for m in CLAUSE.finditer(line)]


def build_expr(pairs: list[tuple[str, str]]) -> str:
    """Render the actor->secret chain.

    GitHub evaluates && above ||, so this reads as a chain of (test && value)
    with a '' fallback: an unknown actor yields an empty token, and the
    workflow's preflight step says so on the ticket instead of silently
    charging whoever is listed last.
    String comparison in GitHub expressions is case-insensitive.
    """
    clauses = [f"github.actor == '{login}' && secrets.{secret}" for login, secret in pairs]
    expr = "${{ " + " || ".join(clauses + ["''"]) + " }}"
    # A plain YAML scalar would break on either of these; assert rather than
    # emit a workflow file that no longer parses.
    assert "\n" not in expr and ": " not in expr, f"unsafe expression: {expr}"
    return expr


def upsert(pairs: list[tuple[str, str]], login: str, secret: str) -> list[tuple[str, str]]:
    """Add the pair, or replace it if that login is already billed."""
    kept = [(l, s) for l, s in pairs if l.lower() != login.lower()]
    return kept + [(login, secret)]


def rewrite(text: str, login: str, secret: str) -> str:
    m = TOKEN_LINE.search(text)
    if not m:
        raise SystemExit("no AGENT_TOKEN line found — workflow changed shape?")
    pairs = parse_clauses(m.group(0))
    if not pairs:
        # The line was hand-flattened to a bare `${{ secrets.AGENT_TOKEN }}`.
        # Rewriting it now would emit a chain containing only the new person,
        # and the repo owner's own runs would start resolving to '' — a silent
        # break discovered the next time they comment @agent.
        raise SystemExit(
            f"the AGENT_TOKEN line in one workflow has no `github.actor == '...'` clause, "
            f"so it was hand-edited. Restore the generated form first:\n"
            f"  AGENT_TOKEN: {build_expr([('<owner-login>', 'AGENT_TOKEN')])}"
        )
    new_line = f"{m['indent']}AGENT_TOKEN: {build_expr(upsert(pairs, login, secret))}"
    return text[: m.start()] + new_line + text[m.end() :]


def gh(*args: str, stdin: str | None = None) -> str:
    out = subprocess.run(
        ["gh", *args], input=stdin, capture_output=True, text=True, check=False
    )
    if out.returncode:
        raise SystemExit(f"gh {' '.join(args)} failed:\n{out.stderr.strip()}")
    return out.stdout.strip()


def cmd_add(login: str, grant: bool) -> None:
    repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")

    if grant:
        gh("api", "-X", "PUT", f"repos/{repo}/collaborators/{login}", "-f", "permission=push")
        print(f"invited {login} to {repo} (write)")

    print(f"Ask {login} for a token for this repo's AGENT_RUNNER, minted on their")
    print("own machine (`claude setup-token`, an OpenAI API key, etc.).")
    token = getpass.getpass("token: ").strip()
    if not token:
        raise SystemExit("no token given, nothing changed")

    name = secret_name(login)
    # Via stdin, never argv: a `--body <token>` would put the secret in this
    # process's command line, readable by any other user's `ps` on this machine.
    gh("secret", "set", name, "--body-file", "-", stdin=token)
    print(f"set secret {name}")

    for path in WORKFLOWS:
        path.write_text(rewrite(path.read_text(), login, name))
        print(f"updated {path.relative_to(REPO_ROOT)}")

    print("\nNext: git add .github/workflows && git commit && git push")
    print(f"      {login}'s @agent runs bill their account once that lands on the default branch.")


def self_test() -> None:
    assert secret_name("7BitOctocat") == "AGENT_TOKEN_7BITOCTOCAT"
    assert secret_name("foo-bar.baz") == "AGENT_TOKEN_FOO_BAR_BAZ"

    line = "      AGENT_TOKEN: ${{ github.actor == 'a' && secrets.S_A || '' }}"
    assert parse_clauses(line) == [("a", "S_A")]

    # round trip: parse -> build reproduces the same expression
    assert build_expr(parse_clauses(line)) == line.split(": ", 1)[1]

    # upsert replaces rather than duplicating, case-insensitively
    assert upsert([("a", "S_A")], "A", "S_A2") == [("A", "S_A2")]
    assert upsert([("a", "S_A")], "b", "S_B") == [("a", "S_A"), ("b", "S_B")]

    # rewrite preserves indentation and everything around the line
    text = f"x: 1\n{line}\ny: 2\n"
    out = rewrite(text, "b", "S_B")
    assert out.startswith("x: 1\n") and out.endswith("\ny: 2\n"), out
    assert out.splitlines()[1].startswith("      AGENT_TOKEN: "), out
    assert parse_clauses(out) == [("a", "S_A"), ("b", "S_B")], out

    # the fallback clause must survive, or an unknown actor silently bills someone
    assert out.splitlines()[1].endswith("|| '' }}"), out

    # a hand-flattened line is refused instead of silently dropping the owner
    try:
        rewrite("  AGENT_TOKEN: ${{ secrets.AGENT_TOKEN }}\n", "b", "S_B")
    except SystemExit as e:
        assert "hand-edited" in str(e), e
    else:
        raise AssertionError("flattened token line was rewritten instead of refused")

    # an installed repo's workflows must already be in generated shape. Skipped
    # when running from the plugin's own templates/ dir, where they do not exist.
    for path in WORKFLOWS:
        if not path.exists():
            continue
        m = TOKEN_LINE.search(path.read_text())
        assert m, path
        assert parse_clauses(m.group(0)), f"{path}: no actor clauses"
        assert m.group(0).rstrip().endswith("|| '' }}"), f"{path}: missing '' fallback"

    print("self-test OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="run asserts and exit")
    sub = ap.add_subparsers(dest="cmd")
    p_add = sub.add_parser("add", help="onboard a collaborator")
    p_add.add_argument("login", help="their GitHub login")
    p_add.add_argument("--grant", action="store_true", help="also give them write access")

    args = ap.parse_args()
    if args.self_test:
        self_test()
    elif args.cmd == "add":
        cmd_add(args.login, args.grant)
    else:
        ap.print_help()
        sys.exit(1)
