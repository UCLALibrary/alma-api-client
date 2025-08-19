from enum import Enum


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
    def __init__(self, api_response: dict) -> None:
        if api_response:
            self._create_from_api_response(api_response)

    def __str__(self) -> str:
        return f"{self.description} : {self.link}"

    def _create_from_api_response(self, api_response: dict):
        """Add attributes to this `SetMember` object based on data from the API response.

        :param api_response: A dict of data provided by the Alma API.
        :return: None
        """
        self.id = api_response.get("id", "")
        self.description = api_response.get("description", "")
        self.link = api_response.get("link", "")


class Set:
    def __init__(self, name: str = "", api_response: dict | None = None) -> None:
        # Other fields could be added here, but unless we're creating sets from
        # scratch via API, I don't see a need.
        self.name = name
        if api_response:
            self._create_from_api_response(api_response)

    def _create_from_api_response(self, api_response: dict) -> None:
        """Add attributes to this `Set` object based on data from the API response.

        :param api_response: A dict of data provided by the Alma API.
        :return: None
        """
        self.name = api_response.get("name", "")
        self.content_type = self._get_content_type_from_api_response(api_response)

        member_info = api_response.get("number_of_members", {})
        self.number_of_members = member_info.get("value", 0)
        self.members_api = member_info.get("link", "")

    def _get_content_type_from_api_response(self, api_response: dict) -> SetContentType:
        """Convert the set content type to an enum.

        :param api_response: A dict of data provided by the Alma API.
        :return: A `SetContentType` enum.
        """
        content = api_response.get("content", {})
        return SetContentType(content.get("desc"))

    def add_members(self, members: list[SetMember]) -> None:
        """Add a reference to the members of this Set.

        :param members: A list of `SetMember` objects.
        :return: None
        """
        self.members = members
