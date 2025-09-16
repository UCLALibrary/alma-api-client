import xml.etree.ElementTree as ET
from io import BytesIO
from pymarc import parse_xml_to_array, record_to_xml_node, Record

import xmltodict
from pprint import pprint


class AlmaMARCRecord:
    # In this base class, only the MARC record and the XML are available.
    # Subclasses will add subclass-specific attributes.
    __slots__ = ["marc_record", "_all_attributes", "_record_type"]

    def __init__(self, api_response: dict | None = None) -> None:
        if api_response:
            self._create_from_api_response(api_response)

    def _create_from_api_response(self, api_response: dict) -> None:
        """Add attributes to this `AlmaMARCRecord` object based on data from the API response.

        :param api_response: A dict of data provided by the Alma API.
        :return: None
        """
        # The most important element in the API response is "content", which contains
        # XML as bytes with UTF-8 encoding.
        alma_xml: bytes = api_response.get("content", b"")
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

    def prepare_xml_for_update(self) -> bytes:
        """Combines this object's pymarc record with the required Alma XML and returns
        an updated bytes with MARCXML in the <record> element."""
        # Convert data to ElementTree elements,
        # using pymarc's record_to_xml_node to convert to MARCXML.
        original_element = ET.fromstring(self.alma_xml)
        new_record_element = record_to_xml_node(self.marc_record)

        old_record_element = original_element.find("record")
        if old_record_element is not None:
            # Replace the old <record> element with the current MARCXML.
            original_element.remove(old_record_element)
            original_element.append(new_record_element)

            # xml_declaration=False because the Alma API doesn't require it, and the API
            # call fails if xml_declaration=True due to escape characters in ET's declaration
            final_alma_xml = ET.tostring(
                original_element, encoding="utf8", method="xml", xml_declaration=False
            )
            self.alma_xml = final_alma_xml
            return final_alma_xml
        else:
            # TODO: Understand what errors can happen and handle them correctly
            # For now, if XML not updated, return original XML?
            return self.alma_xml

    def _set_attributes(self, alma_xml: bytes) -> None:
        alma_data = xmltodict.parse(alma_xml)
        pprint(alma_data, width=132)
        # Set specific attributes defined in __slots__ for read/write access.
        # There should be only one key in alma_data, indicating what type of record it is.
        self._record_type = next(iter(alma_data))
        attributes: dict = alma_data.get(self._record_type, {})
        for key, value in attributes.items():
            if key in self.__slots__:
                setattr(self, key, value)

        # Store as-is for read-only access to other data via properties.
        self._all_attributes = attributes


class AuthorityRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "cataloging_level",
        "record_format",
        "vocabulary",
    ]

    def __init__(self, api_response: dict | None = None) -> None:
        super().__init__(api_response)


class BibRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "brief_level",
        "cataloging_level",
        "record_format",
        "suppress_from_publishing",
    ]

    def __init__(self, api_response: dict | None = None) -> None:
        super().__init__(api_response)


class HoldingsRecord(AlmaMARCRecord):
    # These attributes are in addition to those defined in the base class.
    __slots__ = [
        "suppress_from_publishing",
    ]

    def __init__(self, api_response: dict | None = None) -> None:
        super().__init__(api_response)

    @property
    def created_by(self) -> str:
        return self._all_attributes.get("created_by", "")
