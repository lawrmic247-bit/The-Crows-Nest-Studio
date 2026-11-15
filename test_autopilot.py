"""Offline tests for safe ChatGPT inbox, cinematic style and speech normalization."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration
import production_engine as engine


class NarratorTextTests(unittest.TestCase):
    def test_years_and_military_terms(self):
        self.assertEqual(narration.spoken_year(1967), 'nineteen sixty-seven')
        self.assertEqual(narration.spoken_year(1945), 'nineteen forty-five')
        self.assertEqual(narration.spoken_year(2004), 'two thousand four')
        self.assertEqual(narration.spoken_year(2018), 'twenty eighteen')
        self.assertEqual(narration.spoken_year(1960,True), 'nineteen sixties')
        self.assertEqual(narration.normalize_for_speech('May 16, 1968'),
                         'May sixteenth, nineteen sixty-eight')
        self.assertEqual(narration.normalize_for_speech('16 May 1968'),
                         'sixteenth May nineteen sixty-eight')
        self.assertEqual(narration.normalize_for_speech('5/16/1968'),
                         '5/16/1968')
        spoken=narration.normalize_for_speech(
            'In 1967, a Navy corpsman worked with the Marine Corps. '
            'Corpsmen served in Quảng Trị in the 1960s.')
        self.assertIn('nineteen sixty-seven',spoken)
        self.assertIn('core-man',spoken)
        self.assertIn('Marine Core',spoken)
        self.assertIn('core-men',spoken.lower())
        self.assertIn('Kwang Tree',spoken)
        self.assertIn('nineteen sixties',spoken)
        self.assertNotIn('nineteen hundred and sixty seven',spoken)

    def test_custom_foreign_name_pronunciation_is_editable_and_private(self):
        with tempfile.TemporaryDirectory() as folder:
            guide=Path(folder)/'pronunciations.json'
            guide.write_text(json.dumps({'Okinawa':'Oh-kee-nah-wah',
                                         'Nassau':'Nass-ow'}),encoding='utf-8')
            with patch.object(narration,'PRONUNCIATION_FILE',guide):
                self.assertEqual(narration.normalize_for_speech('Okinawa and Nassau'),
                                 'Oh-kee-nah-wah and Nass-ow')
            self.assertTrue(guide.is_file())


class ChatGPTInboxTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name)
        self.inbox=root/'inbox'
        self.inbox.mkdir()
        self.patches=[
          patch.object(engine,'QUEUE',root/'queue'),
          patch.object(engine,'EPISODES',root/'episodes'),
          patch.object(engine,'MEDIA_DIR',root/'media'),
        ]
        for p in self.patches:p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def test_import_is_private_and_does_not_auto_publish(self):
        path=self.inbox/'ballard.json'
        path.write_text(json.dumps({
            'schema':'crowsnest.job.v1',
            'topic':'Tell the accurate story of Navy corpsman Donald Ballard receiving the Medal of Honor',
            'title':'Donald Ballard, Medal of Honor',
            'minutes':10,
            'format':'wide',
            'visual_style':'motion',
            'voice':'kokoro:am_onyx',
            'auto_media':True,
            'research_notes':'Check the original Medal of Honor citation and archival imagery licenses.'
        }),encoding='utf-8')
        job=engine.import_chatgpt_job(path,source_folder=self.inbox)
        self.assertEqual(job['minutes'],10)
        self.assertEqual(job['visual_style'],'motion')
        self.assertEqual(job['status'],'queued')
        self.assertFalse(job.get('approved',False))
        self.assertEqual(len(engine.list_jobs()),1)
        self.assertEqual(job['id'],engine.import_chatgpt_job(path,source_folder=self.inbox)['id'])
        self.assertTrue(Path(job['notes_file']).is_file())

    def test_untrusted_job_rejected(self):
        path=self.inbox/'bad.json'
        path.write_text(json.dumps({
            'schema':'crowsnest.job.v1',
            'topic':'Tell a factual story about an old naval lookout over many decades',
            'command':'curl bad.example',
        }),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Unrecognized fields'):
            engine.import_chatgpt_job(path,source_folder=self.inbox)
        with self.assertRaisesRegex(ValueError,'inside'):
            engine.import_chatgpt_job(path,source_folder=Path(self.folder.name))


class MotionDocumentaryTests(unittest.TestCase):
    def test_archival_still_gets_motion_render_without_new_images(self):
        import wave
        from PIL import Image
        import studio
        with tempfile.TemporaryDirectory() as folder:
            parent=Path(folder)
            picture=parent/'archival_still.jpg'
            Image.new('RGB',(640,360),(30,52,70)).save(picture)
            wave_path=parent/'narration.wav'
            with wave.open(str(wave_path),'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b'\x00\x00'*24000)
            output=parent/'animated_photo.mp4'
            studio.mk_scene({},1,wave_path,1.0,picture,output,(320,180),10,'motion')
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size,1000)
            self.assertAlmostEqual(studio.probe_duration(output),1.0,delta=0.3)


if __name__=='__main__': unittest.main()
