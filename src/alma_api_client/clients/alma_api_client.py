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
        """Call the given Alma API, with any data and parameters provided.
        This is the only method which interacts directly with the remove Alma API.

        :param method: A supported HTTP method, one of "delete", "get", "post", "put".
        Case does not matter.
        :param api: The API, either as a full URL or the `/almaws/...` path.
        :param data: The data to sent in the body of a POST or PUT request.  See `Data` type
        for supported formats.
        :param parameters: Any parameters supported by the specific API being called.
        :param data_format: The desired format, expected to be json or xml.
        :raises: `ValueError`, if an unexpected value is passed in `method` or `data_format`.
        :return response: A `requests.Response` object with the data as received.
        """

        if method.lower() not in ["delete", "get", "post", "put"]:
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
        """Create an Alma item, attached to the given bib and holding record ids.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record.
        :param holding_id: The Alma id of the holding record.
        :param data: The item data; see Alma documentation for details.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
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
        """Retrieve the Alma item(s) attached to the given bib and holding record ids.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record.
        :param holding_id: The Alma id of the holding record.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}/items"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving item.")

    def get_integration_profiles(self, parameters: dict | None = None) -> APIResponse:
        """Retrieve Alma integration profiles, possibly filtered by search parameters.

        :param parameters: Any optional parameters; see Alma documentation for details.
        Caller can pass search parameters, but must deal with possible multiple matches.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/conf/integration-profiles"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving integration profiles.")

    def get_jobs(self, parameters: dict | None = None) -> APIResponse:
        """Retrieve Alma jobs (batch processes), possibly filtered by search parameters.

        :param parameters: Any optional parameters; see Alma documentation for details.
        Caller normally will pass parameters, but they're not required.  Caller must deal with
        possible multiple matches.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/conf/jobs"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving jobs.")

    def run_job(
        self, job_id, data: dict | None = None, parameters: dict | None = None
    ) -> APIResponse:
        """Tell Alma to queue / run a job.  Does *not* wait for completion.

        :param job_id: The Alma id of the job to run.
        :param data: The job data; see Alma documentation for details.
        Running a scheduled job requires empty data `[]`; not sure about other jobs.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
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
        """Wait for the given Alma job, specified by both the general job id and the specific
        instance id of the running job, to finish running.
        Running a job (via `run_job()`) just queues it to run; Alma assigns an instance id once the
        job begins running.  This method allows the caller to wait until the given instance of the
        job has completed.

        :param job_id: The Alma id of the job to monitor.
        :param instance_id: The Alma id of the specific instance of the running job.
        :param seconds_to_poll: How often to check the job status, in seconds.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/conf/jobs/{job_id}/instances/{instance_id}"
        api_response = self._call_api(method="get", api=api)
        # progress value (0-100) can't be used as it remains 0 if FAILED.
        # Use status instead; values from:
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
        """Retrieve Alma fees for the given user, possibly filtered by search parameters.

        :param user_id: The Alma id of the user.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/users/{user_id}/fees"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving fees.")

    def get_analytics_report(self, parameters: dict | None = None) -> APIResponse:
        """Run an Alma Analytics report and retrieve the data.  *NOTE* Caller currently
        is responsible for retrieving all data via paging; see also:
        `alma_analytics_client.get_report()`.

        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """

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
        """Retrieve the Alma Analytics path(s) for an Analytics report.
        TODO: Is this really needed?  Doesn't seem to be used by us....

        :param path: The path to the report.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/analytics/paths/{path}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving analytics path.")

    def get_vendors(self, parameters: dict | None = None) -> APIResponse:
        """Retrieve Alma vendors, possibly filtered by search parameters.

        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/acq/vendors"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving vendors.")

    def get_vendor(
        self, vendor_code: str, parameters: dict | None = None
    ) -> APIResponse:
        """Retrieve an Alma vendor record by code.

        :param vendor_code: The Alma code for the vendor.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/acq/vendors/{vendor_code}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving vendor.")

    def create_user(self, data: dict, parameters: dict | None = None) -> APIResponse:
        """Create an Alma user.

        :param data: The user data; see Alma documentation for details.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/users"
        api_response = self._call_api(
            method="post", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error creating user.")

    def delete_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        """Delete an Alma user.

        :param user_id: The Alma id of the user to delete.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting user.")

    def get_user(self, user_id: str, parameters: dict | None = None) -> APIResponse:
        """Retrieve an Alma user.

        :param user_id: The Alma id of the user to retrieve.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving user.")

    def update_user(
        self, user_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        """Update an Alma user.

        :param user_id: The Alma id of the user to update.
        :param data: The user data; see Alma documentation for details.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/users/{user_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error updating user.")

    def get_general_configuration(self) -> APIResponse:
        """Retrieve general Alma configuration information.  This is minimal, but
        useful for checking production / sandbox via environment_type value.

        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/conf/general"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving general configuration.")

    def get_code_tables(self) -> APIResponse:
        """Retrieve list of Alma code tables.  This specific API is undocumented.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/conf/code-tables"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving code tables.")

    def get_code_table(
        self, code_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Retrieve specific code table, via name from get_code_tables().

        :param code_table: The Alma code for the code table to retrieve.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/conf/code-tables/{code_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving code table.")

    def get_mapping_tables(self) -> APIResponse:
        """Retrieve list of Alma mapping tables.  This specific API is undocumented.

        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """

        api = "/almaws/v1/conf/mapping-tables"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving mapping tables.")

    def get_mapping_table(
        self, mapping_table: str, parameters: dict | None = None
    ) -> APIResponse:
        """Retrieve specific mapping table, via name from get_mapping_tables().

        :param mapping_table: The Alma code for the mapping table to retrieve.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/conf/code-tables/{mapping_table}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving mapping table.")

    def get_libraries(self) -> APIResponse:
        """Retrieve all Alma libraries.

        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/conf/libraries"
        api_response = self._call_api(method="get", api=api)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving libraries.")

    def get_library(self, library_code: str) -> APIResponse:
        """Retrieve data for a single library, via code.
        Doesn't provide more details than each entry in get_libaries().

        :param ibrary_code: The Alma code for the library to retrieve.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
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
        """Retrieve data about Alma circulation desks in a single library, via code.

        :param library_code: The Alma code for the library's circulation desks to retrieve.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/conf/libraries/{library_code}/circ-desks/"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving circulation desks.")

    def get_funds(self, parameters: dict | None = None) -> APIResponse:
        """Retrieve Alma funds, possibly filtered by search parameters.

        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = "/almaws/v1/acq/funds"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving funds.")

    def get_fund(self, fund_id: str, parameters: dict | None = None) -> APIResponse:
        """Retrieve an Alma fund.

        :param fund_id: The Alma id of the fund to retrieve.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(method="get", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error retrieving fund.")

    def update_fund(
        self, fund_id: str, data: dict, parameters: dict | None = None
    ) -> APIResponse:
        """Update an Alma fund.

        :param fund_id: The Alma id of the fund to update.
        :param data: The fund data; see Alma documentation for details.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :raises: `APIError`, if an Alma API error occurs.
        :return: An `APIResponse` object with all relevant data.
        """
        api = f"/almaws/v1/acq/funds/{fund_id}"
        api_response = self._call_api(
            method="put", api=api, data=data, parameters=parameters
        )
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error updating fund.")

    def get_set(self, set_id: str, get_all_members: bool = True) -> Set:
        """Retrieve data for an Alma set.

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
        """Retrieve an Alma MARC record, as MARCXML combined with other Alma-specific data.
        This is a generic internal method, meant to be called only by type-specific
        external methods.

        :param api: The API, either as a full URL or the `/almaws/...` path.
        :param parameters: Any optional parameters; see Alma documentation for details.
        :return response: A `requests.Response` object with the data as received.
        """
        api_response = self._call_api(
            method="get", api=api, parameters=parameters, data_format="xml"
        )
        # This is a raw `requests.Response`, which the calling method will convert to a
        # specific subclass of APIResponse.
        return api_response

    def get_authority_record(
        self, authority_id: str, parameters: dict | None = None
    ) -> AuthorityRecord:
        """Retrieve authority record from Alma, as an `AuthorityRecord`.

        :param authority_id: The Alma authority record id.
        :param parameters: Any optional parameters; see Alma documentation for details.
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
        """Create an Alma bibliographic record.

        :param bib_record: The Alma bib record, as a `BibRecord`.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as created in Alma, augmented with new data like record id.
        """
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
        """Update an Alma bibliographic record.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record.
        :param bib_record: The Alma bib record, as a `BibRecord`.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as updated in Alma, augmented with any new data.
        """
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
        """Delete an Alma bibliographic record.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as updated in Alma, augmented with any new data.
        """
        api = f"/almaws/v1/bibs/{bib_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting bib record.")

    def create_holding_record(
        self, bib_id: str, holding_record: HoldingRecord, parameters: dict | None = None
    ) -> HoldingRecord:
        """Create an Alma holding record, as an `HoldingRecord`.

        :param bib_id: The Alma bib record id the holding record will be attached to.
        :param holding_record: The Alma holding record, as a `HoldingRecord`.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as created in Alma, augmented with new data like record id.
        """
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
        """Update an Alma holding record.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record the holding record
        is attached to
        :param holding_record: The Alma holding record, as a `HoldingRecord`.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as updated in Alma, augmented with any new data.
        """
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
        """Delete an Alma bibliographic record.

        :param bib_id: The Alma id (aka MMS ID) of the bibliographic record the holding record
        is attached to.
        :param holding_id: The Alma id of the holding record to delete.
        :param parameters: Other parameters, see Alma documentation for details.
        :return: The record as updated in Alma, augmented with any new data.
        """
        api = f"/almaws/v1/bibs/{bib_id}/holdings/{holding_id}"
        api_response = self._call_api(method="delete", api=api, parameters=parameters)
        if api_response.ok:
            return APIResponse(api_response)
        else:
            raise APIError(api_response, "Error deleting holding record.")
