import xmltodict
import xml.etree.ElementTree as ET
from io import BytesIO
from pymarc import parse_xml_to_array, record_to_xml_node, Record
from requests import Response
from alma_api_client.models.api import APIResponse


class AlmaMARCRecord(APIResponse):
    # In this base class, only the MARC record and the XML are available.
    # Subclasses will add subclass-specific attributes.
    __slots__ = ["marc_record", "_all_attributes", "_record_type"]

    def __init__(self, api_response: Response | None = None) -> None:
        if api_response is not None:
            super().__init__(api_response)
            # Everything needed is in the api_response, available via base class.
            self._create_from_api_response()

    def _create_from_api_response(self) -> None:
        """Add attributes to this `AlmaMARCRecord` object based on data from the API response.

        :return: None
        """
        # The most important element in the API response is "content", which contains
        # XML as bytes with UTF-8 encoding.
        alma_xml: bytes = self.api_data.get("content", b"")
        self.marc_record = self._get_pymarc_record_from_xml(alma_xml)

        # Some other XML elements may be relevant, especially for creating records.
        # Those are defined in the class's __slots__, for exposure to class users.
        self._set_attributes(alma_xml)

    def _get_pymarc_record_from_xml(self, alma_xml: bytes) -> Record | None:
        """Convert a MARCXML record, as returned by the API, to a
        pymarc Record.

        :param alma_xml: Data from the Alma API representing a MARC record
        (biliographic or holdings).
        :return pymarc_record: Pymarc record
        """
        root = ET.fromstring(alma_xml)
        record = root.find("record")
        if record:
            # xml_declaration=False since we want only the <record> element, not a full XML doc
            alma_xml = ET.tostring(
                record, encoding="utf8", method="xml", xml_declaration=False
            )
            # pymarc needs file-like object
            with BytesIO(alma_xml) as fh:
                pymarc_record = parse_xml_to_array(fh)[0]
            return pymarc_record
        else:
            return None

    def _set_attributes(self, alma_xml: bytes) -> None:
        """Dynamically sets attributes from Alma data, which vary by subclass.
        Attributes set are based on __slots__ for the current subclaass.
        For the base class, no attributes are set as only subclass-specific data
        can be retrieved from Alma.

        :param alma_xml: XML data from an Alma MARC-specific API response.
        :return: None
        """
        # Convert XML to dictionary, since we hate XML.
        # This gives something like:
        # {'record_type': {'attribute_1': 'value_1', 'attribute_2': 'value_2'}}
        # TODO: Consider changing attr_prefix and cdata_key from xmltodict defaults.
        alma_data = xmltodict.parse(alma_xml)

        # Set specific attributes defined in __slots__ for read/write access.
        # There should be only one key in alma_data, indicating what type of record it is.
        if len(alma_data) != 1:
            raise ValueError("Unexpected data in {alma_data}")

        # Only 1 key, representing record type (authority, bib, holding).
        self._record_type = next(iter(alma_data))
        # All other attributes are the value of the record type key.
        attributes: dict = alma_data.get(self._record_type, {})
        # For each attribute, if it matches something in __slots__, set it on this object.
        # These attributes will be read/write for users of the object.
        for key, value in attributes.items():
            if key in self.__slots__:
                setattr(self, key, value)

        # Store the whole collection of attributes for read-only access to other data
        # via properties defined on subclasses.
        self._all_attributes = attributes

    @property
    def alma_xml(self) -> bytes:
        """Build the XML required for Alma, combined with this object's pymarc record.
        The pymarc record in self.marc_record is converted to MARCXML in the
        <record> element.

        :param: None
        :return alma_xml: XML (as bytes) to be sent to the Alma API.
        """
        # Create a dict from the attributes represented by this object's __slots__,
        # which are the only ones relevant for creating or updating Alma records.
        attributes = {key: getattr(self, key, "") for key in self.__slots__}

        # Convert this to XML, with record type as the root element.
        alma_data = {self._record_type: attributes}
        xml_data = xmltodict.unparse(alma_data)

        # Convert the pymarc record to MARCXML.
        marcxml = record_to_xml_node(self.marc_record)

        # Treat this as real XML now, for node manipulation.
        xml_element = ET.fromstring(xml_data)

        # Add the MARCXML.
        xml_element.append(marcxml)

        # Convert it all to a (bytes) string for use by Alma API.
        # xml_declaration=False because the Alma API doesn't require it, and the API
        # call fails if xml_declaration=True due to escape characters in ET's declaration.
        alma_xml = ET.tostring(
            xml_element, encoding="utf8", method="xml", xml_declaration=False
        )

        return alma_xml


class AuthorityRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "cataloging_level",
        "record_format",
        "vocabulary",
    ]

    def __init__(self, api_response: Response | None = None) -> None:
        super().__init__(api_response)
        self._record_type = "authority"


class BibRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "brief_level",
        "cataloging_level",
        "record_format",
        "suppress_from_publishing",
    ]

    def __init__(self, api_response: Response | None = None) -> None:
        super().__init__(api_response)
        self._record_type = "bib"

    @property
    def bib_id(self) -> str:
        return self._all_attributes.get("mms_id", "")


class HoldingRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "suppress_from_publishing",
    ]

    def __init__(self, api_response: Response | None = None) -> None:
        super().__init__(api_response)
        self._record_type = "holding"

    @property
    def created_by(self) -> str:
        return self._all_attributes.get("created_by", "")

    @property
    def holding_id(self) -> str:
        return self._all_attributes.get("holding_id", "")
