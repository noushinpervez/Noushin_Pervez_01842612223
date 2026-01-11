"""
Unit Tests for HL7 SIU S12 Appointment Parser

This module contains comprehensive unit tests for the HL7 parser.
Tests cover:
- Correct parsing of valid SIU messages
- Graceful handling of missing fields
- Behavior with malformed input
- Timestamp normalization logic

Run tests with: python -m pytest tests/test_parser.py -v
Or: python -m unittest tests.test_parser
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hl7_parser.segment_parsers import (
    safe_get_field,
    safe_get_component,
    parse_hl7_timestamp,
    parse_hl7_date,
    parse_msh_segment,
    parse_sch_segment,
    parse_pid_segment,
    parse_pv1_segment,
    split_message_into_segments,
    get_segment,
)
from hl7_parser.parser import (
    parse_hl7_message,
    parse_single_message,
    split_hl7_file_into_messages,
    validate_message_type,
    parse_hl7_file_streaming,
)
from hl7_parser.exceptions import (
    InvalidMessageTypeError,
    MissingSegmentError,
    MalformedSegmentError,
    InvalidHL7FormatError,
)


class TestSafeGetField(unittest.TestCase):
    """Tests for safe_get_field function."""

    def test_get_existing_field(self):
        """Test getting a field that exists."""
        fields = ["PID", "1", "P12345", "", "Doe^John"]
        result = safe_get_field(fields, 2)
        self.assertEqual(result, "P12345")

    def test_get_field_out_of_range(self):
        """Test getting a field beyond the list length."""
        fields = ["PID", "1", "P12345"]
        result = safe_get_field(fields, 10)
        self.assertEqual(result, "")

    def test_get_empty_field(self):
        """Test getting a field that is empty."""
        fields = ["PID", "", "P12345"]
        result = safe_get_field(fields, 1)
        self.assertEqual(result, "")

    def test_get_field_with_default(self):
        """Test getting a field with a custom default value."""
        fields = ["PID", ""]
        result = safe_get_field(fields, 5, "DEFAULT")
        self.assertEqual(result, "DEFAULT")

    def test_get_field_with_whitespace(self):
        """Test that whitespace is stripped from fields."""
        fields = ["PID", "  value  "]
        result = safe_get_field(fields, 1)
        self.assertEqual(result, "value")


class TestSafeGetComponent(unittest.TestCase):
    """Tests for safe_get_component function."""

    def test_get_first_component(self):
        """Test getting the first component of a field."""
        field = "Doe^John^Michael"
        result = safe_get_component(field, 0)
        self.assertEqual(result, "Doe")

    def test_get_middle_component(self):
        """Test getting a middle component."""
        field = "Doe^John^Michael"
        result = safe_get_component(field, 1)
        self.assertEqual(result, "John")

    def test_get_component_out_of_range(self):
        """Test getting a component beyond available components."""
        field = "Doe^John"
        result = safe_get_component(field, 5)
        self.assertEqual(result, "")

    def test_get_component_empty_field(self):
        """Test getting a component from an empty field."""
        result = safe_get_component("", 0)
        self.assertEqual(result, "")

    def test_get_component_no_separator(self):
        """Test getting a component when there's no separator."""
        field = "SingleValue"
        result = safe_get_component(field, 0)
        self.assertEqual(result, "SingleValue")


