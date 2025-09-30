from copy import deepcopy
import json
import sys
from unittest import TestCase
from requests import Response, HTTPError
from requests.structures import CaseInsensitiveDict

# Can't find a way to get tests to run within the dev environment
# without this hack.
sys.path.append("/home/app_user/project/src")
# Ignore pylance for this out-of-position import.
from alma_api_client.models.api import APIResponse  # noqa


class TestAPIResponse(TestCase):
    """Confirm response from API is converted to `APIResponse` correctly."""

    @classmethod
    def setUpClass(cls):
        data = {"foo": "bar"}
        response = Response()
        response.status_code = 200
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Exl-Api-Remaining": "12345",
        }
        response.headers = CaseInsensitiveDict(headers)
        response._content = json.dumps(data).encode()
        cls.sample_response = response

    def test_api_calls_remaining(self):
        api_response = APIResponse(self.sample_response)
        self.assertEqual(api_response.api_calls_remaining, 12345)

    def test_api_data_json(self):
        api_response = APIResponse(self.sample_response)
        api_data = api_response.api_data
        self.assertEqual(api_data.get("foo", ""), "bar")
        self.assertEqual(len(api_data), 1)

    def test_api_data_xml(self):
        # Change the default JSON content type to XML.
        xml_response = deepcopy(self.sample_response)
        xml_response.headers["Content-Type"] = "application/xml;charset=UTF-8"
        api_response = APIResponse(xml_response)
        api_data = api_response.api_data
        # "XML" data in this contrived case is bytes with the original JSON as string.
        # MARC tests show proper XML.
        self.assertEqual(api_data.get("content", b""), b'{"foo": "bar"}')
        self.assertEqual(len(api_data), 1)

    def test_content_type(self):
        api_response = APIResponse(self.sample_response)
        self.assertEqual(api_response.content_type, "json")

    def test_non_ok_status_raises_error(self):
        # Change the default 200 status code to an error condition.
        invalid_response = deepcopy(self.sample_response)
        invalid_response.status_code = 500
        api_response = APIResponse(invalid_response)
        with self.assertRaises(HTTPError):
            api_response.raise_for_status()

    def test_status_code(self):
        api_response = APIResponse(self.sample_response)
        self.assertEqual(api_response.status_code, 200)
