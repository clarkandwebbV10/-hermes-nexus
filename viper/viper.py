from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import errno
import ipaddress
import tempfile
import json
import math
import os
import re
import stat
import socket
import sys
import urllib.request
import urllib.error
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

VERSION = "0.1.3"
PRODUCT = "Hidden Viper"
MAX_HASH_BYTES = 256 * 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_CLAIM_BYTES = 65536


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def checked_stat(path):
    """Inspect a path without following a final link or masking permission errors."""
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        raise ValueError("linked artifact paths are unsupported")
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("artifact must be a regular file")
    return st


def file_identity(st):
    """Metadata that path-stat and handle-stat APIs can compare across platforms."""
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def file_state(st):
    """A same-API snapshot includes ctime to detect metadata-only changes."""
    return (*file_identity(st), st.st_ctime_ns)


@contextmanager
def bounded_artifact(path, limit):
    """Read one bounded regular file; reject observed changes and replaced objects.
    A stable operator-controlled parent directory remains a trust requirement.
    """
    path = Path(path)
    before = checked_stat(path)
    if before.st_size > limit:
        raise ValueError("artifact exceeds observation size limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ValueError("artifact disappeared before observation") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or file_identity(opened) != file_identity(before):
            raise ValueError("artifact changed before observation")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            yield stream, opened
            try:
                current = checked_stat(path)
            except FileNotFoundError as exc:
                raise ValueError("artifact disappeared during observation") from exc
            if file_state(os.fstat(stream.fileno())) != file_state(opened) or file_state(current) != file_state(before):
                raise ValueError("artifact changed during observation")
    finally:
        if fd is not None:
            os.close(fd)


def hash_artifact(path):
    h = hashlib.sha256()
    count = 0
    with bounded_artifact(path, MAX_HASH_BYTES) as (f, initial):
        while True:
            chunk = f.read(min(1024 * 1024, MAX_HASH_BYTES - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > MAX_HASH_BYTES:
                raise ValueError("artifact grew beyond observation size limit")
            h.update(chunk)
        if count != initial.st_size:
            raise ValueError("artifact size changed during observation")
    return h.hexdigest(), count


def sha256_file(path: str | Path) -> str:
    return hash_artifact(path)[0]


def canonical_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def boolean_expectation(claim: dict) -> bool:
    """Accept JSON booleans only; omission retains the default expectation."""
    expected = claim.get("expected", True)
    if not isinstance(expected, bool):
        raise ValueError("expected must be a JSON boolean (true or false)")
    return expected


def artifact_path(claim):
    target = claim["target"]
    if not isinstance(target, str) or not target or len(target) > 4096 or "\x00" in target:
        raise ValueError("target must be a bounded file path")
    return Path(target).expanduser()


def check_file_exists(claim: dict) -> tuple[bool, dict]:
    expected = boolean_expectation(claim)
    path = artifact_path(claim)
    try:
        checked_stat(path)
        actual = True
    except FileNotFoundError:
        actual = False
    return actual == expected, {"path": str(path), "exists": actual}


def check_file_sha256(claim: dict) -> tuple[bool, dict]:
    path = artifact_path(claim)
    expected = claim["expected"]
    if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
        raise ValueError("expected must be a SHA-256 digest")
    try:
        actual, size = hash_artifact(path)
    except FileNotFoundError:
        return False, {"path": str(path), "error": "file missing"}
    return actual == expected.lower(), {"path": str(path), "sha256": actual, "bytes": size}


def check_file_contains(claim: dict) -> tuple[bool, dict]:
    path = artifact_path(claim)
    needle = claim["expected"]
    if not isinstance(needle, str) or not 0 < len(needle) <= 2048:
        raise ValueError("expected must be nonempty bounded text")
    encoding = claim.get("encoding", "utf-8")
    if encoding not in ("utf-8", "utf-8-sig", "ascii", "utf-16", "utf-16-le", "utf-16-be"):
        raise ValueError("unsupported text encoding")
    try:
        with bounded_artifact(path, MAX_TEXT_BYTES) as (f, initial):
            raw = f.read(MAX_TEXT_BYTES + 1)
            if len(raw) > MAX_TEXT_BYTES or len(raw) != initial.st_size:
                raise ValueError("text artifact changed or exceeds observation limit")
            text = raw.decode(encoding, errors="strict")
    except FileNotFoundError:
        return False, {"path": str(path), "error": "file missing"}
    found = needle in text
    return found, {"path": str(path), "contains": found, "needleSha256": hashlib.sha256(needle.encode()).hexdigest()}


def observation_timeout(claim, default):
    timeout = claim.get("timeoutSeconds", default)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 10:
        raise ValueError("timeoutSeconds must be finite and in (0, 10]")
    return timeout


def check_tcp_listen(claim: dict) -> tuple[bool, dict]:
    expected = boolean_expectation(claim)
    host = claim.get("host", "127.0.0.1")
    port = claim["target"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("target must be an integer TCP port")
    if not isinstance(host, str) or not 0 < len(host) <= 253:
        raise ValueError("invalid TCP host")
    timeout = observation_timeout(claim, 1.0)
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        code = sock.connect_ex((host, port))
    finally:
        sock.close()
    if code == 0:
        return expected is True, {"host": host, "port": port, "listening": True,
                                  "observation": "connection accepted from probe"}
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    refused = {errno.ECONNREFUSED, getattr(errno, "WSAECONNREFUSED", 10061)}
    if loopback and code in refused:
        return expected is False, {"host": host, "port": port, "listening": False,
                                   "observation": "loopback connection refused at probe time"}
    raise OSError(code, "TCP observation inconclusive; absence of a connection does not establish absence of a listener")


class ObserveRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_http_status(claim: dict) -> tuple[bool, dict]:
    url = claim["target"]
    expected = claim.get("expected", 200)
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ValueError("invalid HTTP URL")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None or parts.password is not None or parts.fragment:
        raise ValueError("only credential-free HTTP(S) URLs without fragments are supported")
    if type(expected) is not int or not 100 <= expected <= 599:
        raise ValueError("expected must be an integer HTTP status")
    timeout = observation_timeout(claim, 3.0)
    # Do not follow a redirect or inherit proxy configuration. Observe the named endpoint.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), ObserveRedirect())
    try:
        with opener.open(url, timeout=timeout) as response:
            status = int(response.status)
    except urllib.error.HTTPError as response:
        try:
            status = int(response.code)
        finally:
            response.close()
    return status == expected, {"url": url, "status": status, "redirectFollowed": False}


CHECKS = {
    "file_exists": check_file_exists,
    "file_sha256": check_file_sha256,
    "file_contains": check_file_contains,
    "tcp_listen": check_tcp_listen,
    "http_status": check_http_status,
}


def verify(claim: dict) -> dict:
    receipt = {"schema": "hidden-viper.receipt/v1", "hiddenViperVersion": VERSION, "observedAtUtc": utc_now(), "claim": None}
    try:
        # Validate JSON representability before retaining an untrusted claim in a receipt.
        serialized = json.dumps(claim, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(serialized) > MAX_CLAIM_BYTES:
            raise ValueError("claim exceeds observation size limit")
        receipt["claim"] = claim
        if not isinstance(claim, dict):
            raise ValueError("claim must be a JSON object")
        kind = claim.get("kind")
        if not isinstance(kind, str) or kind not in CHECKS:
            receipt["status"] = "UNVERIFIED"
            receipt["observation"] = {"error": f"unsupported claim kind: {kind!r}"}
        else:
            ok, observation = CHECKS[kind](claim)
            receipt["status"] = "VERIFIED" if ok else "CONTRADICTED"
            receipt["observation"] = observation
    except Exception as exc:
        receipt["status"] = "UNVERIFIED"
        receipt["observation"] = {"error": f"{type(exc).__name__}: {exc}"}
    receipt["receiptSha256"] = canonical_hash(receipt)
    return receipt


def invalid_stream_receipt(line_number, input_digest, reason):
    receipt = {
        "schema": "hidden-viper.receipt/v1",
        "hiddenViperVersion": VERSION,
        "observedAtUtc": utc_now(),
        "claim": None,
        "status": "UNVERIFIED",
        "observation": {"error": reason, "lineNumber": line_number,
                        "inputLineSha256": input_digest},
    }
    receipt["receiptSha256"] = canonical_hash(receipt)
    return receipt


def stream_receipt(raw, line_number, input_digest):
    from viper_events import unique_fields, MAX_LINE
    if raw is None or len(raw) > MAX_LINE:
        return invalid_stream_receipt(line_number, input_digest, "claim exceeds 64 KiB")
    if not raw.strip():
        return None
    try:
        def reject_constant(value):
            raise ValueError("non-finite JSON constant")
        claim = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields,
                           parse_constant=reject_constant)
        if not isinstance(claim, dict):
            raise ValueError("claim must be a JSON object")
        # Reject escaped lone surrogates, including in nested strings, before verifying.
        json.dumps(claim, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return verify(claim)
    except (ValueError, UnicodeError, RecursionError):
        return invalid_stream_receipt(line_number, input_digest, "invalid JSON claim")


def stream_verify(lines: Iterable[str]) -> tuple[list[dict], int]:
    """Compatibility collector for finite, caller-controlled iterables.
    Use write_stream for incremental bounded CLI input/output.
    """
    receipts = []
    code = 0
    for line_number, line in enumerate(lines, start=1):
        try:
            raw = line.encode("utf-8")
        except UnicodeError:
            raw = line.encode("utf-8", errors="surrogatepass")
        receipt = stream_receipt(raw, line_number, hashlib.sha256(raw).hexdigest())
        if receipt is not None:
            receipts.append(receipt)
            code = max(code, {"VERIFIED": 0, "CONTRADICTED": 1, "UNVERIFIED": 2}[receipt["status"]])
    return receipts, code if receipts else 2


def write_stream(source, output, mirror=None):
    """Emit each bounded JSONL observation before reading the next claim."""
    from viper_events import bounded_lines
    code, count = 0, 0
    for line_number, (raw, digest) in enumerate(bounded_lines(source), start=1):
        receipt = stream_receipt(raw, line_number, digest)
        if receipt is None:
            continue
        rendered = json.dumps(receipt, separators=(",", ":"), ensure_ascii=True) + "\n"
        if mirror is not None:
            mirror.write(rendered)
            mirror.flush()
        output.write(rendered)
        output.flush()
        count += 1
        code = max(code, {"VERIFIED": 0, "CONTRADICTED": 1, "UNVERIFIED": 2}[receipt["status"]])
    return code if count else 2


def run_demo() -> int:
    # No caller-owned path is created, overwritten or removed.
    with tempfile.TemporaryDirectory(prefix="hidden-viper-demo-") as folder:
        root = Path(folder)
        demo = root / "sample.txt"
        demo.write_text("deployment-state=ready\n", encoding="utf-8")
        claims = [
            {"id": "demo-file", "kind": "file_exists", "target": str(demo), "expected": True},
            {"id": "demo-content", "kind": "file_contains", "target": str(demo), "expected": "deployment-state=ready"},
            {"id": "demo-contradiction", "kind": "file_exists", "target": str(root / "absent.txt"), "expected": True},
        ]
        receipts = [verify(claim) for claim in claims]
        print(json.dumps(receipts, indent=2))
        return 0 if [r["status"] for r in receipts] == ["VERIFIED", "VERIFIED", "CONTRADICTED"] else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Hidden Viper: independent ground-state verifier for AI-agent claims")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")

    verify_parser = sub.add_parser("verify", help="verify one JSON claim file")
    verify_parser.add_argument("claim_json")
    verify_parser.add_argument("--out")

    stream_parser = sub.add_parser("stream", help="verify newline-delimited JSON claims from stdin")
    stream_parser.add_argument("--out", help="optional JSONL receipt output file")

    events_parser = sub.add_parser("events", help="verify JSONL events against an operator-provided artifact manifest")
    events_parser.add_argument("--manifest", required=True)

    args = parser.parse_args()

    if args.cmd == "events":
        from viper_events import verify_events, ManifestError

        try:
            code = verify_events(sys.stdin.buffer, sys.stdout, args.manifest)
        except ManifestError as error:
            events_parser.exit(2, f"invalid verification manifest: {error}\n")
        except (OSError, ValueError, RecursionError) as error:
            events_parser.exit(2, f"event input/output failed; partial receipts are not a completed run: {error}\n")
        raise SystemExit(code)

    if args.cmd == "demo":
        raise SystemExit(run_demo())

    if args.cmd == "stream":
        try:
            if args.out:
                # Exclusive create prevents accidentally overwriting input or other evidence.
                with Path(args.out).open("x", encoding="utf-8") as mirror:
                    code = write_stream(sys.stdin.buffer, sys.stdout, mirror)
            else:
                code = write_stream(sys.stdin.buffer, sys.stdout)
        except OSError:
            stream_parser.exit(2, "stream input/output failed; any partial receipts are not a completed run\n")
        raise SystemExit(code)

    try:
        with bounded_artifact(Path(args.claim_json), MAX_CLAIM_BYTES) as (source, initial):
            raw = source.read(MAX_CLAIM_BYTES + 1)
            if len(raw) != initial.st_size or len(raw) > MAX_CLAIM_BYTES:
                raise ValueError("claim file changed or exceeds size limit")
        receipt = stream_receipt(raw, 1, hashlib.sha256(raw).hexdigest())
        if receipt is None:
            receipt = invalid_stream_receipt(1, hashlib.sha256(raw).hexdigest(), "empty claim")
        rendered = json.dumps(receipt, indent=2, ensure_ascii=True) + "\n"
        if args.out:
            with Path(args.out).open("x", encoding="utf-8") as output:
                output.write(rendered)
        print(rendered, end="", flush=True)
        raise SystemExit(0 if receipt["status"] == "VERIFIED" else 1)
    except (OSError, ValueError, RecursionError):
        verify_parser.exit(2, "claim input/output failed; existing evidence was not overwritten\n")


if __name__ == "__main__":
    main()
