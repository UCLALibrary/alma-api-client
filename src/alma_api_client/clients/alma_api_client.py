import requests
from time import sleep
from typing import Union, TypeAlias

from alma_api_client.models.api import APIResponse, APIError
from alma_api_client.models.sets import Set, SetMember
from alma_api_client.models.marc_records import (
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

    def _call_api(
        self,
        method: str,
        api: str,
        data: Data | None = None,
        parameters: dict | None = None,
        data_format: str = "json",
    ) -> requests.Response:
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
        # request requires an empty dictionary, if params is passed but not populated.
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

        return response

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

    def create_item(
        self, bib_id: str, holding_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error creating item.")

    def get_items(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving item.")

    def get_integration_profiles(self, parameters: dict | None = None) -> APIResponse:
        # Caller can pass search parameters, but must deal with possible
        # multiple matches.
        api = "/almaws/v1/conf/integration-profiles"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving integration profiles.")

    def get_jobs(self, parameters: dict | None = None) -> APIResponse:
        # Caller normally will pass parameters, but they're not required.
        # Caller must deal with possible multiple matches.
        api = "/almaws/v1/conf/jobs"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving jobs.")

    def run_job(
        self, job_id, data: dict | None = None, parameters: dict | None = None
    ) -> APIResponse:
        # Tells Alma to queue / run a job; does *not* wait for completion.
        # Caller must provide job_id outside of parameters.
        # Running a scheduled job requires empty data {}; not sure about other jobs
        if data is None:
            data = {}
        api = f"/almaws/v1/conf/jobs/{job_id}"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error running job.")

    def wait_for_completion(
        self, job_id: str, instance_id: str, seconds_to_poll: int = 15
    ) -> APIResponse:
        # Running a job just queues it to run; Alma assigns an instance id.
        # This method allows the caller to wait until the given instance of
        # the job has completed.
        api = f"/almaws/v1/conf/jobs/{job_id}/instances/{instance_id}"
        api_response = self._call_api(method="get", api=api)
        # progress value (0-100) can't be used as it remains 0 if FAILED.
        # Use status instead; values from
        # https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_job_instance.xsd/
        # TODO: Improve this, with error handling.
        response_obj = APIResponse(api_response)
        status = response_obj.api_data.get("status", {}).get("value", "")

        # There are other values, but these indicate the job is still running (or at least,
        # not yet done).
        while status in [
            "QUEUED",
            "PENDING",
            "INITIALIZING",
            "RUNNING",
            "FINALIZING",
        ]:
            response_obj = APIResponse(api_response)
            status = response_obj.api_data.get("status", {}).get("value", "")
            print(status)
            sleep(seconds_to_poll)
        # Return the whole final response, for the caller to use as desired.
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error completing job.")

    def get_fees(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        api = f"/almaws/v1/users/{user_id}/fees"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving fees.")

    def get_analytics_report(self, parameters: dict | None = None) -> APIResponse:
        # Docs say to URL-encode report name (path);
        # request lib is doing it automatically.
        api = "/almaws/v1/analytics/reports"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving analytics report.")

    def get_analytics_path(
        self, path: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/analytics/paths/{path}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving analytics path.")

    def get_vendors(self, parameters: dict | None = None) -> APIResponse:
        api = "/almaws/v1/acq/vendors"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving vendors.")

    def get_vendor(
        self, vendor_code: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/acq/vendors/{vendor_code}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving vendor.")

    def get_set_members(
        self, set_id: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/conf/sets/{set_id}/members"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving set members.")

    def create_user(self, data: dict, parameters: dict | None = None) -> APIResponse:
        api = "/almaws/v1/users"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error creating user.")

    def delete_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting user.")

    def get_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving user.")

    def update_user(
        self, user_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error updating user.")

    def get_general_configuration(self) -> APIResponse:
        """Return general configuration info.
        Useful for checking production / sandbox via environment_type.
        """
        api = "/almaws/v1/conf/general"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving general configuration.")

    def get_code_tables(self) -> APIResponse:
        """Return list of code tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/code-tables"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving code tables.")

    def get_code_table(
        self, code_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return specific code table, via name from get_code_tables()."""
        api = f"/almaws/v1/conf/code-tables/{code_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving code table.")

    def get_mapping_tables(self) -> APIResponse:
        """Return list of mapping tables.  This specific API is undocumented."""
        api = "/almaws/v1/conf/mapping-tables"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving mapping tables.")

    def get_mapping_table(
        self, mapping_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return specific mapping table, via name from get_mapping_tables()."""
        api = f"/almaws/v1/conf/code-tables/{mapping_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving mapping table.")

    def get_libraries(self) -> APIResponse:
        """Return all libraries."""
        api = "/almaws/v1/conf/libraries"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving libraries.")

    def get_library(self, library_code: str) -> APIResponse:
        """Return data for a single library, via code.
        Doesn't provide more details than each entry in get_libaries().
        """
        api = f"/almaws/v1/conf/libraries/{library_code}"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving library.")

    def get_circulation_desks(
        self, library_code: str, parameters: dict | None = None
    ) -> APIResponse:
        """Return data about circ desks in a single library, via code."""
        api = f"/almaws/v1/conf/libraries/{library_code}/circ-desks/"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving circulation desks.")

    def get_funds(self, parameters: dict | None = None) -> APIResponse:
        """Return data about all funds matching search in parameters."""
        api = "/almaws/v1/acq/funds"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving funds.")

    def get_fund(self, fund_id: str, parameters: dict | None = None) -> APIResponse:
        """Return data about a specific fund."""
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving fund.")

    def update_fund(
        self, fund_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        """Update a specific fund."""
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error updating fund.")

    def get_set(self, set_id: str, get_all_members: bool = True) -> Set:
        """Retrieve data for a specific set.

        :param set_id: The Alma id for the set.
        :param get_all_members: Fetch all set members.
        :return alma_set: An alma_api_client.models.Set object.
        """
        api = f"/almaws/v1/conf/sets/{set_id}"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
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
                    # TODO: Handle errors if this fails.
                    response_obj = APIResponse(api_response)
                    new_members = response_obj.api_data.get("member", [])
                    offset += len(new_members)
                    for new_member in new_members:
                        members.append(SetMember(member_data=new_member))

            alma_set.add_members(members)
            return alma_set
        else:
            raise APIError(api_response, "Error retrieving set")

    def _retrieve_all(self):
        # TODO: Is it practical to generalize API iteration to fetch all whatevers?
        pass

    def _get_marc_record(
        self,
        api: str,
        parameters: dict | None = None,
    ) -> requests.Response:
        api_response = self._call_api(
            method="get", api=api, parameters=parameters, data_format="xml"
        )
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
        if api_response.ok:
            return AuthorityRecord(api_response)
        else:
            raise APIError(api_response, "Error retrieving authority record.")

    def get_bib_record(self, bib_id: str, parameters: dict | None = None) -> BibRecord:
        """Retrieve bibliographic record from Alma, as a `BibRecord`.

        :param bib_id: The Alma bib record id.
        :param parameters: Other parameters, see Alma documentation for details.
        :raises: `ValueError`, if Alma cannot find a record matching the id.
        :return: The record.
        """
        api = f"/almaws/v1/bibs/{bib_id}"
        api_response = self._get_marc_record(api, parameters)
        if api_response.ok:
            return BibRecord(api_response)
        else:
            raise APIError(api_response, "Error retrieving bib record.")

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
        if api_response.ok:
            return HoldingRecord(api_response)
        else:
            raise APIError(api_response, "Error retrieving holding record.")

    def create_bib_record(
        self, bib_record: BibRecord, parameters: dict | None = None
    ) -> BibRecord:
        api = "/almaws/v1/bibs"
        data = bib_record.alma_xml
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters, data_format="xml"
        )
        if api_response.ok:
            return BibRecord(api_response)
        else:
            raise APIError(api_response, "Error creating bib record.")

    def update_bib_record(
        self, bib_id: str, bib_record: BibRecord, parameters: dict | None = None
    ) -> BibRecord:
        api = f"/almaws/v1/bibs/{bib_id}"
        data = bib_record.alma_xml
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters, data_format="xml"
        )
        if api_response.ok:
            return BibRecord(api_response)
        else:
            raise APIError(api_response, "Error updating bib record.")

    def delete_bib_record(
        self, bib_id: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/bibs/{bib_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting bib record.")

    def create_holding_record(
        self, bib_id: str, holding_record: HoldingRecord, parameters: dict | None = None
    ) -> HoldingRecord:
        api = f"/almaws/v1/bibs/{bib_id}/holdings"
        data = holding_record.alma_xml
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters, data_format="xml"
        )
        if api_response.ok:
            return HoldingRecord(api_response)
        else:
            raise APIError(api_response, "Error creating holding record.")

    def update_holding_record(
        self,
        bib_id: str,
        holding_record: HoldingRecord,
        parameters: dict | None = None,
    ) -> HoldingRecord:
        holding_id = holding_record.holding_id
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        data = holding_record.alma_xml
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters, data_format="xml"
        )
        if api_response.ok:
            return HoldingRecord(api_response)
        else:
            raise APIError(api_response, "Error updating holding record.")

    def delete_holding_record(
        self, bib_id: str, holding_id: str, parameters: dict | None = None
    ) -> APIResponse:
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting holding record.")
