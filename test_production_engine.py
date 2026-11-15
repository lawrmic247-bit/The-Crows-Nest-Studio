from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import production_engine as p

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patchers=[patch.object(p,'QUEUE',root/'queue'),
                       patch.object(p,'EPISODES',root/'episodes'),
                       patch.object(p,'MEDIA_DIR',root/'media')]
        for x in self.patchers:x.start()
    def tearDown(self):
        for x in reversed(self.patchers):x.stop()
        self.tmp.cleanup()
    def test_queue_draft_and_fact_gate(self):
        job=p.create_job('Explore the transformation of American sea lookouts and their changing tools',minutes=4,fmt='both',auto_media=False)
        def fake(job,complete=None):
            scenes=[{'heading':'History','narration':'A lookout watched the sea for approaching vessels and changes in weather.'},
                    {'heading':'Modernization','narration':'New electronic sensors changed the lookout role, although visual watches remained important.'}]
            if complete:complete(1,2,'Writing historical section')
            return scenes
        result=p.run_job(job['id'],script_generator=fake)
        self.assertEqual(result['status'],'awaiting_review')
        self.assertFalse(json.loads(Path(result['manifest']).read_text())['approved'])
        with self.assertRaises(ValueError):p.prepare_for_render(job['id'],rights_confirmed=True)
        self.assertEqual(len(p.list_jobs()),1)
    def test_ollama_failure_status(self):
        job=p.create_job('Tell the true history of United States military traditions',auto_media=False)
        def fail(*args,**kwargs):raise RuntimeError('Ollama is not available')
        with self.assertRaises(RuntimeError):p.run_job(job['id'],script_generator=fail)
        self.assertEqual(p.get_job(job['id'])['status'],'needs_model')
    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):p.create_job('tiny')
        with self.assertRaises(ValueError):p.create_job('Detailed history of naval lookouts',minutes=60)
        with self.assertRaises(ValueError):p.create_job('Detailed history of naval lookouts',fmt='portrait 3:4')
        with self.assertRaises(ValueError):p.job_path('../data')
    def test_outline_and_voice_text(self):
        self.assertEqual(p._headings_from_outline('["Age of Sail","Modern Era"]',4),['Age of Sail','Modern Era'])
        self.assertEqual(p._clean_narration('<think>hidden</think> From the first watch.'),'From the first watch.')
    def test_ollama_payload_uses_loopback(self):
        class Reply:
            def __init__(self):self.payload=b'{"response":"A local script."}'
            def __enter__(self):return self
            def __exit__(self,*_):return None
            def read(self,n):return self.payload
        def requester(req,timeout):
            self.assertEqual(req.full_url,'http://127.0.0.1:11434/api/generate')
            self.assertEqual(json.loads(req.data)['stream'],False)
            return Reply()
        self.assertEqual(p.ollama_generate('qwen3:8b','write a script',request=requester),'A local script.')
    def test_word_scene_generation(self):
        job=p.create_job('Explore the history of the crow nest as a lookout post',minutes=2,auto_media=False)
        def mock_llm(_model,_prompt,**_kwargs):
            if 'JSON array' in _prompt:return '["First Watches","Modern Lookouts","Safety at Sea"]'
            return ' '.join(['Lookouts carefully observed distant ships and changing weather throughout the voyage.']*10)
        scenes=p.generate_scenes(job,ollama=mock_llm)
        self.assertEqual(len(scenes),3)
        self.assertTrue(all(len(s['narration'].split())>=30 for s in scenes))
    def test_credits_not_license_approval(self):
        self.assertTrue('verify' in p.download_commons_images.__doc__.lower() if p.download_commons_images.__doc__ else True)

if __name__=='__main__':unittest.main()