class TestParseHL7Timestamp(unittest.TestCase):
    """Tests for HL7 timestamp parsing and normalization."""

    def test_full_timestamp(self):
        """Test parsing a complete timestamp (YYYYMMDDHHMMSS)."""
        result = parse_hl7_timestamp("20250502130000")
        self.assertEqual(result, "2025-05-02T13:00:00Z")

    def test_timestamp_with_minutes(self):
        """Test parsing timestamp with hours and minutes only."""
        result = parse_hl7_timestamp("202505021430")
        self.assertEqual(result, "2025-05-02T14:30:00Z")

    def test_date_only(self):
        """Test parsing date-only timestamp."""
        result = parse_hl7_timestamp("20250502")
        self.assertEqual(result, "2025-05-02T00:00:00Z")

    def test_timestamp_with_timezone(self):
        """Test parsing timestamp with timezone offset."""
        result = parse_hl7_timestamp("20250502130000+0500")
        self.assertEqual(result, "2025-05-02T13:00:00Z")

    def test_empty_timestamp(self):
        """Test parsing empty timestamp."""
        result = parse_hl7_timestamp("")
        self.assertIsNone(result)

    def test_invalid_timestamp(self):
        """Test parsing invalid timestamp."""
        result = parse_hl7_timestamp("invalid")
        self.assertIsNone(result)

    def test_short_timestamp(self):
        """Test parsing timestamp that's too short."""
        result = parse_hl7_timestamp("2025")
        self.assertIsNone(result)


class TestParseHL7Date(unittest.TestCase):
    """Tests for HL7 date parsing."""

    def test_valid_date(self):
        """Test parsing a valid date."""
        result = parse_hl7_date("19850210")
        self.assertEqual(result, "1985-02-10")

    def test_empty_date(self):
        """Test parsing empty date."""
        result = parse_hl7_date("")
        self.assertIsNone(result)

    def test_invalid_date(self):
        """Test parsing invalid date."""
        result = parse_hl7_date("notadate")
        self.assertIsNone(result)


class TestParseMSHSegment(unittest.TestCase):
    """Tests for MSH segment parsing."""

    def test_parse_valid_msh(self):
        """Test parsing a valid MSH segment."""
        segment = "MSH|^~\\&|SENDER|FACILITY|RECEIVER|DEST|20250502130000||SIU^S12|MSG001|P|2.5"
        result = parse_msh_segment(segment)

        self.assertEqual(result["message_type"], "SIU^S12")
        self.assertEqual(result["message_control_id"], "MSG001")
        self.assertEqual(result["sending_application"], "SENDER")

    def test_parse_minimal_msh(self):
        """Test parsing MSH with minimal fields."""
        segment = "MSH|^~\\&|||||||SIU^S12"
        result = parse_msh_segment(segment)

        self.assertEqual(result["message_type"], "SIU^S12")


class TestParseSCHSegment(unittest.TestCase):
    """Tests for SCH segment parsing."""

    def test_parse_valid_sch(self):
        """Test parsing a valid SCH segment."""
        segment = "SCH|123456|456789|||||Consultation||Clinic A||20250502130000"
        result = parse_sch_segment(segment)

        self.assertEqual(result["appointment_id"], "456789")
        self.assertEqual(result["appointment_datetime"], "2025-05-02T13:00:00Z")
        self.assertEqual(result["reason"], "Consultation")

    def test_parse_sch_with_placer_id_only(self):
        """Test SCH parsing when only placer ID is present."""
        segment = "SCH|PLACER123||||||Checkup|||20250503100000"
        result = parse_sch_segment(segment)

        self.assertEqual(result["appointment_id"], "PLACER123")

    def test_parse_sch_with_complex_id(self):
        """Test SCH parsing when ID has components."""
        segment = "SCH|123^PLACER_SYS|456^FILLER_SYS|||||Follow-up|||20250504090000"
        result = parse_sch_segment(segment)

        # Should get just the ID portion, not the full component
        self.assertEqual(result["appointment_id"], "456")


class TestParsePIDSegment(unittest.TestCase):
    """Tests for PID segment parsing."""

    def test_parse_valid_pid(self):
        """Test parsing a valid PID segment."""
        segment = "PID|1||P12345||Doe^John^Michael||19850210|M"
        result = parse_pid_segment(segment)

        self.assertEqual(result["patient_id"], "P12345")
        self.assertEqual(result["first_name"], "John")
        self.assertEqual(result["last_name"], "Doe")
        self.assertEqual(result["dob"], "1985-02-10")
        self.assertEqual(result["gender"], "M")

    def test_parse_pid_female_gender(self):
        """Test PID parsing with female gender."""
        segment = "PID|1||P99999||Smith^Jane||19901015|F"
        result = parse_pid_segment(segment)

        self.assertEqual(result["gender"], "F")

    def test_parse_pid_missing_fields(self):
        """Test PID parsing with missing optional fields."""
        segment = "PID|1||P12345||Doe^John"
        result = parse_pid_segment(segment)

        self.assertEqual(result["patient_id"], "P12345")
        self.assertEqual(result["first_name"], "John")
        self.assertEqual(result["last_name"], "Doe")
        self.assertIsNone(result["dob"])


