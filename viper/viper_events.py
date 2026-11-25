"""Map JSONL events to operator-selected, read-only filesystem observations."""
import hashlib
import json
import re
import stat
from pathlib import Path

MAX_LINE = 65536
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:@-]{0,191}\Z")


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def identifier(value):
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def resolve_claim(root, entry):
    if not isinstance(entry, dict) or set(entry) != {"kind", "target", "expected"}:
        raise ValueError("a manifest claim needs kind, target and expected")
    kind, name, expected = entry["kind"], entry["target"], entry["expected"]
    if kind == "file_exists":
        if type(expected) is not bool:
            raise ValueError("file_exists expects a JSON boolean")
    elif kind == "file_sha256":
        if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            raise ValueError("file_sha256 expects a SHA-256 digest")
    elif kind == "file_contains":
        if not isinstance(expected, str) or not 0 < len(expected) <= 2048:
            raise ValueError("file_contains expects nonempty bounded text")
    else:
        raise ValueError("unsupported manifest check")
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("target must be a portable relative path")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("target must stay within the manifest directory")
    path = root
    for part in parts:
        path = path / part
        try:
            attrs = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("linked artifact paths are unsupported")
        if path == root / name and not stat.S_ISREG(attrs.st_mode):
            raise ValueError("target must be a regular file")
    return {"kind": kind, "target": str(path), "expected": expected}


def load_manifest(filename):
    manifest = Path(filename).resolve(strict=True)
    if manifest.stat().st_size > 1048576:
        raise ValueError("manifest exceeds 1 MiB")
    data = manifest.read_bytes()
    entries = json.loads(data, object_pairs_hook=unique_fields)
    if not isinstance(entries, dict) or not entries or not all(identifier(key) for key in entries):
        raise ValueError("manifest must map claim identifiers to checks")
    return manifest.parent, entries, hashlib.sha256(data).hexdigest()


def bounded_lines(stream):
    while True:
        chunk = stream.readline(MAX_LINE + 1)
        if not chunk:
            return
        if len(chunk) <= MAX_LINE:
            yield chunk, hashlib.sha256(chunk).hexdigest()
            continue
        digest = hashlib.sha256(chunk)
        while chunk and not chunk.endswith(b"\n"):
            chunk = stream.readline(MAX_LINE + 1)
            digest.update(chunk)
        yield None, digest.hexdigest()


def verify_events(stream, output, manifest_path):
    from viper import VERSION, canonical_hash, utc_now, verify

    root, entries, manifest_digest = load_manifest(manifest_path)
    exit_code = 0
    count = 0
    for line_no, (raw, digest) in enumerate(bounded_lines(stream), start=1):
        if raw is not None and not raw.strip():
            continue
        count += 1
        provenance = {"line": line_no, "inputSha256": digest, "manifestSha256": manifest_digest}
        try:
            if raw is None:
                raise ValueError("event exceeds 64 KiB")
            event = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields)
            if not isinstance(event, dict):
                raise ValueError("event must be an object")
            for key in ("source", "id", "type"):
                if identifier(event.get(key)):
                    provenance[key] = event[key]
            if not all(key in provenance for key in ("source", "id", "type")):
                raise ValueError("event requires source, id and type identifiers")
            if event["type"] != "outcome.claimed":
                raise ValueError("event does not assert a measurable outcome")
            claim_id = event.get("claim")
            if not identifier(claim_id) or claim_id not in entries:
                raise ValueError("claim is absent from the operator manifest")
            provenance["claim"] = claim_id
            receipt = verify(resolve_claim(root, entries[claim_id]))
            # The new digest binds the independent observation to the event and manifest.
            del receipt["receiptSha256"]
        except (ValueError, OSError, RecursionError) as error:
            receipt = {"schema": "hidden-viper.receipt/v1", "hiddenViperVersion": VERSION,
                       "observedAtUtc": utc_now(), "claim": None, "status": "UNVERIFIED",
                       "observation": {"error": str(error)}}
        receipt["provenance"] = provenance
        receipt["receiptSha256"] = canonical_hash(receipt)
        output.write(json.dumps(receipt, ensure_ascii=True, separators=(",", ":")) + "\n")
        exit_code = max(exit_code, {"VERIFIED": 0, "CONTRADICTED": 1, "UNVERIFIED": 2}[receipt["status"]])
    return exit_code if count else 2

