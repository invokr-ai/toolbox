# Hammer — isolated Python tools for invokr

The kit provides 30 independent tools.
[Full Hermes disposition](catalog/README.md) accounts for all 94 named source
tools, including native replacements and runtime/gateway blockers. An adapter
implements only the operations documented in its own README, not every Hermes
provider/backend option.

Python 3.11+ on Linux. Each directory is complete: plugin.json, main.py, exact
requirements, offline tests and README. No runtime cross-tool imports or shared
mutable state. Dependencies are restricted to three hash-locked document parsers.

## Tools and permissions

Approval: offline tools `ask`; network reads `ask_once` (Auto mode prompts until a
standing grant covers the call); side-effecting tools `always_ask` (http_api,
spotify_playback, spotify_queue, ha_call_service, discord, github_pr). `ask_once`/`always_ask`
need an invokr with those policies; older invokr treats them as `ask`. All tools:
`code_execution` tier, one-shot execution, no workspace
reads/writes and no persistent scratch. Limits: 128 MiB declared memory, 64 KiB
input and network response, 30 KB serialized output. Offline tools use 3 seconds;
network integrations 15 seconds; synchronous inference 60 seconds. No retries.
Success is `{"result":"<JSON containing data>"}`; errors are
`{"error":"invalid_request: explanation"}`. Few required primitive arguments,
defaults for optional fields, unknown arguments rejected.

| Tool | Specification | Network allowlist | Timeout |
| --- | --- | --- | --- |
| [calculate](tools/calculate/README.md) | Evaluate bounded arithmetic: + - * / // % and parentheses. | off | 3 s |
| [code_outline](tools/code_outline/README.md) | List Python classes, functions, arguments and docstrings without executing source. | off | 3 s |
| [csv_query](tools/csv_query/README.md) | Filter CSV rows by exact column value; return JSON rows. | off | 3 s |
| [datetime](tools/datetime/README.md) | Shift an offset-aware ISO timestamp and convert its UTC offset. | off | 3 s |
| [discord](tools/discord/README.md) | Read Discord channel messages or send a text message. | discord.com | 15 s |
| [discord_admin](tools/discord_admin/README.md) | List Discord guild channels or roles without changing them. | discord.com | 15 s |
| [github_pr](tools/github_pr/README.md) | Open a GitHub pull request from an already-pushed branch. | api.github.com | 15 s |
| [docx_extract](tools/docx_extract/README.md) | Extract plain paragraphs from base64 DOCX without external relationships. | off | 3 s |
| [ha_call_service](tools/ha_call_service/README.md) | Call one Home Assistant service with explicit JSON data. | homeassistant.example.invalid | 15 s |
| [ha_get_state](tools/ha_get_state/README.md) | Read the current Home Assistant state of one entity. | homeassistant.example.invalid | 15 s |
| [ha_list_entities](tools/ha_list_entities/README.md) | List Home Assistant entities, optionally filtered by domain. | homeassistant.example.invalid | 15 s |
| [ha_list_services](tools/ha_list_services/README.md) | List Home Assistant services, optionally filtered by domain. | homeassistant.example.invalid | 15 s |
| [html_extract](tools/html_extract/README.md) | Extract readable text and safe links from supplied HTML. | off | 3 s |
| [http_api](tools/http_api/README.md) | Call approved HTTPS JSON APIs with an explicit method and optional JSON body. | api.github.com | 15 s |
| [json_query](tools/json_query/README.md) | Select JSON by JSON Pointer; return value or object keys. | off | 3 s |
| [markdown_convert](tools/markdown_convert/README.md) | Convert Markdown to HTML with tables and fenced code blocks. | off | 3 s |
| [pdf_extract](tools/pdf_extract/README.md) | Extract a bounded PDF page text layer from base64 bytes; no OCR. | off | 3 s |
| [regex_search](tools/regex_search/README.md) | Find regex matches in supplied text with line numbers. | off | 3 s |
| [spotify_albums](tools/spotify_albums/README.md) | Read one Spotify album or a page of its tracks. | api.spotify.com | 15 s |
| [spotify_devices](tools/spotify_devices/README.md) | List available Spotify playback devices. | api.spotify.com | 15 s |
| [spotify_library](tools/spotify_library/README.md) | Read one page of your saved Spotify tracks. | api.spotify.com | 15 s |
| [spotify_playback](tools/spotify_playback/README.md) | Read Spotify playback state or control active playback. | api.spotify.com | 15 s |
| [spotify_playlists](tools/spotify_playlists/README.md) | List your Spotify playlists or read playlist items. | api.spotify.com | 15 s |
| [spotify_queue](tools/spotify_queue/README.md) | Read the Spotify queue or append one track or episode. | api.spotify.com | 15 s |
| [spotify_search](tools/spotify_search/README.md) | Search Spotify for tracks, artists or albums. | api.spotify.com | 15 s |
| [text_patch](tools/text_patch/README.md) | Replace one exact text match and preview a unified diff. | off | 3 s |
| [units](tools/units/README.md) | Convert length, mass, duration, or temperature units. | off | 3 s |
| [xlsx_read](tools/xlsx_read/README.md) | Read cached cell values from a base64 XLSX worksheet; never evaluate formulas. | off | 3 s |
| [xml_query](tools/xml_query/README.md) | Select XML elements by a simple ElementTree path; reject DTDs and entities. | off | 3 s |
| [yaml_query](tools/yaml_query/README.md) | Select a YAML value by JSON Pointer; reject aliases and custom tags. | off | 3 s |
| [zip_inspect](tools/zip_inspect/README.md) | List ZIP metadata from base64 bytes without extracting files. | off | 3 s |

