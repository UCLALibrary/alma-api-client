import requests
from requests.structures import CaseInsensitiveDict
from typing import Any


class APIResponse:
    def __init__(self, response: requests.Response, data_format: str = "json") -> None:
        self._response = response
        try:
            if data_format == "json":
                self.api_data: dict = response.json()
            else:
                # response.content will contain XML from Alma.
                self.api_data = {"content": response.content}
        except requests.exceptions.JSONDecodeError:
            # Some responses return nothing, which can't be decoded...
            self.api_data = {}

    def __getattr__(self, attribute_name) -> Any:
        """
        Convenience method for response attributes not explicitly
        exposed via properties.

        :param attribute_name: The attribute name.
        :return: The attribute value from the response object, if found.
        :raises: `AttributeErrror`, if `response.attribute_name` not found.
        """
        try:
            return getattr(self._response, attribute_name)
        except AttributeError:
            raise AttributeError(f"{attribute_name} not found.")

    @property
    def api_calls_remaining(self) -> str:
        return self.headers.get("X-Exl-Api-Remaining", "")

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def headers(self) -> CaseInsensitiveDict:
        return self._response.headers

    @property
    def status_code(self) -> int:
        return self._response.status_code

    def json(self, **kwargs) -> Any:
        return self._response.json(**kwargs)

    def raise_for_status(self) -> None:
        self._response.raise_for_status()
