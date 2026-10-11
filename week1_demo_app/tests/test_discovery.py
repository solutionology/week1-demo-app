import json
import os
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import requests
from streamlit.testing.v1 import AppTest

from discovery import DiscoveryError, OUTPUT_SCHEMA, parse_result, provider_error, run_discovery, validate_inputs
from settings import ROOT, Settings, load_settings
from presentation import fraud_table, question_list

RESULT = {"customer_profile": "A sample profile", "fraud_vectors": [{"vector": "Account takeover", "description": "Potential exposure", "impact": "Customer losses", "signals": "Unusual logins", "mitigation": "Step-up authentication"}], "questions": ["How do you detect unusual logins?"]}
SETTINGS = Settings("ollama", "http://localhost:11434", "sample", "", "Analyze", "Discover {customer_name} at {website_url}")


class DiscoveryTests(unittest.TestCase):
    def test_ollama_runtime_error_detail_is_redacted(self):
        response = Mock(status_code=500, json=Mock(return_value={
            "error": "model requires more system memory; test-secret Bearer another-secret"
        }))
        message = provider_error(response, replace(SETTINGS, api_key="test-secret"))
        self.assertIn("model requires more system memory", message)
        self.assertNotIn("test-secret", message)
        self.assertNotIn("another-secret", message)

    def test_non_json_error_uses_safe_fallback(self):
        response = Mock(status_code=500, json=Mock(side_effect=ValueError("HTML")))
        self.assertIn("restart Ollama", provider_error(response, SETTINGS))

    def test_input_validation(self):
        self.assertEqual(validate_inputs(" Acme ", " https://example.com "), ("Acme", "https://example.com"))
        for name, url in [("", "https://example.com"), ("A", "example.com"), ("A", "javascript:alert(1)"), ("A", "https://user:pass@example.com")]:
            with self.assertRaises(DiscoveryError):
                validate_inputs(name, url)

    def test_response_contract(self):
        self.assertEqual(parse_result("```json\n" + json.dumps(RESULT) + "\n```"), RESULT)
        for content in ["bad json", "[]", '{"customer_profile":"x"}', '{"customer_profile":{},"fraud_vectors":"x"}']:
            with self.assertRaises(DiscoveryError):
                parse_result(content)

    def test_invalid_table_and_questions_are_rejected(self):
        for changes in ({"fraud_vectors": "Old prose"}, {"fraud_vectors": [{}]},
                        {"questions": []}, {"questions": [42]},
                        {"fraud_vectors": [{**RESULT["fraud_vectors"][0], "signals": ""}]}):
            with self.assertRaises(DiscoveryError):
                parse_result(json.dumps({**RESULT, **changes}))

    def test_generated_html_escapes_model_content(self):
        row = {**RESULT["fraud_vectors"][0], "vector": "<script>alert(1)</script>"}
        table = fraud_table([row])
        self.assertIn("<table", table)
        self.assertNotIn("<script>", table)
        self.assertIn("&lt;script&gt;", table)
        self.assertIn("&lt;img", question_list(['<img src=x onerror=alert(1)>']))

    @patch("discovery.requests.post")
    def test_both_provider_payloads(self, post):
        for provider in ["ollama", "openrouter"]:
            config = replace(SETTINGS, provider=provider, api_key="test-key")
            body = {"message": {"content": json.dumps(RESULT)}} if provider == "ollama" else {"choices": [{"message": {"content": json.dumps(RESULT)}}]}
            post.return_value = Mock(status_code=200, json=Mock(return_value=body))
            self.assertEqual(run_discovery(config, "Acme", "https://example.com"), RESULT)
            args, kwargs = post.call_args
            self.assertTrue(args[0].endswith("/api/chat" if provider == "ollama" else "/chat/completions"))
            self.assertIn("format" if provider == "ollama" else "response_format", kwargs["json"])
            self.assertIn("Acme", kwargs["json"]["messages"][1]["content"])
            self.assertFalse(kwargs["allow_redirects"])

    @patch("discovery.requests.post")
    def test_format_repair_for_both_providers(self, post):
        for provider in ("ollama", "openrouter"):
            def response(content):
                message = {"content": content}
                body = {"message": message} if provider == "ollama" else {"choices": [{"message": message}]}
                return Mock(status_code=200, json=Mock(return_value=body))
            post.reset_mock()
            post.side_effect = [response('{"customer_profile":"Profile", "fraud_vectors":"Old prose"}'),
                                response(json.dumps(RESULT))]
            config = replace(SETTINGS, provider=provider, api_key="test-key")
            self.assertEqual(run_discovery(config, "Acme", "https://example.com"), RESULT)
            self.assertEqual(post.call_count, 2)
            first = post.call_args_list[0].kwargs["json"]
            if provider == "ollama":
                self.assertEqual(first["format"], OUTPUT_SCHEMA)
            self.assertEqual(len(first["messages"]), 2)
            self.assertEqual(len(post.call_args.kwargs["json"]["messages"]), 4)

    @patch("discovery.requests.post")
    def test_format_repair_is_bounded(self, post):
        post.return_value = Mock(status_code=200, json=Mock(return_value={"message": {"content": "invalid"}}))
        with self.assertRaisesRegex(DiscoveryError, "one automatic repair"):
            run_discovery(SETTINGS, "Acme", "https://example.com")
        self.assertEqual(post.call_count, 2)

    @patch("discovery.requests.post")
    def test_errors_are_safe(self, post):
        post.return_value = Mock(status_code=401, text="secret-value")
        with self.assertRaisesRegex(DiscoveryError, "API key"):
            run_discovery(SETTINGS, "Acme", "https://example.com")
        self.assertEqual(post.call_count, 1)
        post.side_effect = requests.Timeout("secret-value")
        with self.assertRaisesRegex(DiscoveryError, "timed out"):
            run_discovery(SETTINGS, "Acme", "https://example.com")

    @patch("discovery.requests.post")
    def test_missing_credentials_do_not_call_provider(self, post):
        with self.assertRaises(DiscoveryError):
            run_discovery(replace(SETTINGS, provider="openrouter"), "Acme", "https://example.com")
        post.assert_not_called()

    @patch("settings.dotenv_values", return_value={"LOCAL": "true", "OLLAMA_MODEL": "file-model"})
    def test_environment_precedence(self, dotenv):
        with patch.dict(os.environ, {"LOCAL": "false", "OPENROUTER_MODEL": "env-model"}, clear=True):
            settings = load_settings()
        self.assertEqual((settings.provider, settings.model), ("openrouter", "env-model"))

    @patch("settings.load_settings", return_value=SETTINGS)
    @patch("discovery.requests.post")
    def test_ui_success_and_failure(self, post, settings):
        post.return_value = Mock(status_code=200, json=Mock(return_value={"message": {"content": json.dumps(RESULT)}}))
        app = AppTest.from_file(str(ROOT / "app.py")).run()
        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.tabs], ["Customer Profile", "Fraud Vectors", "Product Positioning", "Similar Customers"])
        app.text_input[0].set_value("Acme")
        app.text_input[1].set_value("https://example.com")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("A sample profile", [item.value for item in app.markdown])
        self.assertTrue(any("<table" in item.value and "Account takeover" in item.value for item in app.markdown))
        self.assertIn("Questions for the customer", [item.value for item in app.subheader])
        self.assertTrue(any("discovery-questions" in item.value and "How do you detect" in item.value for item in app.markdown))
        post.return_value = Mock(status_code=429)
        app.button[0].click().run()
        self.assertTrue(app.error)
        self.assertNotIn("A sample profile", [item.value for item in app.markdown])


if __name__ == "__main__":
    unittest.main()
