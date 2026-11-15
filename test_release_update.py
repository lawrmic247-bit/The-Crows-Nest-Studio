from __future__ import annotations
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import update_engine as update
import production_engine as production

class ReleaseTests(unittest.TestCase):
    def test_repo_and_no_downgrade(self):
        self.assertEqual(update.validate_repo('example/The-Crows-Nest-Studio'),'example/The-Crows-Nest-Studio')
        for s in ('https://github.com/example/repo','../repo','ex/../../bad','a b/repo'):
            with self.assertRaises(ValueError):update.validate_repo(s)
        self.assertIsNone(update.get_release('example/The-Crows-Nest-Studio',current_version='4.0.0',fetch=lambda _:{'tag_name':'v4.0.0'}))

    def test_release_archive_and_path_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'update.zip'
            with zipfile.ZipFile(path,'w') as z:
                for name in update.REQUIRED_CODE:
                    z.writestr(name,'4.0.1' if name=='VERSION' else 'pass\n')
            self.assertEqual(set(update.validate_archive(path,'4.0.1')),update.REQUIRED_CODE)
            with zipfile.ZipFile(path,'a') as z:z.writestr('../outside.py','bad')
            with self.assertRaises(ValueError):update.validate_archive(path,'4.0.1')

    def test_release_requires_digest(self):
        payload={'tag_name':'v4.0.1','assets':[{'name':'Crows_Nest_Studio_Update_v4.0.1.zip',
            'browser_download_url':'https://github.com/example/studio/releases/download/v4.0.1/Crows_Nest_Studio_Update_v4.0.1.zip',
            'size':150}]}
        with self.assertRaises(ValueError):update.get_release('example/studio','4.0.0',fetch=lambda _:payload)
        payload['assets'][0]['digest']='sha256:'+'f'*64
        found=update.get_release('example/studio','4.0.0',fetch=lambda _:payload)
        self.assertEqual(found.version,'4.0.1')

    def test_research_leads_not_claimed_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            path=production.make_research_leads('history of crow nests',Path(folder)/'leads.json')
            obj=json.loads(path.read_text())
            self.assertTrue(obj['leads'])
            self.assertTrue(all(lead['verified'] is False for lead in obj['leads']))
            self.assertTrue(all(lead['search_url'].startswith('https://') for lead in obj['leads']))

if __name__=='__main__':unittest.main()
