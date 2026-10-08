from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import socket
import sys
import urllib.request
from pathlib import Path
from typing import Iterable

VERSION = "0.1.3"
PRODUCT = "Hidden Viper"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_file_exists(claim: dict) -> tuple[bool, dict]:
    path = Path(claim["target"]).expanduser()
    actual = path.exists()
    expected = bool(claim.get("expected", True))
    return actual == expected, {"path": str(path.resolve()) if path.exists() else str(path), "exists": actual}


def check_file_sha256(claim: dict) -> tuple[bool, dict]:
    path = Path(claim["target"]).expanduser()
    if not path.is_file():
        return False, {"path": str(path), "error": "file missing"}
    actual = sha256_file(path)
    expected = str(claim["expected"]).lower()
    return actual == expected, {"path": str(path.resolve()), "sha256": actual, "bytes": path.stat().st_size}


def check_file_contains(claim: dict) -> tuple[bool, dict]:
    path = Path(claim["target"]).expanduser()
    if not path.is_file():
        return False, {"path": str(path), "error": "file missing"}
    needle = str(claim["expected"])
    text = path.read_text(encoding=claim.get("encoding", "utf-8"), errors="replace")
    found = needle in text
    return found, {"path": str(path.resolve()), "contains": found, "needleSha256": hashlib.sha256(needle.encode()).hexdigest()}


def check_tcp_listen(claim: dict) -> tuple[bool, dict]:
    host = claim.get("host", "127.0.0.1")
    port = int(claim["target"])
    timeout = float(claim.get("timeoutSeconds", 1.0))
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        code = sock.connect_ex((host, port))
    finally:
        sock.close()
    listening = code == 0
    expected = bool(claim.get("expected", True))
    return listening == expected, {"host": host, "port": port, "listening": listening}


def check_http_status(claim: dict) -> tuple[bool, dict]:
    url = str(claim["target"])
    expected = int(claim.get("expected", 200))
    timeout = float(claim.get("timeoutSeconds", 3.0))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = int(response.status)
            return status == expected, {"url": url, "status": status}
    except Exception as exc:
        return False, {"url": url, "error": f"{type(exc).__name__}: {exc}"}


CHECKS = {
    "file_exists": check_file_exists,
    "file_sha256": check_file_sha256,
    "file_contains": check_file_contains,
    "tcp_listen": check_tcp_listen,
    "http_status": check_http_status,
}


def verify(claim: dict) -> dict:
    receipt = {"schema": "hidden-viper.receipt/v1", "hiddenViperVersion": VERSION, "observedAtUtc": utc_now(), "claim": claim}
    kind = claim.get("kind")
    if kind not in CHECKS:
        receipt["status"] = "UNVERIFIED"
        receipt["observation"] = {"error": f"unsupported claim kind: {kind!r}"}
    else:
        try:
            ok, observation = CHECKS[kind](claim)
            receipt["status"] = "VERIFIED" if ok else "CONTRADICTED"
            receipt["observation"] = observation
        except Exception as exc:
            receipt["status"] = "UNVERIFIED"
            receipt["observation"] = {"error": f"{type(exc).__name__}: {exc}"}
    receipt["receiptSha256"] = canonical_hash(receipt)
    return receipt


def stream_verify(lines: Iterable[str]) -> tuple[list[dict], int]:
    """Verify newline-delimited JSON claims without binding to one agent framework.

    Exit codes:
      0: every parsed claim was VERIFIED
      1: at least one claim was CONTRADICTED and none were UNVERIFIED
      2: at least one line was UNVERIFIED, including malformed JSON
    """
    receipts: list[dict] = []
    saw_contradicted = False
    saw_unverified = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            claim = json.loads(line)
            if not isinstance(claim, dict):
                raise ValueError("claim must be a JSON object")
            receipt = verify(claim)
        except Exception as exc:
            receipt = {
                "schema": "hidden-viper.receipt/v1",
                "hiddenViperVersion": VERSION,
                "observedAtUtc": utc_now(),
                "claim": None,
                "status": "UNVERIFIED",
                "observation": {
                    "error": f"{type(exc).__name__}: {exc}",
                    "lineNumber": line_number,
                    "inputLineSha256": hashlib.sha256(line.encode()).hexdigest(),
                },
            }
            receipt["receiptSha256"] = canonical_hash(receipt)

        receipts.append(receipt)
        saw_contradicted |= receipt["status"] == "CONTRADICTED"
        saw_unverified |= receipt["status"] == "UNVERIFIED"

    if saw_unverified:
        return receipts, 2
    if saw_contradicted:
        return receipts, 1
    return receipts, 0


def run_demo() -> int:
    demo = Path("hidden-viper-demo-output.txt")
    demo.write_text("deployment-state=ready\n", encoding="utf-8")
    claims = [
        {"id": "demo-file", "kind": "file_exists", "target": str(demo), "expected": True},
        {"id": "demo-content", "kind": "file_contains", "target": str(demo), "expected": "deployment-state=ready"},
        {"id": "demo-contradiction", "kind": "file_exists", "target": "definitely-not-created.txt", "expected": True},
    ]
    receipts = [verify(claim) for claim in claims]
    print(json.dumps(receipts, indent=2))
    try:
        demo.unlink()
    except OSError:
        pass
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

    args = parser.parse_args()

    if args.cmd == "demo":
        raise SystemExit(run_demo())

    if args.cmd == "stream":
        receipts, code = stream_verify(sys.stdin)
        rendered = "".join(json.dumps(receipt, separators=(",", ":"), ensure_ascii=False) + "\n" for receipt in receipts)
        if args.out:
            Path(args.out).write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        raise SystemExit(code)

    claim = json.loads(Path(args.claim_json).read_text(encoding="utf-8"))
    receipt = verify(claim)
    rendered = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if receipt["status"] == "VERIFIED" else 1)


if __name__ == "__main__":
    main()