class TestParsePV1Segment(unittest.TestCase):
    """Tests for PV1 segment parsing."""

    def test_parse_valid_pv1(self):
        """Test parsing a valid PV1 segment."""
        segment = "PV1|1|O|Clinic A^Room 203||||D67890^Smith^Dr"
        result = parse_pv1_segment(segment)

        self.assertEqual(result["provider_id"], "D67890")
        self.assertEqual(result["provider_name"], "Dr Smith")
        self.assertEqual(result["location"], "Clinic A Room 203")

    def test_parse_pv1_minimal(self):
        """Test parsing PV1 with minimal data."""
        segment = "PV1|1|O"
        result = parse_pv1_segment(segment)

        self.assertEqual(result["provider_id"], "")
        self.assertEqual(result["provider_name"], "")


class TestSplitMessageIntoSegments(unittest.TestCase):
    """Tests for message splitting functionality."""

    def test_split_with_newlines(self):
        """Test splitting message with \\n separators."""
        message = "MSH|test\nPID|test\nPV1|test"
        segments = split_message_into_segments(message)

        self.assertEqual(len(segments), 3)
        self.assertTrue(segments[0].startswith("MSH"))

    def test_split_with_carriage_returns(self):
        """Test splitting message with \\r separators."""
        message = "MSH|test\rPID|test\rPV1|test"
        segments = split_message_into_segments(message)

        self.assertEqual(len(segments), 3)

    def test_split_with_crlf(self):
        """Test splitting message with \\r\\n separators."""
        message = "MSH|test\r\nPID|test\r\nPV1|test"
        segments = split_message_into_segments(message)

        self.assertEqual(len(segments), 3)

    def test_split_filters_empty_lines(self):
        """Test that empty lines are filtered out."""
        message = "MSH|test\n\n\nPID|test"
        segments = split_message_into_segments(message)

        self.assertEqual(len(segments), 2)


class TestGetSegment(unittest.TestCase):
    """Tests for segment retrieval functionality."""

    def test_get_existing_segment(self):
        """Test getting a segment that exists."""
        segments = ["MSH|data", "PID|patient", "PV1|visit"]
        result = get_segment(segments, "PID")

        self.assertEqual(result, "PID|patient")

    def test_get_nonexistent_segment(self):
        """Test getting a segment that doesn't exist."""
        segments = ["MSH|data", "PID|patient"]
        result = get_segment(segments, "SCH")

        self.assertIsNone(result)


class TestValidateMessageType(unittest.TestCase):
    """Tests for message type validation."""

    def test_valid_siu_s12(self):
        """Test validation passes for SIU^S12."""
        msh_data = {"message_type": "SIU^S12"}
        # Should not raise
        validate_message_type(msh_data)

    def test_siu_s12_with_structure(self):
        """Test validation passes for SIU^S12^SIU_S12."""
        msh_data = {"message_type": "SIU^S12^SIU_S12"}
        # Should not raise
        validate_message_type(msh_data)

    def test_invalid_message_type(self):
        """Test validation fails for non-SIU messages."""
        msh_data = {"message_type": "ADT^A01"}

        with self.assertRaises(InvalidMessageTypeError):
            validate_message_type(msh_data)


