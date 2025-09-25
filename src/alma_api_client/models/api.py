import re
import requests
from requests.structures import CaseInsensitiveDict
from typing import Any


class APIResponse:
    def __init__(self, response: requests.Response) -> None:
        self._response = response
        data_format = self.content_type
        try:
            if data_format == "json":
                self.api_data: dict = response.json()
            else:
                # response.content will contain XML from Alma.
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
