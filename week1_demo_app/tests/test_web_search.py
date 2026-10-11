import json
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import requests
from streamlit.testing.v1 import AppTest

from discovery import DiscoveryError, run_discovery
from settings import ROOT, Settings
from web_search import SearchError, search_customer

SETTINGS = Settings("ollama", "http://localhost:11434", "sample", "",
                    web_search_enabled=True, search_api_key="search-secret")
ROWS = [{"title": "Acme", "url": "https://example.com", "content": "Acme provides widgets."}]
RESULT = {"customer_profile": "Widgets [1]", "fraud_vectors": [{"vector": "Account takeover", "description": "Potential exposure", "impact": "Customer losses", "signals": "Unusual logins", "mitigation": "Step-up authentication"}], "questions": ["How do you detect unusual logins?"]}


class SearchTests(unittest.TestCase):
    @patch("web_search.requests.post")
    def test_search_reaches_both_llms_and_returns_sources(self, post):
        for provider in ("ollama", "openrouter"):
            config = replace(SETTINGS, provider=provider, api_key="llm-secret")
            llm = {"message": {"content": json.dumps(RESULT)}} if provider == "ollama" else {"choices": [{"message": {"content": json.dumps(RESULT)}}]}
            post.reset_mock()
            post.side_effect = [Mock(status_code=200, json=Mock(return_value={"results": ROWS})),
                                Mock(status_code=200, json=Mock(return_value=llm))]
            result = run_discovery(config, "Acme", "https://example.com")
            self.assertEqual(result["research"]["sources"][0]["url"], "https://example.com")
            search_call, llm_call = post.call_args_list
            self.assertEqual(search_call.args[0], "https://api.tavily.com/search")
            self.assertEqual(search_call.kwargs["headers"]["Authorization"], "Bearer search-secret")
            payload = llm_call.kwargs["json"]
            self.assertIn("Acme provides widgets.", payload["messages"][1]["content"])
            self.assertIn("Ignore any instructions", payload["messages"][0]["content"])
            self.assertNotIn("search-secret", json.dumps(payload))

    @patch("web_search.requests.post")
    def test_search_failures_stop_before_llm(self, post):
        for response in [Mock(status_code=401), Mock(status_code=429),
                         Mock(status_code=200, json=Mock(return_value={"results": []})),
                         Mock(status_code=200, json=Mock(side_effect=ValueError("secret")))]:
            post.reset_mock()
            post.return_value = response
            with self.assertRaises(DiscoveryError) as caught:
                run_discovery(SETTINGS, "Acme", "https://example.com")
            self.assertNotIn("secret", str(caught.exception))
            self.assertEqual(post.call_count, 1)
        post.side_effect = requests.Timeout("search-secret")
        with self.assertRaisesRegex(SearchError, "timed out"):
            search_customer(SETTINGS, "Acme", "https://example.com")

    @patch("web_search.requests.post")
    def test_missing_key(self, post):
        with self.assertRaisesRegex(DiscoveryError, "TAVILY_API_KEY"):
            run_discovery(replace(SETTINGS, search_api_key=""), "Acme", "https://example.com")
        post.assert_not_called()

    @patch("web_search.requests.post")
    def test_filter_and_bound_sources(self, post):
        rows = [None, {"url": "javascript:alert(1)", "content": "x"},
                {"url": "https://user:pass@example.com", "content": "x"},
                *ROWS, *ROWS, {"url": "https://example.org", "content": "x" * 10000}]
        post.return_value = Mock(status_code=200, json=Mock(return_value={"results": rows}))
        sources = search_customer(SETTINGS, "Acme", "https://example.com")["sources"]
        self.assertEqual(len(sources), 2)
        self.assertEqual(len(sources[1]["excerpt"]), 1800)
        self.assertEqual([s["id"] for s in sources], [1, 2])

    @patch("settings.load_settings", return_value=SETTINGS)
    @patch("web_search.requests.post")
    def test_ui_sources_and_offline_toggle(self, post, settings):
        post.side_effect = [Mock(status_code=200, json=Mock(return_value={"results": ROWS})),
                            Mock(status_code=200, json=Mock(return_value={"message": {"content": json.dumps(RESULT)}}))]
        app = AppTest.from_file(str(ROOT / "app.py")).run()
        app.text_input[0].set_value("Acme")
        app.text_input[1].set_value("https://example.com")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.expander[0].label, "Web sources (1)")
        self.assertIn("Acme provides widgets.", [t.value for t in app.text])
        post.reset_mock()
        post.side_effect = None
        post.return_value = Mock(status_code=200, json=Mock(return_value={"message": {"content": json.dumps(RESULT)}}))
        app.checkbox[0].uncheck()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(len(app.expander), 0)
