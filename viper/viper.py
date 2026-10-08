from __future__ import annotations
import argparse, datetime as dt, hashlib, json, socket, urllib.request
from pathlib import Path
VERSION="0.1.2"
def utc_now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def canonical_hash(obj):
    raw=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
def check_file_exists(claim):
    p=Path(claim["target"]).expanduser()
    actual=p.exists(); expected=bool(claim.get("expected",True))
    return actual==expected,{"path":str(p.resolve()) if p.exists() else str(p),"exists":actual}
def check_file_sha256(claim):
    p=Path(claim["target"]).expanduser()
    if not p.is_file(): return False,{"path":str(p),"error":"file missing"}
    actual=sha256_file(p); expected=str(claim["expected"]).lower()
    return actual==expected,{"path":str(p.resolve()),"sha256":actual,"bytes":p.stat().st_size}
def check_file_contains(claim):
    p=Path(claim["target"]).expanduser()
    if not p.is_file(): return False,{"path":str(p),"error":"file missing"}
    needle=str(claim["expected"])
    text=p.read_text(encoding=claim.get("encoding","utf-8"),errors="replace")
    found=needle in text
    return found,{"path":str(p.resolve()),"contains":found,"needleSha256":hashlib.sha256(needle.encode()).hexdigest()}
def check_tcp_listen(claim):
    host=claim.get("host","127.0.0.1"); port=int(claim["target"]); timeout=float(claim.get("timeoutSeconds",1.0))
    s=socket.socket(); s.settimeout(timeout)
    try: code=s.connect_ex((host,port))
    finally: s.close()
    listening=code==0; expected=bool(claim.get("expected",True))
    return listening==expected,{"host":host,"port":port,"listening":listening}
def check_http_status(claim):
    url=str(claim["target"]); expected=int(claim.get("expected",200)); timeout=float(claim.get("timeoutSeconds",3.0))
    try:
        with urllib.request.urlopen(url,timeout=timeout) as r:
            status=int(r.status); return status==expected,{"url":url,"status":status}
    except Exception as exc:
        return False,{"url":url,"error":f"{type(exc).__name__}: {exc}"}
CHECKS={"file_exists":check_file_exists,"file_sha256":check_file_sha256,"file_contains":check_file_contains,"tcp_listen":check_tcp_listen,"http_status":check_http_status}
def verify(claim):
    receipt={"schema":"hidden-viper.receipt/v1","hiddenViperVersion":VERSION,"observedAtUtc":utc_now(),"claim":claim}
    kind=claim.get("kind")
    if kind not in CHECKS:
        receipt["status"]="UNVERIFIED"; receipt["observation"]={"error":f"unsupported claim kind: {kind!r}"}
    else:
        try:
            ok,obs=CHECKS[kind](claim); receipt["status"]="VERIFIED" if ok else "CONTRADICTED"; receipt["observation"]=obs
        except Exception as exc:
            receipt["status"]="UNVERIFIED"; receipt["observation"]={"error":f"{type(exc).__name__}: {exc}"}
    receipt["receiptSha256"]=canonical_hash(receipt); return receipt
def run_demo():
    demo=Path("hidden-viper-demo-output.txt"); demo.write_text("deployment-state=ready\n",encoding="utf-8")
    claims=[
        {"id":"demo-file","kind":"file_exists","target":str(demo),"expected":True},
        {"id":"demo-content","kind":"file_contains","target":str(demo),"expected":"deployment-state=ready"},
        {"id":"demo-contradiction","kind":"file_exists","target":"definitely-not-created.txt","expected":True}]
    receipts=[verify(c) for c in claims]; print(json.dumps(receipts,indent=2))
    try: demo.unlink()
    except OSError: pass
    return 0 if [r["status"] for r in receipts]==["VERIFIED","VERIFIED","CONTRADICTED"] else 2
def main():
    ap=argparse.ArgumentParser(description="Hidden Viper: independent ground-state verifier for AI-agent claims")
    ap.add_argument("--version",action="version",version=VERSION)
    sub=ap.add_subparsers(dest="cmd",required=True); sub.add_parser("demo")
    v=sub.add_parser("verify"); v.add_argument("claim_json"); v.add_argument("--out")
    args=ap.parse_args()
    if args.cmd=="demo": raise SystemExit(run_demo())
    claim=json.loads(Path(args.claim_json).read_text(encoding="utf-8")); receipt=verify(claim)
    rendered=json.dumps(receipt,indent=2,ensure_ascii=False)+"\n"
    if args.out: Path(args.out).write_text(rendered,encoding="utf-8")
    print(rendered,end=""); raise SystemExit(0 if receipt["status"]=="VERIFIED" else 1)
if __name__=="__main__": main()
