import json
import xmltodict
from alma_api_client import AlmaAPIClient
from alma_api_client.models.api import APIResponse


class AlmaAnalyticsClient:
    def __init__(self, api_key: str) -> None:
        self.API_KEY = api_key
        self.FILTER_XML_NAMESPACES = """
            xmlns:saw="com.siebel.analytics.web/report/v1.1"
            xmlns:sawx="com.siebel.analytics.web/expression/v1.1"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
        """

        self.alma_client = AlmaAPIClient(self.API_KEY)
        self.column_names: bool = True
        self.filter: str = ""
        self.report_path: str = ""
        self.rows_per_fetch: int = 1000

    def set_filter_xml(self, filter_xml: str) -> None:
        """Set filter which will be applied to Analytics report.

        Caller is responsible for building full XML required.
        Analytics report must already have an "Is prompted" filter
        on the given table and field.

        :param filter_xml: The XML for a valid Analytics filter.
        """
        self.filter = self._clean_filter_xml(filter_xml)

    def set_filter_equal(self, table_name: str, field_name: str, value: str) -> None:
        """Set filter for single-field 'EQUAL' comparison.

        Analytics report must already have an "Is prompted" filter
        on the given table and field.

        :param table_name: Name of the table to filter.
        :param field_name: Name of the field to filter on.
        :param value: Value to filter on.
        """
        filter_xml = f"""
        <sawx:expr xsi:type="sawx:comparison" op="equal"
            {self.FILTER_XML_NAMESPACES}
        >
            <sawx:expr xsi:type="sawx:sqlExpression">"{table_name}"."{field_name}"</sawx:expr>
            <sawx:expr xsi:type="xsd:string">{value}</sawx:expr>
        </sawx:expr>
        """
        self.filter = self._clean_filter_xml(filter_xml)

    def set_filter_like(self, table_name: str, field_name: str, value: str) -> None:
        """Set filter for single-field 'LIKE' comparison.

        Analytics report must already have an "Is prompted" filter
        on the given table and field.

        :param table_name: Name of the table to filter.
        :param field_name: Name of the field to filter on.
        :param value: Value to filter on. This value must contain SQL wildcard(s).
        """
        filter_xml = f"""
        <sawx:expr xsi:type="sawx:list" op="like"
            {self.FILTER_XML_NAMESPACES}
        >
            <sawx:expr xsi:type="sawx:sqlExpression">"{table_name}"."{field_name}"</sawx:expr>
            <sawx:expr xsi:type="xsd:string">{value}</sawx:expr>
        </sawx:expr>
        """
        self.filter = self._clean_filter_xml(filter_xml)

    def set_report_path(self, report_path: str) -> None:
        """Set full path to report in Analytics.

        :param report_path: The full path of the report in Analytics. The path
        must not be URL-escaped.
        """
        self.report_path = report_path

    def set_rows_per_fetch(self, rows_per_fetch: int) -> None:
        """Set number of rows to fetch per API call.

        Note: The only real reason to call this: testing iteration code.

        :param rows_per_fetch: The number of rows to fetch.
        Must be between 25 and 1000 inclusive; best as multiple of 25
        """
        self.rows_per_fetch = rows_per_fetch

    def get_report(self) -> list[dict]:
        """Run Analytics report and return data."""

        if not self.report_path:
            raise ValueError("Path to report must be set")
        # Used with every API call
        constant_params = {
            "col_names": self.column_names,
            "limit": self.rows_per_fetch,
        }
        initial_params = {
            "filter": self.filter,
            "path": self.report_path,
        }
        # First run: use constant + initial parameters merged
        params = constant_params | initial_params
        api_response = self.alma_client.get_analytics_report(params)
        # Get data in usable format
        report_data = self._get_report_data(api_response)
        # Initial set of rows
        all_rows = self._get_rows(report_data)

        # Preserve column_names as they don't seem to be set on subsequent runs
        column_names = report_data["column_names"]
        # Use the token from first run in all subsequent ones
        subsequent_params = {
            "token": report_data["resumption_token"],
        }

        while report_data["is_finished"] == "false":
            # After first run: use constant = subsequent parameters merged
            params = constant_params | subsequent_params
            api_response = self.alma_client.get_analytics_report(params)
            report_data = self._get_report_data(api_response)
            all_rows.extend(self._get_rows(report_data))

        # Replace generic column names with real ones
        final_data = self._apply_column_names(column_names, all_rows)
        return final_data

    def _get_report_data(self, api_response: APIResponse) -> dict:
        """Extract usable data from XML the Analytics API returns.

        :param xml_report: The full report as returned by the API.
        """

        # Report available only in XML
        # Entire XML report is a "list" with one value, in 'anies' element of json response
        xml: str = api_response.api_data["anies"][0]
        # Convert xml to python dict intermediate format
        xml_dict = xmltodict.parse(xml)
        # Convert this to real dict
        temp_dict: dict = json.loads(json.dumps(xml_dict))
        # Everything is in QueryResult dict
        report_dict = temp_dict["QueryResult"]
        # Actual rows of data are a list of dictionaries, in this dictionary
        rows: list = report_dict["ResultXml"]["rowset"]["Row"]

        # Clean up
        report_data: dict = {
            "rows": rows,
            "column_names": self._get_real_column_names(report_dict),
            "is_finished": report_dict["IsFinished"],  # should always exist
            "resumption_token": report_dict.get("ResumptionToken"),  # may not exist
        }

        return report_data

    def _get_real_column_names(self, report_dict: dict) -> dict:
        """Get real column names from report metadata.

        :param report_dict: Report data and metadata, created as part of _get_report_data().
        """

        column_names = {}
        try:
            column_info = report_dict["ResultXml"]["rowset"]["xsd:schema"][
                "xsd:complexType"
            ]["xsd:sequence"]["xsd:element"]
            # Create mapping of generic column names (Column0 etc.) to real column names
            for row in column_info:
                generic_name = row["@name"]
                real_name = row["@saw-sql:columnHeading"]
                column_names[generic_name] = real_name
        except KeyError:
            # OK to swallow this error
            pass
        return column_names

    def _apply_column_names(self, column_names: dict, data_rows: list) -> list:
        """Map real column names onto data rows, replacing generic ColumnN names and.
        removing meaningless Column0.

        :param column_names: Mapping between generic column names used by Analytics and
        real column names extracted from metadata.
        :param data_rows: All of the rows of data, which column names will be applied to.
        :return data: The updated rows of data, with column names applied.
        """
        data = []
        for row in data_rows:
            # Update keys to use real column names, removing meaningless Column0
            new_row = dict(
                [(column_names.get(k), v) for k, v in row.items() if k != "Column0"]
            )
            data.append(new_row)
        return data

    def _clean_filter_xml(self, filter_xml: str) -> str:
        """Strip out formatting characters which make API unhappy.

        :param filter_xml: The XML for an Analytics filter.
        :return: The input XML with relevant characters removed.
        """
        return filter_xml.replace("\n", "").replace("\t", "")

    def _get_rows(self, report_data: dict) -> list:
        """Convert single-row bare dict to a list containing that dict, if needed.

        :param report_data: Dictionary with a `rows` key.
        :return rows: List of rows of data.
        """
        # This is a list of dictionaries if > 1 row...
        # but just a dictionary if only 1 row.
        rows: list | dict = report_data.get("rows", [])
        if isinstance(rows, dict):
            rows = [rows]
        return rows
