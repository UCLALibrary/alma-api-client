from enum import Enum
from requests import Response
from ..alma_api_client import APIResponse


# Derived from /almaws/v1/conf/code-tables/SetContentType
class SetContentType(Enum):
    AUTHORITY_MMS = "Authorities"
    BIB_MMS = "All Titles"
    BIB_MMS_DISCOVERY = "All Discovery Titles"
    COURSE = "Courses"
    FILE = "Digital files"
    HOLDING = "Physical holdings"
    IEC = "Collections"
    IED = "Digital titles"
    IEE = "Electronic titles"
    IE = "Inventory titles"
    IEPA = "Electronic collections"
    IEP = "Physical titles"
    IER = "Research assets"
    ITEM = "Physical items"
    PO_LINE = "Order lines"
    PORTFOLIO = "Electronic portfolios"
    READING_LIST_CITATION = "Citations"
    READING_LIST = "Reading lists"
    REMOTE_REPRESENTATION = "Digital remote representations"
    REPRESENTATION = "Digital representations"
    RESEARCHERS = "Researchers"
    USER = "User"
    VENDOR = "Vendor"


class SetMember:
    def __init__(self, member_data: dict) -> None:
        if member_data:
            self._create_from_member_data(member_data)

    def __str__(self) -> str:
        return f"{self.description} : {self.link}"

    def _create_from_member_data(self, member_data: dict):
        """Add attributes to this `SetMember` object based on data from the API response.

        :param member_data: A `dict` extracted from Alma API data.
        :return: None
        """
        self.id = member_data.get("id", "")
        self.description = member_data.get("description", "")
        self.link = member_data.get("link", "")


class Set(APIResponse):
    def __init__(self, name: str = "", api_response: Response | None = None) -> None:
        # Other fields could be added here, but unless we're creating sets from
        # scratch via API, I don't see a need.
        self.name = name
        if api_response:
            super().__init__(api_response)
            self._create_from_api_response(api_response)

    def _create_from_api_response(self, api_response: Response) -> None:
        """Add attributes to this `Set` object based on data from the API response.

        :param api_response: An `APIResponse` provided by the Alma API.
        :return: None
        """
        self.name = self.api_data.get("name", "")
        self.set_type = self._get_set_content_type()

        member_info = self.api_data.get("number_of_members", {})
        self.number_of_members = member_info.get("value", 0)
        self.members_api = member_info.get("link", "")

    def _get_set_content_type(self) -> SetContentType:
        """Convert the set content type to an enum.

        :return: A `SetContentType` enum.
        """
        content_info = self.api_data.get("content", {})
        # content_info looks like this (values will vary based on type):
        # {'content': {'desc': 'Physical items', 'value': 'ITEM'}
        return SetContentType(content_info.get("desc"))

    def add_members(self, members: list[SetMember]) -> None:
        """Add a reference to the members of this Set.

        :param members: A list of `SetMember` objects.
        :return: None
        """
        self.members = members
