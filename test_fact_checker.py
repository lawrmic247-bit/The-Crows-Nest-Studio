"""Regression checks: factual claims cannot be published without source-led review."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from fact_checker import (get_claims,mark_claim,report_markdown,require_clearance,
                          report_path, safe_url,save_report,status_summary,sync_report,source_tier)

class FactCheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.slug='first_ep'
        self.script='In 1942, the ship sailed into the Atlantic.\n\nA lookout scanned the sea. This is The Crow\'s Nest.'
    def tearDown(self):self.tmp.cleanup()

    def test_detects_claims_and_risk(self):
        rows=get_claims(self.script)
        self.assertEqual(len(rows),3)
        self.assertIn('date',rows[0]['flags'])
        self.assertEqual(rows[0]['priority'],'high')

    def test_without_report_blocks_publication(self):
        with self.assertRaisesRegex(ValueError,'report missing'):
            require_clearance(self.slug,self.script,self.root)

    def test_unresolved_blocks_publication(self):
        saved=sync_report(self.slug,'First Episode',self.script,self.root)
        save_report(saved,self.root)
        with self.assertRaisesRegex(ValueError,'unresolved'):
            require_clearance(self.slug,self.script,self.root)

    def test_source_is_required_for_supported(self):
        row=sync_report(self.slug,'First Episode',self.script,self.root)['claims'][0]
        with self.assertRaisesRegex(ValueError,'valid HTTPS'):
            mark_claim(row,status='supported',source_url='http://example.com',source_quote='A very good supporting excerpt',reviewer_confirmed=True)
        with self.assertRaisesRegex(ValueError,'specific supporting excerpt'):
            mark_claim(row,status='supported',source_url='https://www.history.navy.mil/',source_quote='short',reviewer_confirmed=True)
        with self.assertRaisesRegex(ValueError,'personally compared'):
            mark_claim(row,status='supported',source_url='https://www.history.navy.mil/',source_quote='The reported event did occur at sea.',reviewer_confirmed=False)

    def test_number_mismatch_cannot_be_marked_supported(self):
        row=sync_report(self.slug,'First Episode',self.script,self.root)['claims'][0]
        with self.assertRaisesRegex(ValueError,'dates/numbers'):
            mark_claim(row,status='supported',source_url='https://www.history.navy.mil/',
                       source_quote='A historical record from another era.',reviewer_confirmed=True)

    def test_exemption_requires_reason(self):
        row=sync_report(self.slug,'First Episode',self.script,self.root)['claims'][0]
        with self.assertRaises(ValueError):
            mark_claim(row,status='nonfactual',review_notes='okay',reviewer_confirmed=True)

    def test_cleared_sources_and_changed_claim_reopens(self):
        report=sync_report(self.slug,'First Episode',self.script,self.root)
        for row in report['claims']:
            mark_claim(row,status='supported',source_url='https://www.history.navy.mil/',
                       source_quote='A carefully reviewed primary source passage documenting the event of 1942 and an account of lookouts.',reviewer_confirmed=True)
        save_report(report,self.root)
        self.assertEqual(status_summary(report),(3,3,0))
        self.assertEqual(require_clearance(self.slug,self.script,self.root),report_path(self.slug,self.root))
        edited=self.script.replace('1942','1943')
        with self.assertRaisesRegex(ValueError,'unresolved'):
            require_clearance(self.slug,edited,self.root)
        scan=sync_report(self.slug,'First Episode',edited,self.root)
        self.assertEqual(status_summary(scan),(2,3,1))

    def test_insecure_urls_are_blocked(self):
        for value in ['file:///etc/passwd','https://127.0.0.1/a','https://localhost:443',
                      'http://www.navy.mil','https://192.168.1.4/','https://169.254.169.254/']:
            self.assertFalse(safe_url(value),value)
        self.assertTrue(safe_url('https://www.history.navy.mil/research'))

    def test_report_contains_traceable_source(self):
        report=sync_report(self.slug,'First Episode',self.script,self.root)
        mark_claim(report['claims'][0],status='supported',source_url='https://www.history.navy.mil/research',
                   source_quote='The historical record of 1942 provides direct evidence.',reviewer_confirmed=True)
        text=report_markdown(report)
        self.assertIn('history.navy.mil/research',text)
        self.assertIn('NOT CLEARED',text)

if __name__=='__main__':unittest.main()
