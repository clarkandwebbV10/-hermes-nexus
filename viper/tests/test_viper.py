import hashlib,socket,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import viper

class ViperTests(unittest.TestCase):
    def test_file_exists_verified(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.txt"; p.write_text("hello")
            self.assertEqual(viper.verify({"kind":"file_exists","target":str(p),"expected":True})["status"],"VERIFIED")

    def test_missing_file_contradicted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"missing.txt"
            self.assertEqual(viper.verify({"kind":"file_exists","target":str(p),"expected":True})["status"],"CONTRADICTED")

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.txt"; p.write_bytes(b"abc")
            expected=hashlib.sha256(b"abc").hexdigest()
            self.assertEqual(viper.verify({"kind":"file_sha256","target":str(p),"expected":expected})["status"],"VERIFIED")

    def test_file_contains_verified(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.txt"; p.write_text("deployment-state=ready\n",encoding="utf-8")
            self.assertEqual(viper.verify({"kind":"file_contains","target":str(p),"expected":"deployment-state=ready"})["status"],"VERIFIED")

    def test_tcp_listen_verified(self):
        s=socket.socket()
        s.bind(("127.0.0.1",0))
        s.listen(1)
        try:
            port=s.getsockname()[1]
            self.assertEqual(viper.verify({"kind":"tcp_listen","target":port,"host":"127.0.0.1","expected":True})["status"],"VERIFIED")
        finally:
            s.close()

    def test_unsupported(self):
        self.assertEqual(viper.verify({"kind":"unknown","target":"x"})["status"],"UNVERIFIED")

if __name__=="__main__":
    unittest.main()
