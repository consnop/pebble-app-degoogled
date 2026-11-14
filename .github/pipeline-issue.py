#!/usr/bin/env python3
"""Pipeline issues: the cloud routine "pebble patch conflicts" starts on each new one.

  report conflict|build   a run failed: git am failed (conflict), or the patches applied but the build failed
  close                   a release succeeded: close this tag's open issues

Each failed attempt at a tag (a new patch set) gets a new issue, so every attempt to fix it starts the
routine again. A rerun of the same patch set (the daily schedule) files nothing new. After MAX_ISSUES
issues for one tag the pipeline stops filing and asks for a human, so a bad fix can't loop.

Env: GH_TOKEN, GITHUB_REPOSITORY, TAG, RELEASE (<tag>-consnop-<patch id>), RUN_ID, RUN_URL,
UPSTREAM (a name for the issue text), DRY_RUN=1 to print instead of writing.
"""
import json
import os
import re
import subprocess
import sys

MAX_ISSUES = 4  # the first report plus three fix attempts
CONFLICT = "Patches don't apply to"
BUILD = "Patched build fails on"
GAVE_UP = "<!-- pipeline: gave up -->"

env = os.environ
repo, tag = env["GITHUB_REPOSITORY"], env["TAG"]
dry = env.get("DRY_RUN") == "1"


def gh(*args, write=False):
    if write and dry:
        print("DRY RUN: gh", *args[:4], "...")
        return ""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def tag_issues():
    """This tag's pipeline issues, oldest first."""
    title_re = re.compile(rf"^({re.escape(CONFLICT)}|{re.escape(BUILD)}) {re.escape(tag)}( \(attempt \d+\))?$")
    found = json.loads(gh("issue", "list", "-R", repo, "--state", "all", "--limit", "300",
                          "--search", f'in:title "{tag}"', "--json", "number,title,state,body,author"))
    return sorted((i for i in found
                   if title_re.match(i["title"]) and "github-actions" in i["author"]["login"]),
                  key=lambda i: i["number"])


def log_excerpt():
    """The failed step of this run's build job: error-looking lines, then its tail."""
    jobs = json.loads(gh("api", f"repos/{repo}/actions/runs/{env['RUN_ID']}/jobs"))["jobs"]
    job = next((j for j in jobs if j["name"] == "build"), None)
    if not job:
        return "(no build job log found)"
    raw = gh("api", f"repos/{repo}/actions/jobs/{job['id']}/logs")
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", re.sub(r"^\S+Z ", "", l)) for l in raw.splitlines()]
    # The failed step's output runs from its last "##[group]Run" header to the first "##[error]".
    end = next((n for n, l in enumerate(lines) if l.startswith("##[error]")), len(lines))
    start = max((n for n, l in enumerate(lines[:end]) if l.startswith("##[group]Run")), default=0)
    step = [l for l in lines[start:end] if not l.startswith("##[")]
    cut = lambda l: l if len(l) <= 300 else l[:300] + " [...]"
    errors = [cut(l) for l in step
              if not re.match(r"\[\d+/\d+\] ", l)  # ninja progress, e.g. "Building ... error.c.obj"
              and re.search(r"\berror\b|FAILED|fatal|^e: |CONFLICT|patch failed|does not apply|undefined reference",
                           l, re.I)][:40]
    tail = [cut(l) for l in step[-40:]]
    return ("Error lines:\n" + "\n".join(errors or ["(none matched)"]) +
            "\n\nLast lines of the failed step:\n" + "\n".join(tail)).replace("```", "'''")


def report(kind):
    issues = tag_issues()
    open_issues = [i for i in issues if i["state"] == "OPEN"]
    marker = f"<!-- pipeline: release {env['RELEASE']} -->"
    if any(marker in i["body"] for i in issues):
        print(f"Already reported {env['RELEASE']}.")
        return
    if len(issues) >= MAX_ISSUES:
        last = issues[-1]
        if GAVE_UP not in last["body"] and not gh("issue", "view", str(last["number"]), "-R", repo,
                                                  "--json", "comments", "--jq",
                                                  f'.comments[] | select(.body | contains("{GAVE_UP}")) | .id'):
            if last["state"] != "OPEN":
                gh("issue", "reopen", str(last["number"]), "-R", repo, write=True)
            gh("issue", "comment", str(last["number"]), "-R", repo, "--body",
               f"Still failing after {len(issues)} automatic attempts at `{tag}` (now `{env['RELEASE']}`, "
               f"run: {env['RUN_URL']}). The pipeline stops filing issues for `{tag}`; this needs a human.\n\n{GAVE_UP}",
               write=True)
        print(f"{len(issues)} issues for {tag} already; gave up.")
        return

    prefix = CONFLICT if kind == "conflict" else BUILD
    title = f"{prefix} {tag}" + (f" (attempt {len(issues) + 1})" if issues else "")
    what = (f"`git am` failed applying `patches/` to upstream {env.get('UPSTREAM', '')} `{tag}`."
            if kind == "conflict" else
            f"`patches/` apply to upstream {env.get('UPSTREAM', '')} `{tag}`, but the build fails.")
    todo = ("Rebase the patches onto `TAG`, regenerate them with `git format-patch`, and push to the `pipeline` branch."
            if kind == "conflict" else
            "Fix the patches so `TAG` builds (apply them onto `TAG`, change them, regenerate with "
            "`git format-patch`), and push to the `pipeline` branch.").replace("TAG", tag)
    try:
        excerpt = log_excerpt()
    except Exception as e:  # never let a log problem stop the issue (and the routine) from happening
        excerpt = f"(couldn't read the build log: {e}; see the run)"
    history = "".join(f"\n- #{i['number']} {i['title']}" for i in issues)
    body = (f"{what} Patch set `{env['RELEASE']}`, run: {env['RUN_URL']}\n\n{todo}\n\n"
            f"Attempt {len(issues) + 1} of {MAX_ISSUES} for `{tag}`." +
            (f" Earlier issues for this tag:{history}" if issues else "") +
            f"\n\n```text\n{excerpt}\n```\n\n{marker}")
    if dry:
        print(title, "\n", body)
    url = gh("issue", "create", "-R", repo, "--title", title, "--body", body, write=True).strip()
    for i in open_issues:
        gh("issue", "close", str(i["number"]), "-R", repo,
           "--comment", f"Superseded by {url or 'a newer issue'}.", write=True)


def close():
    for i in tag_issues():
        if i["state"] == "OPEN":
            gh("issue", "close", str(i["number"]), "-R", repo,
               "--comment", f"Built and released as {env['RELEASE']}.", write=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"] and sys.argv[2:] in (["conflict"], ["build"]):
        report(sys.argv[2])
    elif sys.argv[1:] == ["close"]:
        close()
    else:
        sys.exit(__doc__)
