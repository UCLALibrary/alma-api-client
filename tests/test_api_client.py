from unittest import TestCase
from unittest.mock import patch
import requests
import sys

# Can't find a way to get tests to run within the dev environment
# without this hack.
sys.path.append("/home/app_user/project/src")
# Ignore pylance for these out-of-position imports.
from alma_api_client.clients.alma_api_client import AlmaAPIClient  # noqa
from alma_api_client.models.api import APIError  # noqa


class TestAPIClient(TestCase):
    def test_call_api_ssl_error(self):
        client = AlmaAPIClient(api_key="dummy")
        with patch(
            "requests.request", side_effect=requests.exceptions.SSLError("SSL fail")
        ):
            # Confirm that an APIError is raised with the expected message.
            with self.assertRaises(APIError) as context:
                client._call_api("GET", "/dummy-endpoint")
            self.assertIn("SSL Error calling Alma API", str(context.exception))
            self.assertIn("SSL fail", str(context.exception))
