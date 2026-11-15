"""Regression tests for one-story/three-format export and optional local video."""
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import studio as local_video
import production_engine as engine
from production_engine import distill_story,available_outputs


class ShortFormTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        p=patch.object(engine,"EPISODES",self.root/"episodes")
        p.start();self.addCleanup(p.stop)
        self.scenes=[
          {"heading":"Early years","narration":"The young Navy corpsman joined the Marines in Vietnam in 1967. "
               "He learned their names and took responsibility for their wounds. "},
          {"heading":"The ambush","narration":"During an ambush he heard a warning about a grenade. "
               "He moved toward the wounded and risked his life to protect them. "
               "The grenade failed to detonate as he shielded the other Marines."},
          {"heading":"Aftermath","narration":"The wounded Marines were moved toward safety. "
               "His devotion to duty was recognized with the Medal of Honor. "
               "Years later, he continued speaking about service and sacrifice."}
        ]
    def test_choices_and_source_verbatim(self):
        self.assertEqual(available_outputs(["full","shorts","tiktok"]),["full","shorts","tiktok"])
        for kind in ("shorts","tiktok"):
            short=distill_story(self.scenes,kind)
            self.assertTrue(short)
            self.assertIn("Hook",short[0]["heading"])
            all_words=" ".join(row["narration"] for row in self.scenes)
            for row in short:
                for sentence in row["narration"].split("."):
                    if sentence.strip():
                        self.assertIn(sentence.strip(),all_words)
            self.assertLessEqual(sum(len(r["narration"].split()) for r in short),165)
        with self.assertRaises(ValueError):
            available_outputs(["shorts","shorts"])
        with self.assertRaises(ValueError):
            available_outputs(["video-pirate"])

    def test_three_separate_review_gates(self):
        job={"id":"a1b2c3d4e5f6","title":"The Navy Corpsman","voice":"kokoro:am_onyx",
             "visual_style":"motion","deliverables":["full","shorts","tiktok"]}
        manifest={"slug":"navy_doc_test","title":"The Navy Corpsman","scenes":self.scenes,
                  "approved":False,"sources":[],"media_sources":[]}
        engine.atomic_json(engine.EPISODES/"navy_doc_test.json",manifest)
        with patch("fact_checker.sync_report") as sync,patch("fact_checker.save_report"):
            sync.return_value={"claims":[]}
            outputs=engine.create_story_companions(job,manifest)
        self.assertEqual(set(outputs),{"full","shorts","tiktok"})
        for label,path in outputs.items():
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertFalse(data["approved"])
            if label!="full":
                self.assertEqual(data["deliverable"],label)
                self.assertTrue(data["slug"].endswith("_"+label))
                self.assertTrue(data["scenes"])

    def test_punchy_local_rewrite_and_no_invented_year(self):
        from production_engine import social_story
        original=self.scenes*5
        words=("The corpsman heard the grenade warning and immediately moved to protect "
               "wounded Marines under enemy fire. ")
        middle=("The battle took place in Vietnam, and his medical duty remained "
                "to keep wounded service members alive as combat continued. ")
        ending=("He continued serving the wounded and was recognized for his "
                "courage and devotion to duty. ")
        generated="\n\n".join([words*3,middle*3,ending*3])
        rewritten=social_story(original,"tiktok",rewrite=lambda prompt,target:generated)
        self.assertEqual(len(rewritten),3)
        self.assertIn("grenade",rewritten[0]["narration"])
        self.assertIn("Payoff",rewritten[-1]["heading"])
        ungrounded=generated+" In 9999 he returned."
        safe=social_story(original,"tiktok",rewrite=lambda prompt,target:ungrounded)
        self.assertNotIn("9999",str(safe))

    def test_each_variant_requires_its_own_review(self):
        with patch.object(engine,"QUEUE",self.root/"queue"):
            job=engine.create_job(
                "Remember the documented heroism of a Navy corpsman in Vietnam",
                fmt="both",auto_media=False)
            main={"slug":"independent_reviews","title":"Review Example",
                  "scenes":self.scenes,"approved":False,"sources":[],"media_sources":[]}
            engine.atomic_json(engine.EPISODES/"independent_reviews.json",main)
            with patch("fact_checker.sync_report") as sync,patch("fact_checker.save_report"):
                sync.return_value={"claims":[]}
                variants=engine.create_story_companions(job,main)
            engine.change(job["id"],status="awaiting_review",
                          variants=variants,manifest=variants["full"])
            with self.assertRaises(ValueError):
                engine.prepare_for_render(job["id"],deliverable="shorts",
                                          rights_confirmed=False)
            with patch("fact_checker.require_clearance",return_value=Path(self.root/"evidence")):
                approved=engine.prepare_for_render(
                    job["id"],deliverable="shorts",rights_confirmed=True)
            self.assertTrue(json.loads(approved.read_text())["approved"])
            self.assertFalse(json.loads(Path(variants["full"]).read_text())["approved"])
            self.assertFalse(json.loads(Path(variants["tiktok"]).read_text())["approved"])

    def test_verified_updater_supports_local_video_modules(self):
        import update_engine
        self.assertTrue(update_engine.is_allowed("production_engine.py"))
        self.assertTrue(update_engine.is_allowed("studio.py"))
        self.assertFalse(update_engine.is_allowed("private_voice_recording.wav"))

    def test_default_both_compat(self):
        with patch.object(engine,"QUEUE",self.root/"queue"):
            job=engine.create_job(
                "The documented service of a Navy corpsman during the Vietnam War",
                fmt="both",auto_media=False)
        self.assertEqual(job["deliverables"],["full","shorts","tiktok"])


class ComfyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"wan_api.json"
        self.path.write_text(json.dumps({
            "10":{"class_type":"CLIPTextEncode",
                  "inputs":{"text":"__CROWS_PROMPT__"}},
            "11":{"class_type":"SaveVideo",
                  "inputs":{"filename_prefix":"CrowsNest","video":["12",0]}}
        }),encoding="utf-8")
    def test_safe_local_workflow(self):
        original=local_video.load_workflow(self.path)
        changed=local_video.prepare_workflow(original,
                "A clearly labeled historical illustration of a naval lookout on a ship")
        self.assertIn("clearly labeled",changed["10"]["inputs"]["text"])
        self.assertEqual(original["10"]["inputs"]["text"],"__CROWS_PROMPT__")
        self.assertEqual(changed["11"]["inputs"]["filename_prefix"],"CrowsNest")
        with self.assertRaises(local_video.LocalVideoError):
            local_video.prepare_workflow(original,"short")
        with self.assertRaises(local_video.LocalVideoError):
            local_video._request("http://other-host:8123/prompt")
    def test_export_must_be_api_json_with_placeholder(self):
        self.path.write_text(json.dumps({"nodes":[{"type":"SaveImage"}]}))
        with self.assertRaises(local_video.LocalVideoError):
            local_video.load_workflow(self.path)
    def test_reenactment_shot_has_explicit_screen_disclosure(self):
        import studio,wave
        from PIL import Image
        pic=Path(self.temp.name)/"still.jpg"
        Image.new("RGB",(640,360),(28,52,66)).save(pic)
        audio=Path(self.temp.name)/"audio.wav"
        with wave.open(str(audio),"wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(24000)
            f.writeframes(b"\x00\x00"*24000)
        result=Path(self.temp.name)/"AI_demo.mp4"
        studio.mk_scene({"visual_provenance":"AI-generated illustration"},1,
                        audio,1.0,pic,result,(320,180),10,"archival")
        self.assertTrue(result.exists())
        self.assertGreater(result.stat().st_size,1000)

    def test_mock_local_render_receives_video_file(self):
        video=b"\x00\x00\x00\x18ftypmp42"+b"x"*1500
        pid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        class Response:
            def __init__(self,payload): self.payload=payload
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,n):return self.payload[:n]
        called=[]
        def fake(req,timeout=12):
            url=req.full_url
            called.append(url)
            if url.endswith("/prompt"):
                return Response(json.dumps({"prompt_id":pid}).encode())
            if url.endswith("/history/"+pid):
                return Response(json.dumps({pid:{"status":{"completed":True},
                    "outputs":{"11":{"videos":[{"filename":"test.mp4","subfolder":"","type":"output"}]}}}}).encode())
            if "/view?" in url:return Response(video)
            raise AssertionError(url)
        output=local_video.generate_clip(
            "Historical illustrative ship in stormy seas, no fictional markings",
            self.path,Path(self.temp.name)/"clip.mp4",urlopen=fake,poll_interval=0,
            deadline_seconds=5)
        self.assertEqual(output.read_bytes(),video)
        self.assertTrue(all(url.startswith(local_video.BASE) for url in called))
    def test_connection_without_server_explains_missing_setup(self):
        def fail(req,timeout=12):
            raise OSError("server not listening")
        with self.assertRaisesRegex(local_video.LocalVideoError,"ComfyUI is not running"):
            local_video.status(urlopen=fail)


if __name__=="__main__":
    unittest.main()
