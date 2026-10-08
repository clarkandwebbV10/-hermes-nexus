from __future__ import annotations
import argparse, base64, hashlib, json
from pathlib import Path
from cryptography.hazmat.primitives import serialization

def canonical_payload(payload):
    return json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description="Verify a Hidden Viper / Great Ape AI Ed25519 provenance receipt")
    ap.add_argument("receipt")
    ap.add_argument("--public-key",default=str(Path(__file__).with_name("OPERATOR_PUBLIC_KEY.pem")))
    ap.add_argument("--artifact")
    args=ap.parse_args()

    receipt=json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    payload=receipt["payload"]
    canonical=canonical_payload(payload)

    if hashlib.sha256(canonical).hexdigest()!=receipt["canonicalPayloadSha256"]:
        raise SystemExit("INVALID: canonical payload hash mismatch")

    public=serialization.load_pem_public_key(Path(args.public_key).read_bytes())
    public.verify(base64.b64decode(receipt["signatureBase64"]),canonical)

    result={"signatureValid":True,"receiptId":payload["receiptId"],"artifactSha256":payload["artifactSha256"]}
    if args.artifact:
        actual=sha256_file(args.artifact)
        result["artifactProvided"]=str(Path(args.artifact))
        result["artifactHashMatches"]=actual==payload["artifactSha256"]
        result["actualArtifactSha256"]=actual
        if not result["artifactHashMatches"]:
            print(json.dumps(result,indent=2))
            raise SystemExit(2)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
