# github_pr

Open a GitHub pull request from an already-pushed branch.

## Why it exists

invokr's shell sandbox mounts no `~/.config/gh`, so `gh pr create` inside it
reports "not logged in". This tool does the one API call outside the sandbox
with its own scoped token. Push the branch first (invokr's `git_write` with
`op=push`); this tool never pushes.

## Install and configure

Copy this directory into your invokr toolbox root, or install it from invokr's
`/tools` → Install tab. See the kit README for runtime configuration. No pip
packages are needed.
Create `.secrets.json` **inside this tool directory only** with `{"token":"YOUR_SCOPED_TOKEN"}`;
set mode `0600`. Use a fine-grained token limited to the repositories you need,
with **Pull requests: read and write**. Never place it in arguments, environment
variables, examples, git or another tool's directory. Missing/expired
credentials fail clearly; this tool does not refresh tokens.

Example arguments: `{"repo": "octo/demo", "head": "feature", "base": "main", "title": "Add feature"}`.

Creates one pull request per call and returns its number, URL, state and draft
flag. No edits, merges, reviews, labels or listing. Approval is `always_ask`:
every PR is a visible, outward-facing change.

## Permissions and limits

Network: HTTPS port 443 on `api.github.com` only. Public IPs only; DNS is validated then
pinned, TLS verified, redirects/proxies refused. No ambient credentials.
Workspace reads/writes disabled; no persistent scratch or state.
15-second invokr deadline, 12-second process alarm, 8-second socket timeout,
128 MiB declared memory, 64 KiB input/response and 30 KB serialized output cap.
Creation is not retried after a timeout because the outcome may be unknown;
check the repository before calling again.

Success: `{"result":"{\"data\":...}"}`; failure:
`{"error":"invalid_request: ..."}`. Provider errors omit response bodies, so a
422 (PR already exists, no commits between branches) reports only the status.

## Source and scope

Primary API reference: https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request.

## Offline tests

`python3 -I -B test_main.py` tests the wire request, auth isolation, repo and
branch validation, unsafe URLs, private/mixed DNS, TLS pinning, response limits
and protocol errors using mocks. No live provider calls.
