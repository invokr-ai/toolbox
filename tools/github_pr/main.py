import json
import math
import signal
import sys
from pathlib import Path
# Copy into the individual tool; never import this shared template at runtime.
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


def request(url, method="GET", body=None, headers=None):
    """One bounded HTTPS request; no proxies, redirects, ambient auth or cookies."""
    if any(ord(char) < 33 or ord(char) == 127 for char in url):
        raise ValueError("URL must not contain whitespace or controls")
    parsed = urlsplit(url)
    spec = json.loads(Path(__file__).with_name("plugin.json").read_text())
    hosts = spec["network"]["allow_hosts"]
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.fragment):
        raise ValueError("URL must be HTTPS port 443 on a declared host, without credentials or fragment")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("destination must resolve only to public IP addresses")
    family, kind, protocol, _, address = addresses[0]
    raw = socket.socket(family, kind, protocol)
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=8)
    try:
        raw.settimeout(8)
        raw.connect(address)  # Pin the checked address: never resolve the hostname a second time.
        connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request_headers = {"Accept-Encoding": "identity", "User-Agent": "invokr-hammer/1"}
        request_headers.update(headers or {})
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise ValueError("redirect refused; use the approved final URL")
        if not 200 <= response.status < 300:
            raise ValueError("HTTP status " + str(response.status))
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("compressed response refused")
        data = response.read(65537)
        if len(data) > 65536:
            raise ValueError("response exceeds 64 KiB")
        return response.status, response.getheader("Content-Type", ""), data
    except (http.client.HTTPException, OSError) as exc:
        # Do not echo URLs, tokens, query parameters or provider error bodies.
        raise ValueError("HTTPS request failed: " + type(exc).__name__) from exc
    finally:
        connection.close()
        raw.close()


ORIGIN = 'https://api.github.com'
AUTH_PREFIX = 'Bearer '

import os
import stat
import re


def token():
    """Read only this tool's explicitly provisioned, owner-only credential."""
    path = Path(__file__).with_name('.secrets.json')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValueError('configure this tool with an owner-only .secrets.json token') from exc
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise ValueError('.secrets.json must be a regular owner-only file owned by this user')
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise ValueError('credential file exceeds 8 KiB')
    try:
        value = json.loads(raw)['token']
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('credential file must contain a token string') from exc
    if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError('token must contain printable ASCII without whitespace')
    return value


def api(path, method='GET', body=None):
    payload = None if body is None else json.dumps(body, allow_nan=False).encode()
    status, content_type, raw = request(ORIGIN + path, method, payload,
        {'Authorization': AUTH_PREFIX + token(), 'Accept': 'application/vnd.github+json',
         'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
    if 'json' not in content_type.lower():
        raise ValueError('provider response must be JSON')
    try:
        result = json.loads(raw, parse_constant=reject_constant)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('provider returned invalid JSON') from exc
    if not isinstance(result, dict):
        raise ValueError('provider must return an object')
    return result


def repo(value):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}', value) or value.endswith(('/.', '/..')):
        raise ValueError('repo must be owner/name')
    return value


def branch(value, key):
    # Git ref-name rules that matter for an API path segment; owner:branch selects a fork head.
    if not re.fullmatch(r'([A-Za-z0-9-]{1,39}:)?[A-Za-z0-9._/-]{1,255}', value) or '..' in value or value.startswith(('-', '/')) or value.endswith(('/', '.lock')):
        raise ValueError(key + ' must be a branch name')
    return value


def run(args):
    if not args['title'].strip():
        raise ValueError('title must not be empty')
    pr = api('/repos/' + repo(args['repo']) + '/pulls', 'POST', {
        'title': args['title'], 'head': branch(args['head'], 'head'), 'base': branch(args['base'], 'base'),
        'body': args['body'], 'draft': args['draft']})
    return {'number': pr.get('number'), 'url': pr.get('html_url'), 'state': pr.get('state'), 'draft': pr.get('draft')}

def reject_constant(value):
    raise ValueError("non-finite JSON number")


def deadline(signum, frame):
    raise TimeoutError("operation exceeded 12 seconds")


def serve():
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(12)
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("input exceeds 64 KiB; send a smaller chunk")
        call = json.loads(raw, parse_constant=reject_constant)
        spec = json.loads(Path(__file__).with_name("plugin.json").read_text())
        if not isinstance(call, dict) or call.get("name") != spec["name"]:
            raise ValueError("name must match plugin name")
        args = call.get("arguments")
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        schema = spec["parameters"]
        if set(args) - schema["properties"].keys():
            raise ValueError("unknown argument")
        for key in schema["required"]:
            if key not in args:
                raise ValueError("missing argument: " + key)
        for key, rule in schema["properties"].items():
            if key not in args:
                if "default" in rule:
                    args[key] = rule["default"]
                continue
            value = args[key]
            types = {"string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,)}
            if type(value) not in types[rule["type"]]:
                raise ValueError(key + " must be " + rule["type"])
            if "enum" in rule and value not in rule["enum"]:
                raise ValueError(key + " must be one of " + str(rule["enum"]))
            if isinstance(value, str) and len(value) > rule.get("maxLength", 32000):
                raise ValueError(key + " is too long")
            if type(value) in (int, float):
                if not math.isfinite(value) or not rule.get("minimum", -1e100) <= value <= rule.get("maximum", 1e100):
                    raise ValueError(key + " is outside allowed range")
        result = json.dumps({"data": run(args)}, ensure_ascii=True, allow_nan=False)
        output = json.dumps({"result": result})
        if len(output.encode()) > 30000:
            raise ValueError("output exceeds 30 KB; send a smaller chunk or lower limit")
    except Exception as exc:  # any failure is a one-line error, never a traceback
        output = json.dumps({"error": "invalid_request: " + str(exc)[:200]})
    finally:
        signal.alarm(0)
    print(output)


if __name__ == "__main__":
    serve()
