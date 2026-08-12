from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.ai import openai_client


class OpenAIClientTests(SimpleTestCase):
    @override_settings(
        OPENAI_API_KEY='test-key',
        OPENAI_TIMEOUT_SECONDS=17,
        OPENAI_MAX_RETRIES=0,
    )
    @patch('openai.OpenAI')
    def test_client_has_bounded_request_settings(self, client_class):
        openai_client()

        client_class.assert_called_once_with(
            api_key='test-key',
            timeout=17,
            max_retries=0,
        )
