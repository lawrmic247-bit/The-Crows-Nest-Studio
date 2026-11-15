"""Offline regression tests: no AI model downloads required."""
import os,subprocess,tempfile,unittest,wave
from pathlib import Path

class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        os.environ['LOCALAPPDATA']=self.temp.name
        import voice_profiles as vp
        self.vp=vp
        vp.APPDATA=Path(self.temp.name)/'data'
        vp.PROFILE_DIR=vp.APPDATA/'voice_profiles'
        self.reference=Path(self.temp.name)/'my voice.wav'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                        'sine=frequency=220:duration=4','-ar','48000',str(self.reference)],check=True)

    def tearDown(self):self.temp.cleanup()

    def test_consent_and_original_preserved(self):
        with self.assertRaises(PermissionError):
            self.vp.create_profile('Me',self.reference,transcript='hello',consent=False)
        before=self.reference.read_bytes()
        p=self.vp.create_profile('My Natural Voice',self.reference,transcript='hello',consent=True)
        self.assertEqual(self.vp.get_audio(p['profile_id'],'original').read_bytes(),before)
        out=self.vp.clean_recording(p['profile_id'],'light')
        self.assertTrue(out.is_file())
        with wave.open(str(out)) as f:self.assertGreater(f.getnframes(),48000)
        self.assertEqual(self.vp.get_audio(p['profile_id'],'original').read_bytes(),before)
        self.assertEqual(self.vp.get_profile(p['profile_id'])['cleanup_strength'],'light')

    def test_multiple_voices_and_notes(self):
        a=self.vp.create_profile('My Natural Voice',self.reference,transcript='exact text',consent=True)
        b=self.vp.create_profile('My History Voice',self.reference,transcript='historic text',consent=True)
        self.assertNotEqual(a['profile_id'],b['profile_id'])
        self.assertEqual(len(self.vp.list_profiles()),2)
        changed=self.vp.update_profile(a['profile_id'],name='Everyday',transcript='hello world',direction='Quiet and thoughtful')
        self.assertEqual(changed['transcript'],'hello world')
        self.assertEqual(changed['direction'],'Quiet and thoughtful')

    def test_qwen_stub(self):
        p=self.vp.create_profile('Authorized',self.reference,transcript='hello',consent=True)
        import qwen_voice
        qwen_voice.get_profile=self.vp.get_profile
        qwen_voice.get_audio=self.vp.get_audio
        class FakeModel:
            def generate_voice_clone(self,**kwargs):
                import numpy as np
                self.kwargs=kwargs
                return [np.zeros(24000,dtype='float32')],24000
        model=FakeModel();target=Path(self.temp.name)/'clone.wav'
        qwen_voice.clone(p['profile_id'],'Greetings, sailors.',target,model=model)
        self.assertTrue(target.exists())
        self.assertEqual(model.kwargs['ref_text'],'hello')
        self.assertEqual(model.kwargs['text'],'Greetings, sailors.')

if __name__ == '__main__':unittest.main()