class TestParseHL7Message(unittest.TestCase):
    """Integration tests for full message parsing."""

    def test_parse_complete_message(self):
        """Test parsing a complete valid SIU^S12 message."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502130000||SIU^S12|123|P|2.5
SCH|123456|456789|||||Consultation||Clinic A||20250502130000
PID|1||P12345||Doe^John||19850210|M
PV1|1|O|Clinic A||||D67890^Smith^Dr"""

        appointment = parse_hl7_message(message)

        self.assertEqual(appointment.appointment_id, "456789")
        self.assertEqual(appointment.appointment_datetime, "2025-05-02T13:00:00Z")
        self.assertEqual(appointment.patient.id, "P12345")
        self.assertEqual(appointment.patient.first_name, "John")
        self.assertEqual(appointment.patient.last_name, "Doe")
        self.assertEqual(appointment.provider.id, "D67890")
        self.assertEqual(appointment.reason, "Consultation")

    def test_parse_message_without_pid(self):
        """Test parsing message without PID segment."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502130000||SIU^S12|123|P|2.5
SCH|123456|456789|||||Checkup||Clinic B||20250502140000
PV1|1|O|Clinic B||||D11111^Jones^Dr"""

        appointment = parse_hl7_message(message)

        self.assertEqual(appointment.appointment_id, "456789")
        self.assertIsNone(appointment.patient)
        self.assertIsNotNone(appointment.provider)

    def test_parse_message_without_pv1(self):
        """Test parsing message without PV1 segment."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502130000||SIU^S12|123|P|2.5
SCH|123456|456789|||||Checkup||Clinic C||20250502150000
PID|1||P99999||Brown^Alice||19950505|F"""

        appointment = parse_hl7_message(message)

        self.assertEqual(appointment.appointment_id, "456789")
        self.assertIsNotNone(appointment.patient)
        self.assertIsNone(appointment.provider)

    def test_parse_empty_message(self):
        """Test that empty message raises error."""
        with self.assertRaises(InvalidHL7FormatError):
            parse_hl7_message("")

    def test_parse_wrong_message_type(self):
        """Test that wrong message type raises error."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502||ADT^A01|123|P|2.5
PID|1||P12345||Test^Patient"""

        with self.assertRaises(InvalidMessageTypeError):
            parse_hl7_message(message)

    def test_parse_missing_msh(self):
        """Test that missing MSH raises error."""
        message = """SCH|123456|456789|||||Checkup|||Clinic||20250502150000
PID|1||P12345||Test^Patient"""

        with self.assertRaises(MissingSegmentError):
            parse_hl7_message(message)

    def test_parse_missing_sch(self):
        """Test that missing SCH raises error."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502||SIU^S12|123|P|2.5
PID|1||P12345||Test^Patient"""

        with self.assertRaises(MissingSegmentError):
            parse_hl7_message(message)

    def test_parse_single_message(self):
        """Test parsing using parse_single_message function."""
        message = """MSH|^~\\&|SENDER|FAC|REC|FAC|20250502130000||SIU^S12|123|P|2.5
SCH|123456|456789|||||Consultation||Clinic A||20250502130000
PID|1||P12345||Doe^John||19850210|M
PV1|1|O|Clinic A||||D67890^Smith^Dr"""

        appointment1 = parse_hl7_message(message)
        appointment2 = parse_single_message(message)

        self.assertEqual(appointment1.appointment_id, appointment2.appointment_id)
        self.assertEqual(appointment1.patient.id, appointment2.patient.id)

    def test_parse_malformed_sch_missing_datetime(self):
        """Test that SCH segment without valid datetime raises MalformedSegmentError."""
        # SCH segment missing appointment datetime at position 11
        message = """MSH|^~\&|SENDER|FAC|REC|FAC|20250502||SIU^S12|123|P|2.5
SCH|123456|456789|||||Checkup|||Clinic
PID|1||P12345||Test^Patient"""

        with self.assertRaises(MalformedSegmentError) as context:
            parse_hl7_message(message)

        # Verify it's specifically about the datetime
        self.assertIn("datetime", str(context.exception).lower())

    def test_parse_sch_missing_appointment_id(self):
        """Test that SCH segment without appointment ID raises MalformedSegmentError."""
        # SCH segment with empty appointment IDs
        message = """MSH|^~\&|SENDER|FAC|REC|FAC|20250502||SIU^S12|123|P|2.5
SCH|||||||Checkup|||Clinic||20250502150000
PID|1||P12345||Test^Patient"""

        with self.assertRaises(MalformedSegmentError) as context:
            parse_hl7_message(message)

        # Verify it's specifically about the appointment ID
        self.assertIn("appointment id", str(context.exception).lower())


