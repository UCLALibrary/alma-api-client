import re
import requests
import xmltodict
from requests.structures import CaseInsensitiveDict
from typing import Any


class APIResponse:
    def __init__(self, response: requests.Response) -> None:
        self._response = response
        # This is pulled now from the property via self._response.
        data_format = self.content_type
        try:
            if data_format == "json":
                self.api_data: dict = response.json()
            else:
                # response.content probably will contain XML from Alma.
                # This might also be empty (b''), legitimately.
                self.api_data = {"content": response.content}
        except requests.exceptions.JSONDecodeError:
            # Some responses return nothing, which can't be decoded...
            self.api_data = {}

    @property
    def api_calls_remaining(self) -> int:
        # Data in response headers is a string; cast to int
        # so we can do math / comparisons.
        calls_remaining = self.headers.get("X-Exl-Api-Remaining", "0")
        try:
            return int(calls_remaining)
        except ValueError:
            return 0

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def content_type(self) -> str:
        # Header value looks like this:
        # application/json;charset=UTF-8
        ct_header = self.headers.get("Content-Type", "")
        match = re.search(r"application/([a-z].*);charset=UTF-8", ct_header)
        return match.group(1) if match else ""

    @property
    def headers(self) -> CaseInsensitiveDict:
        return self._response.headers

    @property
    def ok(self) -> bool:
        return self._response.ok

    @property
    def status_code(self) -> int:
        return self._response.status_code

    def json(self, **kwargs) -> Any:
        return self._response.json(**kwargs)

    def raise_for_status(self) -> None:
        self._response.raise_for_status()


class APIError(APIResponse, Exception):
    def __init__(self, response: requests.Response, message: str) -> None:
        super().__init__(response)
        self.message = message
        # If the APIResponse came from a MARC API request, the relevant data is in XML.
        # TODO: Consider moving AlmaMARCRecord._set_attributes() to APIResponse?
        if self.content_type == "xml":
            self._update_api_data_from_xml()

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.message}"

    def _update_api_data_from_xml(self):
        alma_xml = self.api_data.get("content", b"")
        response_data = xmltodict.parse(alma_xml)
        self.api_data = response_data.get("web_service_result", {})

    @property
    def error_messages(self) -> list[str]:
        # "errorList" is a dict... with one element called "error", which is a list
        # of dicts with "errorCode", "errorMessage", and "trackingId" keys.
        # Or... "error" can be a dict, instead of a list.
        # Example, with "error" as a list:
        # {
        #     "errorList": {
        #         "error": [
        #             {
        #                 "errorCode": "60107",
        #                 "errorMessage": "Set not found: Set ID abc",
        #                 "trackingId": "E01-2609185557-08VLC-AWAE718524417",
        #             }
        #         ]
        #     },
        #     "errorsExist": True,
        # }
        # or with "error" as a dict:
        # {
        #     "errorList": {
        #         "error": {
        #             "errorCode": "402203",
        #             "errorMessage": "Input parameters mmsId foobar is not valid.",
        #             "trackingId": "E01-2609232728-LDE0N-AWAE1797571547",
        #         }
        #     },
        #     "errorsExist": "true",
        # }
        #
        # It's not clear that the order of error codes or messages is meaningful.
        # We assume that "errorList" being a list implies some calls can return
        # multiple errors.
        # The codes don't seem useful.
        # TODO: Consider enhancement to return errorCode and trackingId with high debug level.

        errors = self.api_data.get("errorList", {}).get("error")
        if isinstance(errors, list):
            return [error_info.get("errorMessage", "") for error_info in errors]
        elif isinstance(errors, dict):
            return [errors.get("errorMessage", "")]
        else:
            return []
