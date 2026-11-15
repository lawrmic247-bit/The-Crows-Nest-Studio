"""Offline Ollama setup tests: no hardware or Ollama installation required."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import production_engine as engine


class FakeReply:
    def __init__(self,payload):
        self.payload=payload
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def read(self,n=-1):
        return self.payload if n<0 else self.payload[:n]
    def __iter__(self):
        return iter(self.payload.splitlines(keepends=True))


class OllamaModelTests(unittest.TestCase):
    def test_discover_installed_models(self):
        def local(req,timeout):
            self.assertEqual(req.full_url,"http://127.0.0.1:11434/api/tags")
            return FakeReply(json.dumps({"models":[
                {"name":"llama3.2:3b"},
                {"name":"qwen3:4b"},
                {"name":"qwen3:4b"}]}).encode())
        self.assertEqual(engine.list_local_models(request=local),
                         ["llama3.2:3b","qwen3:4b"])

    def test_auto_selects_installed_instead_of_missing_eight_b(self):
        installed=["llama3.2:3b","qwen3:4b"]
        self.assertEqual(engine.select_local_model("qwen3:8b",installed=installed),
                         "qwen3:4b")
        self.assertEqual(engine.select_local_model("llama3.2:3b",installed=installed),
                         "llama3.2:3b")
        with self.assertRaisesRegex(engine.OllamaSetupError,"no text model"):
            engine.select_local_model("qwen3:8b",installed=[])

    def test_404_is_missing_model_not_server_offline(self):
        def no_model(req,timeout):
            raise urllib.error.HTTPError(req.full_url,404,"Not Found",{},
                io.BytesIO(b'{"error":"model qwen3:8b not found, try pulling it first"}'))
        with self.assertRaisesRegex(engine.OllamaSetupError,
                                     "cannot find text model qwen3:8b"):
            engine.ollama_generate("qwen3:8b","Write facts",request=no_model)

    def test_missing_running_server_is_actionable(self):
        def fail(req,timeout):
            raise urllib.error.URLError("connection refused")
        with self.assertRaisesRegex(engine.OllamaSetupError,"not running"):
            engine.list_local_models(request=fail)

    def test_explicit_download_stream(self):
        progress=[]
        def download(req,timeout):
            self.assertEqual(req.full_url,"http://127.0.0.1:11434/api/pull")
            self.assertEqual(json.loads(req.data)["name"],"qwen3:4b")
            return FakeReply(
                b'{"status":"pulling manifest"}\n'
                b'{"status":"downloading","completed":300,"total":1000}\n'
                b'{"status":"success"}\n')
        with patch.object(engine,"list_local_models",return_value=["qwen3:4b"]):
            self.assertEqual(engine.pull_local_model(
                "qwen3:4b",progress=progress.append,request=download),"qwen3:4b")
        self.assertTrue(any("30%" in p for p in progress))

    def test_model_preflight_happens_before_research(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            patches=[patch.object(engine,"QUEUE",root/"jobs"),
                     patch.object(engine,"EPISODES",root/"episodes"),
                     patch.object(engine,"MEDIA_DIR",root/"media")]
            for p in patches:p.start()
            try:
                job=engine.create_job(
                    "Research the history of naval corpsmen supporting the Marines",
                    auto_media=False,model="qwen3:8b")
                with patch.object(engine,"list_local_models",return_value=[]), \
                     patch.object(engine,"discover_research",
                                  side_effect=AssertionError("Research should not repeat")):
                    with self.assertRaises(engine.OllamaSetupError):
                        engine.run_job(job["id"])
                self.assertEqual(engine.get_job(job["id"])["status"],"needs_model")
            finally:
                for p in reversed(patches):p.stop()

    def test_retry_changes_missing_model_to_installed_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(engine,"QUEUE",root/"jobs"):
                job=engine.create_job(
                    "Document the history of Navy medicine and hospital corpsmen",
                    model="qwen3:8b",auto_media=False)
                model=engine.prepare_job_model(job["id"],installed=["qwen3:4b"])
                self.assertEqual(model,"qwen3:4b")
                self.assertEqual(engine.get_job(job["id"])["model"],"qwen3:4b")


if __name__=="__main__":
    unittest.main()
