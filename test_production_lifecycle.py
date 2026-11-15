"""Non-destructive production lifecycle and queue-cleanup regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import production_engine as engine


class ProductionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        p=patch.object(engine,'QUEUE',self.root/'production_queue')
        p.start()
        self.addCleanup(p.stop)

    def make(self,topic='Documented naval historical service in the Pacific'):
        return engine.create_job(topic,minutes=10,fmt='wide',auto_media=False)

    def test_ready_draft_leaves_queue_and_goes_to_review_then_library(self):
        job=self.make()
        self.assertEqual(engine.project_stage(job),'queue')
        self.assertEqual([j['id'] for j in engine.list_stage_jobs('queue')],[job['id']])
        changed=engine.change(job['id'],status='awaiting_review',manifest='story.json')
        self.assertEqual(engine.project_stage(changed),'review')
        self.assertEqual(engine.list_stage_jobs('queue'),[])
        self.assertEqual(len(engine.list_stage_jobs('review')),1)
        archived=engine.archive_job(job['id'])
        self.assertTrue(archived['archived'])
        self.assertEqual(archived['status'],'awaiting_review')
        self.assertEqual(engine.list_stage_jobs('review'),[])
        self.assertEqual(len(engine.list_stage_jobs('archive')),1)
        restored=engine.restore_job(job['id'])
        self.assertFalse(restored['archived'])
        self.assertEqual(engine.project_stage(restored),'review')
        engine.change(job['id'],status='finished')
        self.assertEqual(len(engine.list_stage_jobs('archive')),1)

    def test_delete_only_queue_tracking_and_preserve_episode_files(self):
        job=self.make()
        episode=self.root/'episode.json'
        episode.write_text('{"script":"Saved documentary"}',encoding='utf-8')
        engine.change(job['id'],manifest=str(episode),status='awaiting_review')
        engine.remove_queue_job(job['id'])
        self.assertEqual(engine.list_jobs(),[])
        self.assertTrue(engine.get_job(job['id'])['removed'])
        self.assertEqual(json.loads(episode.read_text())['script'],'Saved documentary')
        self.assertEqual(len(engine.list_jobs(include_removed=True)),1)

    def test_actively_running_jobs_cannot_be_deleted_or_archived(self):
        job=self.make()
        for status in ('researching','drafting','gathering_media','rendering'):
            engine.change(job['id'],status=status)
            with self.assertRaisesRegex(ValueError,'still processing'):
                engine.remove_queue_job(job['id'])
            with self.assertRaisesRegex(ValueError,'actively processing'):
                engine.archive_job(job['id'])
            self.assertFalse(engine.get_job(job['id']).get('removed',False))

    def test_clear_waiting_and_completed_only(self):
        a=self.make('The history of the US Navy corpsman')
        b=self.make('Naval medical service in the Vietnam War')
        c=self.make('Documentary footage of the Cold War Navy')
        d=self.make('The history of maritime convoy rescue operations')
        engine.change(b['id'],status='failed')
        engine.change(c['id'],status='awaiting_review')
        engine.change(d['id'],status='finished')
        self.assertEqual(engine.clear_pending_queue(),2)
        self.assertEqual({j['id'] for j in engine.list_jobs()},{c['id'],d['id']})
        self.assertEqual(len(engine.list_stage_jobs('review')),1)
        self.assertEqual(engine.clear_completed_from_queue(),1)
        self.assertEqual([j['id'] for j in engine.list_jobs()],[c['id']])
        self.assertEqual(len(engine.list_jobs(include_removed=True)),4)

    def test_deleted_sync_inbox_job_is_not_reimported(self):
        inbox=self.root/'private_inbox'
        inbox.mkdir()
        source=inbox/'history.json'
        source.write_text(json.dumps({
            'schema':'crowsnest.job.v1',
            'topic':'The historic contributions of Navy hospital corpsmen',
            'minutes':10,
            'format':'wide',
        }),encoding='utf-8')
        job=engine.import_chatgpt_job(source,source_folder=inbox)
        self.assertEqual(len(engine.list_jobs()),1)
        engine.remove_queue_job(job['id'])
        self.assertEqual(len(engine.list_jobs()),0)
        again=engine.import_chatgpt_job(source,source_folder=inbox)
        self.assertEqual(again['id'],job['id'])
        self.assertTrue(again['removed'])
        self.assertEqual(len(engine.list_jobs()),0)

    def test_clear_old_review_backlog_moves_drafts_to_library(self):
        a=self.make('Historical Navy hospital corpsman documentary review')
        b=self.make('Navy heritage and maritime ceremonies')
        for job in (a,b):
            engine.change(job['id'],status='awaiting_review')
        self.assertEqual(len(engine.list_stage_jobs('review')),2)
        self.assertEqual(engine.move_ready_drafts_to_library(),2)
        self.assertEqual(engine.list_stage_jobs('review'),[])
        self.assertEqual(len(engine.list_stage_jobs('archive')),2)
        self.assertFalse(any(j.get('removed') for j in engine.list_jobs()))

    def test_explicitly_selected_writing_model_never_falls_back(self):
        job=self.make()
        engine.change(job['id'],model='qwen3:4b',model_locked=True)
        with self.assertRaisesRegex(engine.OllamaSetupError,'no longer installed'):
            engine.prepare_job_model(job['id'],installed=['other:small'])
        self.assertEqual(engine.get_job(job['id'])['model'],'qwen3:4b')
        self.assertEqual(engine.prepare_job_model(
            job['id'],installed=['qwen3:4b']),'qwen3:4b')

    def test_stage_name_rejects_unknown_filter(self):
        with self.assertRaisesRegex(ValueError,'Unknown'):
            engine.list_stage_jobs('not-a-valid-stage')


if __name__=='__main__':
    unittest.main()
