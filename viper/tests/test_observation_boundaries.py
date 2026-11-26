"""Bounded artifact and endpoint observation regressions; local fixtures only."""
import errno
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import viper


class ObservationBoundaries(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_permission_failure_is_not_absence(self):
        with patch.object(viper, "checked_stat", side_effect=PermissionError("fixture")):
            result = viper.verify({"kind":"file_exists","target":str(self.root/"denied"),"expected":False})
        self.assertEqual(result["status"],"UNVERIFIED")

    def test_nonregular_artifacts_never_pass(self):
        for kind, expected in (("file_exists",True),("file_contains","x"),("file_sha256","0"*64)):
            with self.subTest(kind=kind):
                result = viper.verify({"kind":kind,"target":str(self.root),"expected":expected})
                self.assertEqual(result["status"],"UNVERIFIED")

    def test_linked_file_rejected(self):
        target = self.root/"fixture"
        target.write_bytes(b"sample")
        link = self.root/"link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this host")
        for expected in (True,False):
            self.assertEqual(viper.verify({"kind":"file_exists","target":str(link),"expected":expected})["status"],"UNVERIFIED")

    @unittest.skipUnless(hasattr(os,"mkfifo"),"FIFO unsupported")
    def test_fifo_is_refused_without_opening(self):
        path = self.root/"fifo"
        os.mkfifo(path)
        with patch.object(viper.os,"open",side_effect=AssertionError("must not open FIFO")) as opener:
            result = viper.verify({"kind":"file_sha256","target":str(path),"expected":"0"*64})
        opener.assert_not_called()
        self.assertEqual(result["status"],"UNVERIFIED")

    def test_size_and_encoding_are_bounded(self):
        path = self.root/"artifact"
        path.write_bytes(b"12345")
        with patch.object(viper,"MAX_HASH_BYTES",4),patch.object(viper,"MAX_TEXT_BYTES",4):
            for kind, expected in (("file_sha256",hashlib.sha256(b"12345").hexdigest()),("file_contains","1")):
                self.assertEqual(viper.verify({"kind":kind,"target":str(path),"expected":expected})["status"],"UNVERIFIED")
        path.write_bytes(b"\xff")
        self.assertEqual(viper.verify({"kind":"file_contains","target":str(path),"expected":"x"})["status"],"UNVERIFIED")

    def test_observed_change_invalidates_read(self):
        path = self.root/"artifact"
        path.write_bytes(b"old")
        with self.assertRaises(ValueError):
            with viper.bounded_artifact(path,100) as (stream,_):
                self.assertEqual(stream.read(),b"old")
                path.write_bytes(b"changed")

    def test_invalid_expected_types_and_timeouts_fail_before_probe(self):
        with patch.object(viper.socket,"socket") as socket_factory:
            for port, timeout in ((True,1),(80,False),(80,11),(80,0),(80,float("nan"))):
                result = viper.verify({"kind":"tcp_listen","target":port,"timeoutSeconds":timeout})
                self.assertEqual(result["status"],"UNVERIFIED")
            socket_factory.assert_not_called()
        for value in (None,[],False,""):
            path = self.root/"artifact"
            path.write_bytes(b"sample")
            self.assertEqual(viper.verify({"kind":"file_contains","target":str(path),"expected":value})["status"],"UNVERIFIED")

    def test_http_observes_named_endpoint_not_redirect_destination(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                seen.append(self.path)
                if self.path=="/redirect":
                    self.send_response(302)
                    self.send_header("Location","/destination")
                elif self.path=="/missing":
                    self.send_response(404)
                else:
                    self.send_response(200)
                self.send_header("Content-Length","0")
                self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path, expected, status in (("/redirect",200,"CONTRADICTED"),("/redirect",302,"VERIFIED"),("/missing",404,"VERIFIED")):
                result = viper.verify({"kind":"http_status","target":base+path,"expected":expected})
                self.assertEqual(result["status"],status)
                self.assertFalse(result["observation"]["redirectFollowed"])
            self.assertNotIn("/destination",seen)
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=2)

    def test_http_transport_failure_is_unknown(self):
        with patch.object(viper.urllib.request,"build_opener") as opener:
            opener.return_value.open.side_effect=viper.urllib.error.URLError("fixture timeout")
            result=viper.verify({"kind":"http_status","target":"http://127.0.0.1:12345","expected":200})
            self.assertEqual(result["status"],"UNVERIFIED")
        with patch.object(viper.urllib.request,"build_opener") as opener:
            result=viper.verify({"kind":"http_status","target":"file:///fixture"})
            self.assertEqual(result["status"],"UNVERIFIED")
            opener.assert_not_called()

    def test_single_claim_does_not_overwrite_output(self):
        artifact=self.root/"artifact";artifact.touch()
        claim=self.root/"claim.json"
        claim.write_text(json.dumps({"kind":"file_exists","target":str(artifact)}),encoding="utf-8")
        before=claim.read_bytes()
        result=subprocess.run([sys.executable,str(ROOT/"viper.py"),"verify",str(claim),"--out",str(claim)],capture_output=True,timeout=8)
        self.assertEqual(result.returncode,2)
        self.assertEqual(claim.read_bytes(),before)


    def test_manifest_is_bounded_regular_and_strict_utf8(self):
        from viper_events import load_manifest
        manifest = self.root / "manifest.json"
        data = b'{"entry":{"kind":"file_exists","target":"fixture","expected":true}}'
        manifest.write_bytes(data)
        root, entries, digest = load_manifest(manifest)
        self.assertEqual(root,self.root.resolve())
        self.assertEqual(digest,hashlib.sha256(data).hexdigest())
        self.assertIn("entry",entries)
        with patch("viper_events.MAX_MANIFEST_BYTES",10):
            with self.assertRaises(ValueError):
                load_manifest(manifest)
        for invalid in (b'{"entry":NaN}',b'{"entry":1e999}',b'{"entry":"\\ud800"}',b'{"entry":1,"entry":2}',b'\xff'):
            manifest.write_bytes(invalid)
            with self.assertRaises(ValueError):
                load_manifest(manifest)
        with self.assertRaises(ValueError):
            load_manifest(self.root)

    def test_event_manifest_rejects_ambiguous_portable_paths(self):
        from viper_events import resolve_claim
        for target in ("../outside","CON.txt","NUL","COM1.txt","dir/AUX","name.","name ","a:b","a\\\\b","/absolute","a//b"):
            with self.subTest(target=target),self.assertRaises(ValueError):
                resolve_claim(self.root,{"kind":"file_exists","target":target,"expected":False})
        self.assertEqual(resolve_claim(self.root,{"kind":"file_exists","target":"absent.txt","expected":False})["target"],str(self.root/"absent.txt"))

    def test_disappearing_artifact_is_inconclusive(self):
        path = self.root / "artifact"
        path.write_bytes(b"sample")
        with patch.object(viper.os,"open",side_effect=FileNotFoundError("fixture disappearance")):
            result = viper.verify({"kind":"file_sha256","target":str(path),"expected":hashlib.sha256(b"sample").hexdigest()})
        self.assertEqual(result["status"],"UNVERIFIED")


if __name__=="__main__":
    unittest.main()
