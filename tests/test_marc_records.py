from copy import deepcopy
import pickle
import sys
from unittest import TestCase
from pymarc import MARCReader

from alma_api_client.models.marc_records import BibRecord

# Can't find a way to get tests to run within the dev environment
# without this hack.
sys.path.append("/home/app_user/project/src")
# Ignore pylance for this out-of-position import.
from alma_api_client.models.api import APIResponse  # noqa


class TestMARCParsing(TestCase):
    """Confirm response from API is converted to `AlmaMARCRecord` correctly.
    Tests focus on BibRecord, which should be sufficient as the subclasses of
    AlmaMARCRecord differ only in a few specific attributes they expose.

    This does not test properties inherited from `APIResponse`, as those are tested
    separately.
    """

    @classmethod
    def setUpClass(cls):
        # This is a real `requests.Response` object as received from the Alma API,
        # for a bib record, saved via `pickle.dump()`.
        with open("tests/data/marc_response.pickle", "rb") as f:
            cls.alma_response = pickle.load(f)
        cls.bib_record = BibRecord(cls.alma_response)

    def test_bib_id(self):
        bib_record = self.bib_record
        self.assertEqual(bib_record.bib_id, "9992524713606533")

    def test_brief_level(self):
        bib_record = self.bib_record
        self.assertEqual(bib_record.brief_level, {"@desc": "01", "#text": "01"})

    def test_cataloging_level(self):
        bib_record = self.bib_record
        self.assertEqual(
            bib_record.cataloging_level, {"@desc": "Default Level", "#text": "00"}
        )

    def test_record_format(self):
        bib_record = self.bib_record
        self.assertEqual(bib_record.record_format, "marc21")

    def test_suppress_from_publishing(self):
        bib_record = self.bib_record
        # Note: Alma returns this as a string, and we are currently not converting to boolean.
        self.assertEqual(bib_record.suppress_from_publishing, "true")

    def test_marc_to_xml(self):
        bib_record = self.bib_record
        # Load XML <bib> data previously saved.
        with open("tests/data/bib_record.xml", "rb") as f:
            bib_xml = f.read()
        # Confirm the XML data previously saved, which contains the MARC record as MARCXML,
        # is part of the larger XML package which would be sent to Alma.
        self.assertIn(bib_xml, bib_record.alma_xml)

    def test_response_to_marc(self):
        # This contains the converted response in bib_record.marc_record
        bib_record = self.bib_record
        # Load binary MARC record previously saved.
        reader = MARCReader(open("tests/data/bib_record.mrc", "rb"))
        # Only one record in this file.
        marc_record = next(reader)
        reader.close()

        # Make the !@*(#& type-checker happy, since these could both be None...
        if bib_record.marc_record and marc_record:
            # Need to compare bytes via Record.as_marc(), not Record object identities.
            self.assertEqual(bib_record.marc_record.as_marc(), marc_record.as_marc())

    def test_changes_are_included_in_xml(self):
        updated_bib_record = deepcopy(self.bib_record)
        # Change one of the non-MARC properties which Alma uses.
        updated_bib_record.suppress_from_publishing = "false"
        expected_xml = b"<suppress_from_publishing>false</suppress_from_publishing"
        self.assertIn(expected_xml, updated_bib_record.alma_xml)
