"""Tests for automatic public-source discovery and review before video generation."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import production_engine as engine


class FakeResponse:
    def __init__(self, payload):
        self.payload=json.dumps(payload).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,limit=-1):return self.payload[:limit] if limit>0 else self.payload


class ResearchDiscoveryTests(unittest.TestCase):
    def fetch(self,request,timeout=12):
        address=request.full_url
        if address.startswith("https://en.wikipedia.org/w/rest.php/"):
            return FakeResponse({"pages":[
                {"title":"Donald E. Ballard","key":"Donald_E._Ballard",
                 "excerpt":"<span>Navy hospital corpsman</span> Medal of Honor recipient"},
                {"title":"Unrelated Poetry","key":"Unrelated_Poetry",
                 "excerpt":"Unrelated work"},
            ]})
        if address.startswith("https://www.loc.gov/search/"):
            return FakeResponse({"results":[
                {"title":"Donald Ballard papers","id":"https://www.loc.gov/item/1234/",
                 "description":["Veteran oral history catalog metadata"]},
                {"title":"Other Persons","id":"https://www.loc.gov/item/890/",
                 "description":["Unrelated archive"]}
            ]})
        raise AssertionError("Unexpected external research endpoint "+address)

    def test_two_sources_have_real_urls_and_are_never_automatically_verified(self):
        result=engine.discover_research(
            "Create a documentary about Donald E Ballard Medal of Honor",
            fetch=self.fetch)
        self.assertEqual(len(result["sources"]),2)
        self.assertEqual({r["publisher"] for r in result["sources"]},
                         {"Wikipedia","Library of Congress"})
        self.assertTrue(all(x["url"].startswith("https://") and x["verified"] is False
                            for x in result["sources"]))
        self.assertNotIn("Unrelated",str(result))
        brief=engine.research_brief(result)
        self.assertIn("https://en.wikipedia.org/wiki/Donald_E._Ballard",brief)
        self.assertIn("https://www.loc.gov/item/1234/",brief)
        self.assertIn("UNVERIFIED",brief)

    def test_missing_internet_creates_warning_without_fabricating_references(self):
        def offline(request,timeout=12):
            raise OSError("No connection available")
        result=engine.discover_research("The origins of Navy peacoat",fetch=offline)
        self.assertEqual(result["sources"],[])
        self.assertEqual(len(result["warnings"]),2)
        brief=engine.research_brief(result)
        self.assertIn("No external sources returned",brief)
        self.assertNotIn("http://",brief)

    def test_unexpected_external_host_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unexpected research service"):
            engine._research_json("https://example.org/private?token=test",fetch=self.fetch)

    def test_retrieved_records_saved_as_leads_and_not_fact_check_approvals(self):
        result=engine.discover_research(
            "Donald E Ballard Medal of Honor",fetch=self.fetch)
        with tempfile.TemporaryDirectory() as folder:
            lead_path=Path(folder)/"research_leads.json"
            saved=engine.make_research_leads("Donald Ballard",lead_path,result)
            data=json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(len(data["retrieved_sources"]),2)
            self.assertFalse(any(x["verified"] for x in data["retrieved_sources"]))
            self.assertGreater(len(data["leads"]),0)

    def test_source_discovery_does_not_generate_video(self):
        import inspect
        source=inspect.getsource(engine.run_job)
        self.assertNotIn("_local_reenactments(",source)
        self.assertIn("discover_research(",source)
        # The fact-review gate lives in the renderer before local AI generation.
        import studio
        render_source=inspect.getsource(studio.render)
        self.assertLess(render_source.index("fact_path=require_clearance("),
                        render_source.index("_local_reenactments("))


if __name__=="__main__":
    unittest.main()
