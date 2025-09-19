import requests
from requests.structures import CaseInsensitiveDict
from time import sleep
from typing import Any, Union, TypeAlias

# TODO: Once 3.13 is supported, update this.
# from warnings import deprecated # Python 3.13+
from typing_extensions import deprecated  # Python 3.11

from .models.sets import Set, SetMember
from .models.marc_records import (
    AuthorityRecord,
    BibRecord,
    HoldingRecord,
)


# For requests data parameter, which is very flexible;
# (optional) Dictionary, list of tuples, bytes, or file-like object to send...
# this is better than Any.
# TODO: Once 3.13 is supported, update this:
# type Data = Union[bytes, dict, list[tuple]] # Python 3.12+
Data: TypeAlias = Union[bytes, dict, list[tuple]]  # Python 3.11


class APIResponse:
    def __init__(self, response: requests.Response, data_format: str = "json") -> None:
        self._response = response
        try:
            if data_format == "json":
                self.api_data: dict = response.json()
            else:
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


class AlmaAPIClient:
    def __init__(self, api_key: str) -> None:
        self.API_KEY = api_key
        self.BASE_URL = "https://api-na.hosted.exlibrisgroup.com"

    def _get_headers(self, data_format: str = "json") -> dict:
        """Generate the HTTP headers needed for all API requests, to be sure responses
        are in the requested data_format.

        :param data_format: The desired format, expected to be json or xml.
        :return: The relevant HTTP headers.
        """
        # TODO: Enforce valid formats.
        return {
            "Authorization": f"apikey {self.API_KEY}",
            "Accept": f"application/{data_format}",
            "Content-Type": f"application/{data_format}",
        }

    def _get_api_data(
        self, response: requests.Response, data_format: str = "json"
    ) -> dict:
        """Return dictionary with response content and selected response headers.

        If data_format is not json, the (presumably) XML content is in api_data["content"],
        as a byte array.

        :param response: An HTTP response returned by the API.
        :param data_format: The desired format, expected to be json or xml.
        :return api_data: Response content and selected headers.
        """
        # TODO: Enforce valid formats.
        try:
            if data_format == "json":
                api_data: dict = response.json()
            else:
                api_data = {"content": response.content}
        except requests.exceptions.JSONDecodeError:
            # Some responses return nothing, which can't be decoded...
            api_data = {}
        # Add a few response elements caller can use
        api_data["api_response"] = {
            "headers": response.headers,
            "status_code": response.status_code,
            "request_url": response.url,
        }
        return api_data

    def _call_api(
        self,
        method: str,
        api: str,
        data: Data | None = None,
        parameters: dict | None = None,
        data_format: str = "json",
    ) -> APIResponse:
        if method not in ["delete", "get", "post", "put"]:
            raise ValueError(f"Unsupported method: {method}")

        # requests.request takes optional data and json parameters,
        # but only one should be supplied.  Figure that out here, instead
        # of having two full calls varying only in one parameter.
        if data_format == "json":
            data_params = {"json": data}
        elif data_format == "xml":
            data_params = {"data": data}
        else:
            raise ValueError(f"Unsupported format: {data_format}")

        api_url = self._get_api_url(api)
        headers = self._get_headers(data_format)
        if parameters is None:
            parameters = {}

        # pylance does not like **data_params, since requests.request()
        # does not take **kwargs.
        response = requests.request(
            method=method,
            url=api_url,
            headers=headers,
            params=parameters,
            **data_params,  # type: ignore
        )

        return APIResponse(response)

    def _call_get_api_TMP(
        self, api: str, parameters: dict | None = None, data_format: str = "json"
    ) -> APIResponse:
        return self._call_api(
            method="get", api=api, parameters=parameters, data_format=data_format
        )

    def _get_api_url(self, api: str) -> str:
        """Get the full URL needed to call the API.  The base URL is aadded,
        if the provided `api` does not already start with it.

        :param api: The API, either as a full URL or the `/almaws/...` path.
        :return url: The full URL for the API.
        """
        if api.startswith(self.BASE_URL):
            return api
        else:
            return self.BASE_URL + api

    def _call_get_api(
        self, api: str, parameters: dict | None = None, data_format: str = "json"
    ) -> dict:
        """Send a GET request to the API.

        :param api: The API to call, with or without the base URL.
        :param parameters: The optional request parameters.
        :param data_format: The desired format, expected to be json or xml.
        :return api_data: Response content and selected headers.
        """
        if parameters is None:
            parameters = {}
        api_url = self._get_api_url(api)
        headers = self._get_headers(data_format)
        response = requests.get(api_url, headers=headers, params=parameters)
        api_data: dict = self._get_api_data(response, data_format)
        return api_data

    def _call_post_api(
        self,
        api: str,
        data: Data,
        parameters: dict | None = None,
        data_format: str = "json",
    ) -> dict:
        """Send a POST request to the API.

        :param api: The API to call, with or without the base URL.
        :param data: The data to send in the body of the request.
        :param parameters: The optional request parameters.
        :param data_format: The desired format, expected to be json or xml.
        :return api_data: Response content and selected headers.
        """
        if parameters is None:
            parameters = {}
        api_url = self._get_api_url(api)
        headers = self._get_headers(data_format)
        # Handle both XML (required by MARC methods) and default JSON.
        # TODO: Enforce valid formats.
        if data_format == "xml":
            response = requests.post(
                api_url, headers=headers, data=data, params=parameters
            )
        else:
            response = requests.post(
                api_url, headers=headers, json=data, params=parameters
            )
        api_data: dict = self._get_api_data(response, data_format)
        return api_data

    def _call_put_api(
        self,
        api: str,
        data: Data,
        parameters: dict | None = None,
        data_format: str = "json",
    ) -> dict:
        """Send a PUT request to the API.

        :param api: The API to call, with or without the base URL.
        :param data: The data to send in the body of the request.
        :param parameters: The optional request parameters.
        :param data_format: The desired format, expected to be json or xml.
        :return api_data: Response content and selected headers.
        """
        if parameters is None:
            parameters = {}
        headers = self._get_headers(data_format)
        api_url = self._get_api_url(api)
        # Handle both XML (required by update_bib) and default JSON
        # TODO: Enforce valid formats.
        if data_format == "xml":
            response = requests.put(
                api_url, headers=headers, data=data, params=parameters
            )
        else:
            # json default
            response = requests.put(
                api_url, headers=headers, json=data, params=parameters
            )
        api_data: dict = self._get_api_data(response, data_format)
        return api_data

    def _call_delete_api(
        self, api: str, parameters: dict | None = None, data_format: str = "json"
    ) -> dict:
        """Send a DELETE request to the API.

        :param api: The API to call, with or without the base URL.
        :param parameters: The optional request parameters.
        :param data_format: The desired format, expected to be json or xml.
        :return api_data: Response content and selected headers.
        """
        if parameters is None:
            parameters = {}
        api_url = self._get_api_url(api)
        headers = self._get_headers(data_format)
        response = requests.delete(api_url, headers=headers, params=parameters)
        # Success is HTTP 204, "No Content"
        if response.status_code != 204:
            # TODO: Real error handling
            print(api_url)
            print(response.status_code)
            print(response.headers)
            print(response.text)
            # exit(1)
        api_data: dict = self._get_api_data(response, data_format)
        return api_data

    def create_item(
        self, bib_id: str, holding_id: str, data: dict, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        return self._call_post_api(api, data, parameters)

    def get_items(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        return self._call_get_api(api, parameters)

    def get_integration_profiles(self, parameters: dict | None = None) -> dict:
        # Caller can pass search parameters, but must deal with possible
        # multiple matches.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/conf/integration-profiles"
        return self._call_get_api(api, parameters)

    def get_jobs(self, parameters: dict | None = None) -> dict:
        # Caller normally will pass parameters, but they're not required.
        # Caller must deal with possible multiple matches.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/conf/jobs"
        return self._call_get_api(api, parameters)

    def run_job(
        self, job_id, data: dict | None = None, parameters: dict | None = None
    ) -> dict:
        # Tells Alma to queue / run a job; does *not* wait for completion.
        # Caller must provide job_id outside of parameters.
        # Running a scheduled job requires empty data {}; not sure about other jobs
        if data is None:
            data = {}
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/jobs/{job_id}"
        return self._call_post_api(api, data, parameters)

    def wait_for_completion(
        self, job_id: str, instance_id: str, seconds_to_poll: int = 15
    ) -> dict:
        # Running a job just queues it to run; Alma assigns an instance id.
        # This method allows the caller to wait until the given instance of
        # the job has completed.
        api = f"/almaws/v1/conf/jobs/{job_id}/instances/{instance_id}"

        # Initialize instance, to keep type-checker happy.
        instance = {}
        # progress value (0-100) can't be used as it remains 0 if FAILED.
        # Use status instead; values from
        # https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_job_instance.xsd/
        status = "NONE"  # Fake value until API is called.
        while status in [
            "NONE",
            "QUEUED",
            "PENDING",
            "INITIALIZING",
            "RUNNING",
            "FINALIZING",
        ]:
            instance = self._call_get_api(api)
            status = instance["status"]["value"]
            print(status)
            sleep(seconds_to_poll)
        return instance

    def get_fees(self, user_id: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}/fees"
        return self._call_get_api(api, parameters)

    def get_analytics_report(self, parameters: dict | None = None) -> dict:
        # Docs say to URL-encode report name (path);
        # request lib is doing it automatically.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/analytics/reports"
        return self._call_get_api(api, parameters)

    def get_analytics_path(self, path: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/analytics/paths/{path}"
        return self._call_get_api(api, parameters)

    def get_vendors(self, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/acq/vendors"
        return self._call_get_api(api, parameters)

    def get_vendor(self, vendor_code: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/vendors/{vendor_code}"
        return self._call_get_api(api, parameters)

    @deprecated("Use get_bib_record() instead.")
    def get_bib(self, mms_id: str, parameters: dict | None = None) -> dict:
        """Return dictionary response, with Alma bib record (in Alma XML format),
        in "content" element.
        """
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{mms_id}"
        return self._call_get_api(api, parameters, data_format="xml")

    @deprecated("Use update_bib_record() instead.")
    def update_bib(
        self, mms_id: str, data: bytes, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{mms_id}"
        return self._call_put_api(api, data, parameters, data_format="xml")

    @deprecated("Use get_holding_record() instead")
    def get_holding(
        self, mms_id: str, holding_id: str, parameters: dict | None = None
    ) -> dict:
        """Return dictionary response, with Alma holding record (in Alma XML format),
        in "content" element.
        """
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{mms_id}/holdings/{holding_id}"
        return self._call_get_api(api, parameters, data_format="xml")

    @deprecated("Use get_holding_record() instead.")
    def update_holding(
        self, mms_id: str, holding_id: str, data: bytes, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{mms_id}/holdings/{holding_id}"
        return self._call_put_api(api, data, data_format="xml")

    def get_set_members(self, set_id: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/sets/{set_id}/members"
        return self._call_get_api(api, parameters)

    def create_user(self, user: dict, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/users"
        return self._call_post_api(api, user, parameters)

    def delete_user(self, user_id: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        return self._call_delete_api(api, parameters)

    def get_user(self, user_id: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        return self._call_get_api(api, parameters)

    def update_user(
        self, user_id: str, user: dict, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        return self._call_put_api(api, user, parameters)

    def get_general_configuration(self) -> dict:
        """Return general configuration info.
        Useful for checking production / sandbox via environment_type.
        """
        api = "/almaws/v1/conf/general"
        return self._call_get_api(api)

    def get_code_tables(self) -> dict:
        """Return list of code tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/code-tables"
        return self._call_get_api(api)

    def get_code_table(self, code_table: str, parameters: dict | None = None) -> dict:
        """Return specific code table, via name from get_code_tables()."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/code-tables/{code_table}"
        return self._call_get_api(api, parameters)

    def get_mapping_tables(self) -> dict:
        """Return list of mapping tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/mapping-tables"
        return self._call_get_api(api)

    def get_mapping_table(
        self, mapping_table: str, parameters: dict | None = None
    ) -> dict:
        """Return specific mapping table, via name from get_mapping_tables()."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/code-tables/{mapping_table}"
        return self._call_get_api(api, parameters)

    def get_libraries(self) -> dict:
        """Return all libraries."""
        api = "/almaws/v1/conf/libraries"
        return self._call_get_api(api)

    def get_library(self, library_code: str) -> dict:
        """Return data for a single library, via code.
        Doesn't provide more details than each entry in get_libaries().
        """
        api = f"/almaws/v1/conf/libraries/{library_code}"
        return self._call_get_api(api)

    def get_circulation_desks(
        self, library_code: str, parameters: dict | None = None
    ) -> dict:
        """Return data about circ desks in a single library, via code."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/libraries/{library_code}/circ-desks/"
        return self._call_get_api(api, parameters)

    def get_funds(self, parameters: dict | None = None) -> dict:
        """Return data about all funds matching search in parameters."""
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/acq/funds"
        return self._call_get_api(api, parameters)

    def get_fund(self, fund_id: str, parameters: dict | None = None) -> dict:
        """Return data about a specific fund."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/funds/{fund_id}"
        return self._call_get_api(api, parameters)

    def update_fund(
        self, fund_id: str, fund: dict, parameters: dict | None = None
    ) -> dict:
        """Update a specific fund."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/funds/{fund_id}"
        return self._call_put_api(api, fund, parameters)

    # New / experimental code below.
    def get_set(self, set_id: str, get_all_members: bool = True) -> Set:
        """Retrieve data for a specific set.

        :param set_id: The Alma id for the set.
        :param get_all_members: Fetch all set members.
        :return alma_set: An alma_api_client.models.Set object.
        """
        api = f"/almaws/v1/conf/sets/{set_id}"
        api_response = self._call_get_api(api)
        alma_set = Set(api_response=api_response)

        members = []
        if get_all_members:
            # Get all member references and add them to the Set.
            offset = 0
            limit = 100
            while len(members) < alma_set.number_of_members:
                data = self._call_get_api(
                    api=alma_set.members_api,
                    parameters={"offset": offset, "limit": limit},
                )
                new_members = data.get("member", [])
                offset += len(new_members)
                for new_member in new_members:
                    members.append(SetMember(api_response=new_member))

        alma_set.add_members(members)
        return alma_set

    def _retrieve_all(self):
        # TODO: Is it practical to generalize API iteration to fetch all whatevers?
        pass

    def _get_marc_record(
        self,
        api: str,
        parameters: dict | None = None,
    ) -> dict:
        if parameters is None:
            parameters = {}
        api_data = self._call_get_api(api, parameters, data_format="xml")
        # TODO: Change _get_api_data() to return an object which exposes attributes
        # in a more friendly way. This could involve parsing XML for error messages & codes,
        # as well as response status.
        # Will require updating all client methods.
        # For now, this is isolated to the new record retrieval methods.
        if api_data.get("api_response", {}).get("status_code", "") != 200:
            raise ValueError(f"Unable to get MARC record for {api}")
        else:
            return api_data

    def get_authority_record(
        self, authority_id: str, parameters: dict | None = None
    ) -> AuthorityRecord:
        """Retrieve authority record from Alma, as an `AuthorityRecord`.

        :param authority_id: The Alma authority record id.
        :param parameters: Other parameters, see Alma documentation for details.
        :raises: `ValueError`, if Alma cannot find a record matching the id.
        :return: The record.
        """
        api = f"/almaws/v1/bibs/authorities/{authority_id}"
        api_response = self._get_marc_record(api, parameters)
        return AuthorityRecord(api_response)

    def get_bib_record(self, bib_id: str, parameters: dict | None = None) -> BibRecord:
        """Retrieve bibliographic record from Alma, as a `BibRecord`.

        :param bib_id: The Alma bib record id.
        :param parameters: Other parameters, see Alma documentation for details.
        :raises: `ValueError`, if Alma cannot find a record matching the id.
        :return: The record.
        """
        api = f"/almaws/v1/bibs/{bib_id}"
        api_response = self._get_marc_record(api, parameters)
        return BibRecord(api_response)

    def get_holding_record(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> HoldingRecord:
        """Retrieve holding record from Alma, as an `HoldingRecord`.

        :param bib_id: The Alma bib record id.
        :param holding_id: The Alma holding record id.
        :param parameters: Other parameters, see Alma documentation for details.
        :raises: `ValueError`, if Alma cannot find a record matching the id.
        :return: The record.
        """
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        api_response = self._get_marc_record(api, parameters)
        # TODO: Consider adding bib_id to holding record, which does not get it
        # from API response.
        return HoldingRecord(api_response)

    def create_bib_record(
        self, bib_record: BibRecord, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/bibs"
        data = bib_record.alma_xml
        # TODO: Return the actual record created.
        return self._call_post_api(api, data, parameters, data_format="xml")

    def update_bib_record(
        self, bib_id: str, bib_record: BibRecord, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}"
        data = bib_record.alma_xml
        # TODO: Return the actual record updated.
        return self._call_put_api(api, data, parameters, data_format="xml")

    def delete_bib_record(self, bib_id: str, parameters: dict | None = None) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}"
        return self._call_delete_api(api, parameters)

    def create_holding_record(
        self, bib_id: str, holding_record: HoldingRecord, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings"
        data = holding_record.alma_xml
        # TODO: Return the actual record created.
        return self._call_post_api(api, data, parameters, data_format="xml")

    def update_holding_record(
        self,
        bib_id: str,
        holding_record: HoldingRecord,
        parameters: dict | None = None,
    ) -> dict:
        if parameters is None:
            parameters = {}
        holding_id = holding_record.holding_id
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        data = holding_record.alma_xml
        # TODO: Return the actual record updated.
        return self._call_put_api(api, data, data_format="xml")

    def delete_holding_record(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> dict:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        return self._call_delete_api(api, parameters)