## Install and enable

Validate before installing:

```sh
make test
make lint-ci
```

Copy selected complete directories into invokr's toolbox root. For example,
from this repository, with a destination that does not already exist:

```sh
mkdir -p ~/.invokr/toolbox
cp -R tools/json_query ~/.invokr/toolbox/json_query
```

Check the destination first; do not accidentally nest or overwrite an existing
installation. Install other tools the same way. Alternatively, set
`INVOKR_TOOLBOX_DIR=/absolute/path/to/toolbox/tools` to load this kit directly;
that selects this root instead of your existing toolbox root. Restart invokr,
or use its toolbox discovery refresh through `tool_search`. The namespace is
`hammer`; call names are the names in the table. Per-call approval
still applies. Remove an installed tool directory and restart to disable it.

Required operator settings:

- Keep `toolbox.isolate_env: true` and an empty `toolbox.env` map.
- Keep `toolbox.allow_unsandboxed: false`; do not enable
  `INVOKR_TOOLBOX_ALLOW_UNSANDBOXED`, YOLO mode, or a whole-agent container setup
  that bypasses individual toolbox namespaces.
- Leave `toolbox.venv_dir` unset. No shared venv, state directory, cache override
  or credential passthrough. Use the normal system Python interpreter, outside
  any tool directory.

Invokr prepares an independent `.venv` for each plugin. Most tools have no external
packages. YAML, Markdown and PDF tools declare exact dependency pins, import maps
and complete SHA-256 wheel locks. Resolve/approve/install dependencies separately
under invokr's supply-chain policy before running tests. Tests never install
packages or access providers. See [contract](contracts/README.md).

Network integrations require explicit per-tool configuration documented in their
READMEs. Create that tool's `.secrets.json` with only its scoped token, mode 0600;
never share credential files, use symlinks, or pass ambient environment secrets.
Home Assistant needs an approved public HTTPS proxy hostname configured in both
the manifest and implementation. No tool is enabled or provisioned automatically.

## Isolation model and limits