class TestSplitHL7FileIntoMessages(unittest.TestCase):
    """Tests for splitting files with multiple messages."""

    def test_split_single_message(self):
        """Test file with single message."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
PID|1||P1||Doe^John"""

        messages = split_hl7_file_into_messages(content)
        self.assertEqual(len(messages), 1)

    def test_split_multiple_messages(self):
        """Test file with multiple messages separated by blank lines."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
PID|1||P1||Doe^John

MSH|^~\\&|A|B|C|D|20250502||SIU^S12|2|P|2.5
SCH|2||||||Reason2||Loc2||20250502140000
PID|1||P2||Smith^Jane"""

        messages = split_hl7_file_into_messages(content)
        self.assertEqual(len(messages), 2)

    def test_split_multiple_messages_no_blank_lines(self):
        """Test multiple messages where each MSH starts a new message."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
MSH|^~\\&|A|B|C|D|20250502||SIU^S12|2|P|2.5
SCH|2||||||Reason2||Loc2||20250502140000"""

        messages = split_hl7_file_into_messages(content)
        self.assertEqual(len(messages), 2)


class TestParseHL7FileStreaming(unittest.TestCase):
    """Tests for streaming file parsing functionality."""

    def test_stream_single_message(self):
        """Test streaming parsing of a file with single message."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
PID|1||P1||Doe^John"""

        # Create temporary file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hl7", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            appointments = list(parse_hl7_file_streaming(temp_path))
            self.assertEqual(len(appointments), 1)
            self.assertEqual(appointments[0].appointment_id, "1")
        finally:
            os.unlink(temp_path)

    def test_stream_multiple_messages(self):
        """Test streaming parsing of a file with multiple messages."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
PID|1||P1||Doe^John

MSH|^~\\&|A|B|C|D|20250502||SIU^S12|2|P|2.5
SCH|2||||||Reason2||Loc2||20250502140000
PID|1||P2||Smith^Jane"""

        # Create temporary file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hl7", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            appointments = list(parse_hl7_file_streaming(temp_path))
            self.assertEqual(len(appointments), 2)
            self.assertEqual(appointments[0].appointment_id, "1")
            self.assertEqual(appointments[1].appointment_id, "2")
        finally:
            os.unlink(temp_path)

    def test_stream_continue_on_error(self):
        """Test streaming with continue_on_error=True."""
        content = """MSH|^~\\&|A|B|C|D|20250502||SIU^S12|1|P|2.5
SCH|1||||||Reason||Loc||20250502130000
PID|1||P1||Doe^John

MSH|^~\\&|A|B|C|D|20250502||ADT^A01|2|P|2.5
INVALID|content

MSH|^~\\&|A|B|C|D|20250502||SIU^S12|3|P|2.5
SCH|3||||||Reason3||Loc3||20250502150000
PID|1||P3||Brown^Bob"""

        # Create temporary file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hl7", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            appointments = list(
                parse_hl7_file_streaming(temp_path, continue_on_error=True)
            )
            self.assertEqual(
                len(appointments), 2
            )  # Should skip the invalid ADT message
            self.assertEqual(appointments[0].appointment_id, "1")
            self.assertEqual(appointments[1].appointment_id, "3")
        finally:
            os.unlink(temp_path)


