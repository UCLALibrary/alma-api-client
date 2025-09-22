import requests
from time import sleep
from typing import Union, TypeAlias

# TODO: Once 3.13 is supported, update this.
# from warnings import deprecated # Python 3.13+
from typing_extensions import deprecated  # Python 3.11
from .models.api import APIResponse
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

        return APIResponse(response, data_format=data_format)

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

    @deprecated("Will be removed when deprecated MARC get methods are removed.")
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

    @deprecated("Will be removed when deprecated MARC update methods are removed.")
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

    def create_item(
        self, bib_id: str, holding_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        return api_response

    def get_items(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_integration_profiles(self, parameters: dict | None = None) -> APIResponse:
        # Caller can pass search parameters, but must deal with possible
        # multiple matches.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/conf/integration-profiles"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_jobs(self, parameters: dict | None = None) -> APIResponse:
        # Caller normally will pass parameters, but they're not required.
        # Caller must deal with possible multiple matches.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/conf/jobs"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def run_job(
        self, job_id, data: dict | None = None, parameters: dict | None = None
    ) -> APIResponse:
        # Tells Alma to queue / run a job; does *not* wait for completion.
        # Caller must provide job_id outside of parameters.
        # Running a scheduled job requires empty data {}; not sure about other jobs
        if data is None:
            data = {}
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/jobs/{job_id}"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        return api_response

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
            # TODO: Replace this with _call_api()
            instance = self._call_get_api(api)
            status = instance["status"]["value"]
            print(status)
            sleep(seconds_to_poll)
        return instance

    def get_fees(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}/fees"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_analytics_report(self, parameters: dict | None = None) -> APIResponse:
        # Docs say to URL-encode report name (path);
        # request lib is doing it automatically.
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/analytics/reports"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_analytics_path(
        self, path: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/analytics/paths/{path}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_vendors(self, parameters: dict | None = None) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/acq/vendors"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_vendor(
        self, vendor_code: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/vendors/{vendor_code}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

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

    def get_set_members(
        self, set_id: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/sets/{set_id}/members"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def create_user(self, data: dict, parameters: dict | None = None) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/users"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        return api_response

    def delete_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        return api_response

    def get_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def update_user(
        self, user_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        return api_response

    def get_general_configuration(self) -> APIResponse:
        """Return general configuration info.
        Useful for checking production / sandbox via environment_type.
        """
        api = "/almaws/v1/conf/general"
        api_response = self._call_api(method="get", api=api)
        return api_response

    def get_code_tables(self) -> APIResponse:
        """Return list of code tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/code-tables"
        api_response = self._call_api(method="get", api=api)
        return api_response

    def get_code_table(
        self, code_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return specific code table, via name from get_code_tables()."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/code-tables/{code_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_mapping_tables(self) -> APIResponse:
        """Return list of mapping tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/mapping-tables"
        api_response = self._call_api(method="get", api=api)
        return api_response

    def get_mapping_table(
        self, mapping_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return specific mapping table, via name from get_mapping_tables()."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/code-tables/{mapping_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_libraries(self) -> APIResponse:
        """Return all libraries."""
        api = "/almaws/v1/conf/libraries"
        api_response = self._call_api(method="get", api=api)
        return api_response

    def get_library(self, library_code: str) -> APIResponse:
        """Return data for a single library, via code.
        Doesn't provide more details than each entry in get_libaries().
        """
        api = f"/almaws/v1/conf/libraries/{library_code}"
        api_response = self._call_api(method="get", api=api)
        return api_response

    def get_circulation_desks(
        self, library_code: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return data about circ desks in a single library, via code."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/conf/libraries/{library_code}/circ-desks/"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_funds(self, parameters: dict | None = None) -> APIResponse:
        """Return data about all funds matching search in parameters."""
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/acq/funds"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def get_fund(self, fund_id: str, parameters: dict | None = None) -> APIResponse:
        """Return data about a specific fund."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        return api_response

    def update_fund(
        self, fund_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        """Update a specific fund."""
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        return api_response

    def get_set(self, set_id: str, get_all_members: bool = True) -> Set:
        """Retrieve data for a specific set.

        :param set_id: The Alma id for the set.
        :param get_all_members: Fetch all set members.
        :return alma_set: An alma_api_client.models.Set object.
        """
        api = f"/almaws/v1/conf/sets/{set_id}"
        api_response = self._call_api(method="get", api=api)
        alma_set = Set(api_response=api_response)

        members = []
        if get_all_members:
            # Get all member references and add them to the Set.
            offset = 0
            limit = 100
            while len(members) < alma_set.number_of_members:
                api_response = self._call_api(
                    method="get",
                    api=alma_set.members_api,
                    parameters={"offset": offset, "limit": limit},
                )
                new_members = api_response.api_data.get("member", [])
                offset += len(new_members)
                for new_member in new_members:
                    members.append(SetMember(member_data=new_member))

        alma_set.add_members(members)
        return alma_set

    def _retrieve_all(self):
        # TODO: Is it practical to generalize API iteration to fetch all whatevers?
        pass

    def _get_marc_record(
        self,
        api: str,
        parameters: dict | None = None,
    ) -> APIResponse:
        api_response = self._call_api(
            method="get", api=api, parameters=parameters, data_format="xml"
        )
        api_response.raise_for_status()
        return api_response

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
    ) -> BibRecord:
        if parameters is None:
            parameters = {}
        api = "/almaws/v1/bibs"
        data = bib_record.alma_xml
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters, data_format="xml"
        )
        return BibRecord(api_response)

    def update_bib_record(
        self, bib_id: str, bib_record: BibRecord, parameters: dict | None = None
    ) -> BibRecord:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}"
        data = bib_record.alma_xml
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters, data_format="xml"
        )
        return BibRecord(api_response)

    def delete_bib_record(
        self, bib_id: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        return api_response

    def create_holding_record(
        self, bib_id: str, holding_record: HoldingRecord, parameters: dict | None = None
    ) -> HoldingRecord:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings"
        data = holding_record.alma_xml
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters, data_format="xml"
        )
        return HoldingRecord(api_response)

    def update_holding_record(
        self,
        bib_id: str,
        holding_record: HoldingRecord,
        parameters: dict | None = None,
    ) -> HoldingRecord:
        if parameters is None:
            parameters = {}
        holding_id = holding_record.holding_id
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        data = holding_record.alma_xml
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters, data_format="xml"
        )
        return HoldingRecord(api_response)

    def delete_holding_record(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> APIResponse:
        if parameters is None:
            parameters = {}
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        return api_response
