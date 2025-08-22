import xml.etree.ElementTree as ET
from io import BytesIO
from pymarc import parse_xml_to_array, record_to_xml_node, Record


class AlmaMARCRecord:
    def __init__(self, api_response: dict) -> None:
        if api_response:
            self._create_from_api_response(api_response)

    def _create_from_api_response(self, api_response: dict):
        """Add attributes to this `AlmaMARCRecord` object based on data from the API response.

        :param api_response: A dict of data provided by the Alma API.
        :return: None
        """
        # The only relevant element in the API response is "content", which contains
        # XML as bytes with UTF-8 encoding.
        self.alma_xml: bytes = api_response.get("content", b"")
        self.marc_record = self.get_pymarc_record_from_xml(self.alma_xml)

    def get_pymarc_record_from_xml(self, alma_xml: bytes) -> Record | None:
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
        # Replace the old <record> element with the current MARCXML.
        if old_record_element:
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