class TestAppointmentToJson(unittest.TestCase):
    """Tests for JSON serialization."""

    def test_to_json_complete(self):
        """Test JSON output for complete appointment."""
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||General Consultation||Clinic A Room 203||20250502130000
PID|1||P12345||Doe^John||19850210|M
PV1|1|O|Clinic A^Room 203||||D67890^Smith^Dr"""

        appointment = parse_hl7_message(message)
        json_output = appointment.to_json()

        # Verify it's valid JSON and contains expected fields
        import json

        data = json.loads(json_output)

        self.assertEqual(data["appointment_id"], "456")
        self.assertEqual(data["patient"]["id"], "P12345")
        self.assertEqual(data["provider"]["name"], "Dr Smith")

    def test_to_dict_excludes_none(self):
        """Test that to_dict properly handles None values."""
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||||Loc||20250502130000
PID|1||P12345||Doe^John"""

        appointment = parse_hl7_message(message)
        data = appointment.to_dict()

        # Reason should not be in output if it's None
        self.assertNotIn("reason", data)


class TestEdgeCases(unittest.TestCase):
    """
    Tests for specific edge cases.

    These are the tricky real-world scenarios that break naive parsers.
    These scenarios are common in real-world HL7 feeds.
    """

    def test_fields_present_but_empty(self):
        """
        Test handling when fields exist but are empty (just pipes).

        Real HL7 messages often have empty fields like: PID|1|||Doe^John
        The parser should treat these as missing, not crash.
        """
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||||Loc||20250502130000
PID|1||||Doe^John||||"""

        appointment = parse_hl7_message(message)

        # Patient should still be created with available data
        self.assertIsNotNone(appointment.patient)
        self.assertEqual(appointment.patient.last_name, "Doe")
        # Empty patient_id field should result in empty string or UNKNOWN
        self.assertIn(appointment.patient.id, ["", "UNKNOWN"])

    def test_unexpected_component_separators_in_name(self):
        """
        Test handling of complex component structures.

        Names can get weird: Doe^John^M^Jr^Dr or even worse with
        sub-components using &. Extract what is needed
        without choking on extra carets.
        """
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||||Loc||20250502130000
PID|1||P12345||Doe^John^Michael^Jr^Dr||19850210|M"""

        appointment = parse_hl7_message(message)

        self.assertEqual(appointment.patient.last_name, "Doe")
        self.assertEqual(appointment.patient.first_name, "John")
        # First and last are extracted, extras are ignored

    def test_extra_segments_ignored(self):
        """
        Test that non-standard segments (NTE, OBX, etc.) are ignored.

        Real HL7 feeds often include extra segments.
        Parser shouldn't crash, just skip them.
        """
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||Consultation||Clinic||20250502130000
PID|1||P12345||Doe^John||19850210|M
PV1|1|O|Clinic||||D67890^Smith^Dr
NTE|1||This is a note that should be ignored
OBX|1|TX|VITALS||BP: 120/80
ZZZ|custom|segment|data"""

        # Should parse without error
        appointment = parse_hl7_message(message)

        self.assertEqual(appointment.appointment_id, "456")
        self.assertEqual(appointment.patient.id, "P12345")
        # NTE, OBX, ZZZ data is simply not in output

    def test_truncated_segments_handled_safely(self):
        """
        Test that short segments don't cause index errors.

        Sometimes HL7 senders truncate segments at the end.
        A PID with just: PID|1||P12345 is valid, just missing data.
        """
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|123|456|||||||Clinic||20250502130000
PID|1||P12345
PV1|1|O"""

        appointment = parse_hl7_message(message)

        # Should parse with available data
        self.assertEqual(appointment.patient.id, "P12345")
        self.assertEqual(appointment.patient.first_name, "")  # Missing is OK
        self.assertIsNone(appointment.provider)  # No provider ID in short PV1

    def test_complex_appointment_id_components(self):
        """
        Test extraction of appointment ID from complex SCH fields.

        SCH-1/2 can be: 12345^PLACER_SYS^ISO or more complex.
        Only the ID portion is extracted.
        """
        message = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|PLAC123^HOSP^ISO|FILL456^HOSP^ISO|||||Checkup||Clinic||20250502130000