Invokr's Linux user/mount/PID/network namespaces enforce the boundary. Each
invocation sees its own tool directory and venv read-only, the runtime mounts,
and a private ephemeral `/tmp`. No workspace mount is requested. Sibling tools
and their environments are outside that namespace's mounted filesystem. Failed
calls terminate their own one-shot process; there is no shared daemon or state.
No runtime imports come from another tool or from kit-level code.

Scratch policy: **none required or used**. At invokr `3ffb0f9`, `plugin.json`
has no custom scratch-path declaration. We do not invent an ignored permission
field or grant workspace writes to simulate one. The sandbox supplies writable
private `/tmp` even to a read-only plugin; this is ephemeral namespace-local
storage, not permission to write any host directory. A stricter policy allowing
only a manifest-named scratch path requires an invokr runtime change and cannot
be enforced by this standalone kit alone.

Containment assumes a working, patched Linux kernel, namespace support, and the
settings above. Resource caps bound these tools' computations; they do not claim
complete host availability isolation against arbitrary malicious native code
(for example, invokr does not provide per-plugin cgroup CPU/PID quotas here).
Running `python3 main.py` directly is for trusted tests, not sandboxed execution.
The validator checks contracts and obvious import drift, not arbitrary-code
security. Review additions before installation.

Network-off tools get a distinct network namespace. Network tools declare exact
hosts and independently validate/pin public IPs with verified TLS, no redirects,
proxies or ambient auth. Invokr's DNS host scoping is **not a kernel egress
firewall**: a malicious replacement network script could use literal-IP egress.
The kit cannot promise complete containment against malicious code beyond the
target runtime's actual boundaries. It does not grant workspace access to work
around these limits. Remote API state changes prompt only as their approval policy allows: `ask` (and `ask_once` once granted) can run unattended in Auto mode.

## Add a tool

1. Copy `template/` into `tools/<name>/`; never import shared runtime code.
2. Rename the manifest/example; use short descriptions and at most three required primitive parameters.
3. Implement `run(args)` with bounded data. Keep envelope validation and output/deadline guards.
4. For network tools, copy `network.py.example` and optionally `auth.py.example` into the tool itself, declare exact hosts and select a 15- or 60-second limit. Keep environment isolation.
5. Prefer stdlib. External imports require exact full-closure pins, `dependencies.json` and SHA-256 wheel `requirements.lock`; preparation happens separately from offline tests.
6. Add meaningful offline success/error/adversarial tests, update the tool README and catalog, run the checks below.
7. Commit the complete tool directory once: `tool(<name>): <purpose>`. Later corrections amend/fixup that commit. Push after each commit. Shared validator/template/docs commits precede all tools.

Each tool commit can be cherry-picked or reverted independently. Shared infrastructure
is needed only for kit validation, not execution. Network mutations are explicit
operations; no tests send messages, change devices or spend provider credits.

## Checks

```sh
GOTOOLCHAIN=go1.26.3 make test
GOTOOLCHAIN=go1.26.3 make lint-ci
GOTOOLCHAIN=go1.26.3 make contract INVOKR_SOURCE=/path/to/invokr-snapshot
```

Target invokr commit: `3ffb0f91204d461706f79b7e448f51d5c4c9f24e`.
The overlay loads every actual manifest through invokr's toolbox loader and
validates examples. Stdlib offline tools also run inside its real namespace
sandbox through actual result decoders. Network examples and dependency tools
are loader-only checks; Python behavior tests use mocks or preprepared isolated
dependencies. A separate adversarial probe checks sibling/host read and write
denial, environment isolation, private scratch and distinct network namespace.
Missing sandbox support fails rather than falling back to unsandboxed execution.

Run invokr's own `GOTOOLCHAIN=go1.26.3 make test` and `make lint-ci` in a disposable
source snapshot too. See [validation](VALIDATION.md), [source decisions](SOURCES.md)
and [contract details](contracts/README.md). No invokr checkout edits are required.