PID|1||P12345||Doe^John||19850210|M"""

        appointment = parse_hl7_message(message)

        # Should get filler ID (SCH-2) first component
        self.assertEqual(appointment.appointment_id, "FILL456")

    def test_invalid_message_type_caught(self):
        """
        Test that ADT, ORU, and other message types are rejected.

        Only SIU^S12 is supported. Other types should fail explicitly
        so callers know they sent the wrong message type.
        """
        # ADT message (Admit/Discharge/Transfer)
        adt_message = """MSH|^~\\&|S|F|R|F|20250502||ADT^A01|1|P|2.5
PID|1||P12345||Doe^John"""

        with self.assertRaises(InvalidMessageTypeError) as ctx:
            parse_hl7_message(adt_message)

        self.assertEqual(ctx.exception.expected, "SIU^S12")
        self.assertEqual(ctx.exception.actual, "ADT^A01")

        # ORU message (Observation Result)
        oru_message = """MSH|^~\\&|S|F|R|F|20250502||ORU^R01|1|P|2.5
PID|1||P12345||Doe^John"""

        with self.assertRaises(InvalidMessageTypeError):
            parse_hl7_message(oru_message)

    def test_various_line_ending_formats(self):
        """
        Test handling of different line endings.

        HL7 spec says \\r but real files have \\n, \\r\\n, or mixed.
        Had to deal with this a lot from different EMR systems.
        """
        # Unix line endings
        unix_msg = "MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5\nSCH|1|2|||||||Loc||20250502130000\nPID|1||P1||Doe^John"
        appt1 = parse_hl7_message(unix_msg)
        self.assertEqual(appt1.patient.last_name, "Doe")

        # Windows line endings
        win_msg = "MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5\r\nSCH|1|2|||||||Loc||20250502130000\r\nPID|1||P1||Doe^John"
        appt2 = parse_hl7_message(win_msg)
        self.assertEqual(appt2.patient.last_name, "Doe")

        # Classic HL7 (carriage return only)
        cr_msg = "MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5\rSCH|1|2|||||||Loc||20250502130000\rPID|1||P1||Doe^John"
        appt3 = parse_hl7_message(cr_msg)
        self.assertEqual(appt3.patient.last_name, "Doe")

    def test_timestamp_edge_cases(self):
        """
        Test various timestamp formats found in the wild.

        HL7 timestamps are surprisingly inconsistent across systems.
        """
        # Date only (no time) - should default to midnight
        msg1 = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502
PID|1||P1||Doe^John"""
        appt1 = parse_hl7_message(msg1)
        self.assertEqual(appt1.appointment_datetime, "2025-05-02T00:00:00Z")

        # With timezone offset (should still work)
        msg2 = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502130000-0500
PID|1||P1||Doe^John"""
        appt2 = parse_hl7_message(msg2)
        # Timezone is stripped for simplicity (documented tradeoff)
        self.assertEqual(appt2.appointment_datetime, "2025-05-02T13:00:00Z")

    def test_gender_normalization(self):
        """
        Test that gender values are normalized correctly.

        Should handle M, F, O, U and map unknown values to U.
        """
        # Standard male
        msg_m = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502130000
PID|1||P1||Doe^John||19850210|M"""
        self.assertEqual(parse_hl7_message(msg_m).patient.gender, "M")

        # Standard female
        msg_f = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502130000
PID|1||P1||Doe^Jane||19850210|F"""
        self.assertEqual(parse_hl7_message(msg_f).patient.gender, "F")

        # Other
        msg_o = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502130000
PID|1||P1||Doe^Pat||19850210|O"""
        self.assertEqual(parse_hl7_message(msg_o).patient.gender, "O")

        # Unknown value should map to U
        msg_x = """MSH|^~\\&|S|F|R|F|20250502||SIU^S12|1|P|2.5
SCH|1|2|||||||Loc||20250502130000
PID|1||P1||Doe^Alex||19850210|X"""
        self.assertEqual(parse_hl7_message(msg_x).patient.gender, "U")


if __name__ == "__main__":
    unittest.main()
