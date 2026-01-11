"""
HL7 Segment Parsers

This module contains functions to parse individual HL7 segments.
Each segment (MSH, SCH, PID, PV1) has its own parser function that
extracts relevant fields and handles missing/empty data gracefully.

HL7 Message Structure Basics:
- Segments are separated by carriage returns (\r) or newlines (\n)
- Fields within a segment are separated by pipes (|)
- Components within a field are separated by carets (^)
- First field after segment name is field 1 (except MSH where | is field 1)

Note: HL7 "standards" are more like guidelines.
Different EMR systems have quirks, so defensive parsing is essential.
"""

from typing import Optional, List
from datetime import datetime

from .exceptions import MalformedSegmentError


def safe_get_field(fields: List[str], index: int, default: str = "") -> str:
    """
    Safely get a field from a list of fields.

    HL7 messages often have missing fields at the end of segments.
    This function returns an empty string if the field doesn't exist.

    Args:
        fields: List of field values from a segment
        index: Zero-based index of the field to get
        default: Value to return if field is missing or empty

    Returns:
        The field value or default if not found

    Example:
        fields = ["PID", "", "P12345"]
        safe_get_field(fields, 2)  # Returns "P12345"
        safe_get_field(fields, 10)  # Returns "" (index out of range)
    """
    if index < len(fields):
        value = fields[index].strip()
        return value if value else default
    return default


def safe_get_component(field: str, index: int, component_separator: str = "^") -> str:
    """
    Safely get a component from a field.

    Fields in HL7 can have multiple components separated by ^.
    For example, a name field might be: "Doe^John^Middle"

    Args:
        field: The field value potentially containing components
        index: Zero-based index of the component to get
        component_separator: Character separating components (default ^)

    Returns:
        The component value or empty string if not found

    Example:
        field = "Doe^John^M"
        safe_get_component(field, 0)  # Returns "Doe"
        safe_get_component(field, 1)  # Returns "John"
    """
    if not field:
        return ""

    components = field.split(component_separator)
    if index < len(components):
        return components[index].strip()
    return ""


def parse_hl7_timestamp(timestamp: str) -> Optional[str]:
    """
    Convert HL7 timestamp to ISO 8601 format.

    HL7 timestamps can have various formats:
    - YYYYMMDD (date only)
    - YYYYMMDDHHMM (date and time to minute)
    - YYYYMMDDHHMMSS (date and time to second)
    - May include timezone offset

    Args:
        timestamp: HL7 formatted timestamp string

    Returns:
        ISO 8601 formatted string (YYYY-MM-DDTHH:MM:SSZ) or None if invalid

    Examples:
        parse_hl7_timestamp("20250502130000")  # Returns "2025-05-02T13:00:00Z"
        parse_hl7_timestamp("20250502")         # Returns "2025-05-02T00:00:00Z"
    """
    if not timestamp:
        return None

    # Remove any timezone info for simplicity (e.g., +0000 or -0500)
    # Keep only the numeric part
    clean_timestamp = ""
    for char in timestamp:
        if char.isdigit():
            clean_timestamp += char
        elif char in ["+", "-"] and len(clean_timestamp) >= 8:
            # Timezone indicator - stop here
            break

    if len(clean_timestamp) < 8:
        return None  # Not enough digits for a valid date

    try:
        # Parse based on length of timestamp
        year = clean_timestamp[0:4]
        month = clean_timestamp[4:6]
        day = clean_timestamp[6:8]

        # Default time values
        hour = "00"
        minute = "00"
        second = "00"

        # Extract time if present
        if len(clean_timestamp) >= 10:
            hour = clean_timestamp[8:10]
        if len(clean_timestamp) >= 12:
            minute = clean_timestamp[10:12]
        if len(clean_timestamp) >= 14:
            second = clean_timestamp[12:14]

        # Validate by creating a datetime object
        datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))

        # Return ISO 8601 format
        return f"{year}-{month}-{day}T{hour}:{minute}:{second}Z"

    except (ValueError, IndexError):
        return None


def parse_hl7_date(date_str: str) -> Optional[str]:
    """
    Convert HL7 date to YYYY-MM-DD format.

    Used primarily for dates like date of birth.

    Args:
        date_str: HL7 formatted date (YYYYMMDD)

    Returns:
        Date string in YYYY-MM-DD format or None if invalid

    Example:
        parse_hl7_date("19850210")  # Returns "1985-02-10"
    """
    if not date_str:
        return None

    # Extract only digits
    clean_date = "".join(char for char in date_str if char.isdigit())

    if len(clean_date) < 8:
        return None

    try:
        year = clean_date[0:4]
        month = clean_date[4:6]
        day = clean_date[6:8]

        # Validate the date
        datetime(int(year), int(month), int(day))

        return f"{year}-{month}-{day}"

    except (ValueError, IndexError):
        return None


def parse_msh_segment(segment: str) -> dict:
    """
    Parse MSH (Message Header) segment.

    The MSH segment is special in HL7:
    - Field 1 is the field separator itself (|)
    - Field 2 contains encoding characters (^~\\&)
    - When splitting by |, index 1 is actually field 2

    Important MSH fields:
    - MSH-9: Message Type (e.g., SIU^S12)
    - MSH-10: Message Control ID
    - MSH-7: Message DateTime

    The field separator (|) is MSH-1, so MSH-9 is at index 8 after splitting.

    Args:
        segment: The full MSH segment string

    Returns:
        Dictionary with message type and control ID

    Raises:
        MalformedSegmentError: If the segment doesn't start with "MSH|"

    Example:
        segment = "MSH|^~\\&|SENDER|FACILITY|RECEIVER|DEST|20250502|...|SIU^S12|12345|..."
        result = parse_msh_segment(segment)
        # result["message_type"] = "SIU^S12"
    """
    if not segment.startswith("MSH|"):
        raise MalformedSegmentError(
            "MSH", f"Segment must start with 'MSH|', got: {segment[:20]}..."
        )

    # Split the segment by pipe
    fields = segment.split("|")

    # For MSH, the first | is field 1, so indexing needs adjustment
    # MSH|^~\&|...|message_type|...
    # idx: 0  1   2      8
    # But MSH fields are numbered: 1=|, 2=^~\&, 3=sending_app, etc.
    # So MSH-9 (message type) is at index 8 in zero-based array

    result = {
        "field_separator": "|",
        "encoding_characters": safe_get_field(fields, 1, "^~\\&"),
        "sending_application": safe_get_field(fields, 2),
        "sending_facility": safe_get_field(fields, 3),
        "message_datetime": safe_get_field(fields, 6),
        "message_type": safe_get_field(fields, 8),
        "message_control_id": safe_get_field(fields, 9),
    }

    return result


def parse_sch_segment(segment: str) -> dict:
    """
    Parse SCH (Scheduling Activity Information) segment.

    The SCH segment contains appointment-specific information:
    - SCH-1: Placer Appointment ID (the requesting system's ID)
    - SCH-2: Filler Appointment ID (the scheduling system's ID)
    - SCH-6: Event Reason
    - SCH-7: Appointment Reason
    - SCH-9: Appointment Duration / Location info (varies by implementation)
    - SCH-11: Appointment Timing Quantity (contains start datetime)

    The datetime can be in SCH-10 or SCH-11 depending on the HL7 version
    and the sending system. Both are checked to be safe.

    Args:
        segment: The full SCH segment string

    Returns:
        Dictionary with appointment details

    Raises:
        MalformedSegmentError: If the segment doesn't start with "SCH|"

    Example:
        segment = "SCH|123456|456789|...|Consultation|...|...|...|20250502130000|..."
    """
    if not segment.startswith("SCH|"):
        raise MalformedSegmentError(
            "SCH", f"Segment must start with 'SCH|', got: {segment[:20]}..."
        )

    fields = segment.split("|")

    # Get appointment ID - prefer filler ID (SCH-2), fall back to placer (SCH-1)
    # Filler ID is usually more reliable since it's from the actual scheduling system
    placer_id = safe_get_field(fields, 1)
    filler_id = safe_get_field(fields, 2)
    appointment_id = filler_id if filler_id else placer_id

    # If IDs have components (like 12345^SYSTEM^ISO), get just the actual ID
    if "^" in appointment_id:
        appointment_id = safe_get_component(appointment_id, 0)

    # Get appointment reason - can be in SCH-6 or SCH-7 depending on system
    # SCH-6 is "Event Reason", SCH-7 is "Appointment Reason" - try both
    reason_field = safe_get_field(fields, 6)
    if not reason_field:
        reason_field = safe_get_field(fields, 7)

    # Reason might have components like "CODE^Description" - the description is extracted
    reason = (
        safe_get_component(reason_field, 1) if "^" in reason_field else reason_field
    )

    # Get appointment timing (SCH-10 or SCH-11) - contains start/end datetime
    # Field usage varies across HL7 implementations
    def get_start_datetime(timing_field):
        """Extract datetime from timing field - handles various formats."""
        if not timing_field:
            return ""
        # Timing can be like "20250502130000^20250502140000" (start^end)
        # or just a single datetime, or have other components
        components = timing_field.split("^")
        for component in components:
            component = component.strip()
            # Identify numeric strings with 8+ digits that could represent dates
            if component and len(component) >= 8 and component.isdigit():
                return component
        return ""

    # Try SCH-10 first
    start_datetime = get_start_datetime(safe_get_field(fields, 10))
    if not start_datetime:
        # Fallback to SCH-11
        start_datetime = get_start_datetime(safe_get_field(fields, 11))

    # If still no datetime found, try the whole field as fallback
    if not start_datetime:
        timing_field = safe_get_field(fields, 11)
        if timing_field:
            start_datetime = timing_field.split("^")[0].strip()

    # Get location info (often in SCH-9 or other fields)
    location = safe_get_field(fields, 9)
    if "^" in location:
        location = safe_get_component(location, 0)

    result = {
        "appointment_id": appointment_id,
        "appointment_datetime_raw": start_datetime,
        "appointment_datetime": parse_hl7_timestamp(start_datetime),
        "reason": reason if reason else None,
        "location": location if location else None,
    }

    return result


def parse_pid_segment(segment: str) -> dict:
    """
    Parse PID (Patient Identification) segment.

    The PID segment contains patient demographics:
    - PID-3: Patient ID (may have multiple components like ID^check_digit^system)
    - PID-5: Patient Name (LastName^FirstName^MiddleName^Suffix^Prefix)
    - PID-7: Date of Birth
    - PID-8: Gender (M, F, O, U)

    Name components are consistently ordered as Last^First^Middle.

    Args:
        segment: The full PID segment string

    Returns:
        Dictionary with patient information

    Raises:
        MalformedSegmentError: If the segment doesn't start with "PID|"

    Example:
        segment = "PID|1||P12345||Doe^John^M||19850210|M|..."
    """
    if not segment.startswith("PID|"):
        raise MalformedSegmentError(
            "PID", f"Segment must start with 'PID|', got: {segment[:20]}..."
        )

    fields = segment.split("|")

    # PID-3: Patient ID (index 3)
    # Can be complex: ID^check_digit^code_system^...
    patient_id_field = safe_get_field(fields, 3)
    patient_id = safe_get_component(patient_id_field, 0) if patient_id_field else ""

    # PID-5: Patient Name (index 5)
    # Format: LastName^FirstName^MiddleName^Suffix^Prefix
    name_field = safe_get_field(fields, 5)
    last_name = safe_get_component(name_field, 0)
    first_name = safe_get_component(name_field, 1)

    # PID-7: Date of Birth (index 7)
    dob_raw = safe_get_field(fields, 7)
    dob = parse_hl7_date(dob_raw)

    # PID-8: Gender (index 8)
    gender = safe_get_field(fields, 8)
    # Normalize gender to single character
    if gender:
        gender = gender[0].upper()
        if gender not in ["M", "F", "O", "U"]:
            gender = "U"  # Unknown for unrecognized values

    result = {
        "patient_id": patient_id,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "gender": gender if gender else None,
    }

    return result


def parse_pv1_segment(segment: str) -> dict:
    """
    Parse PV1 (Patient Visit) segment.

    The PV1 segment contains visit/encounter information:
    - PV1-3: Assigned Patient Location (Point^Room^Bed^Facility^...)
    - PV1-7: Attending Doctor (ID^LastName^FirstName^...)
    - PV1-17: Admitting Doctor (backup for provider)

    Provider fields can have multiple components. The format is usually:
    ID^LastName^FirstName^MiddleName^Suffix^Prefix

    Provider information may appear in PV1-7 (attending doctor) or PV1-17 (admitting doctor).
    This parser checks both fields, prioritizing PV1-7.

    Args:
        segment: The full PV1 segment string

    Returns:
        Dictionary with provider and location information

    Raises:
        MalformedSegmentError: If the segment doesn't start with "PV1|"

    Example:
        segment = "PV1|1|O|ClinicA^Room203||...|D67890^Smith^Dr||..."
    """
    if not segment.startswith("PV1|"):
        raise MalformedSegmentError(
            "PV1", f"Segment must start with 'PV1|', got: {segment[:20]}..."
        )

    fields = segment.split("|")

    # PV1-3: Patient Location (index 3)
    # Format can be: Point^Room^Bed^Facility^...
    location_field = safe_get_field(fields, 3)
    if location_field:
        # Try to build a readable location string
        location_parts = location_field.split("^")
        # Filter out empty parts and join with spaces
        location_parts = [p for p in location_parts if p.strip()]
        location = " ".join(location_parts) if location_parts else None
    else:
        location = None

    # PV1-7: Attending Doctor (index 7)
    # Format: ID^LastName^FirstName^MiddleName^...
    attending_field = safe_get_field(fields, 7)

    # PV1-17: Admitting Doctor (index 17) - fallback
    admitting_field = safe_get_field(fields, 17)

    # Use attending doctor if available, otherwise admitting
    provider_field = attending_field if attending_field else admitting_field

    provider_id = ""
    provider_name = ""

    if provider_field:
        provider_id = safe_get_component(provider_field, 0)
        last_name = safe_get_component(provider_field, 1)
        first_name = safe_get_component(provider_field, 2)

        # Build provider name
        if first_name and last_name:
            provider_name = f"{first_name} {last_name}"
        elif last_name:
            provider_name = last_name
        elif first_name:
            provider_name = first_name

    result = {
        "provider_id": provider_id,
        "provider_name": provider_name,
        "location": location,
    }

    return result


def split_message_into_segments(message: str) -> List[str]:
    """
    Split an HL7 message into individual segments.

    HL7 segments are separated by carriage return (\r),
    but files might also use \n or \r\n.

    Args:
        message: The raw HL7 message string

    Returns:
        List of segment strings

    Example:
        message = "MSH|...\rPID|...\rPV1|..."
        segments = split_message_into_segments(message)
        # Returns ["MSH|...", "PID|...", "PV1|..."]
    """
    # Normalize line endings - replace \r\n with \r, then \n with \r
    normalized = message.replace("\r\n", "\r").replace("\n", "\r")

    # Split by \r and filter out empty lines
    segments = [seg.strip() for seg in normalized.split("\r") if seg.strip()]

    return segments


def get_segment(segments: List[str], segment_name: str) -> Optional[str]:
    """
    Find a specific segment by its name (first 3 characters).

    Args:
        segments: List of segment strings
        segment_name: The segment type to find (e.g., "MSH", "PID")

    Returns:
        The full segment string or None if not found

    Example:
        segments = ["MSH|...", "PID|1||P123||Doe^John", "PV1|..."]
        pid_segment = get_segment(segments, "PID")
        # Returns "PID|1||P123||Doe^John"
    """
    for segment in segments:
        # Check if segment starts with the segment name followed by |
        if segment.startswith(segment_name + "|") or segment == segment_name:
            return segment
    return None


def get_all_segments(segments: List[str], segment_name: str) -> List[str]:
    """
    Find all segments of a specific type.

    Some segments can repeat (like OBX). This function
    returns all instances of a segment type.

    Args:
        segments: List of segment strings
        segment_name: The segment type to find

    Returns:
        List of matching segment strings (may be empty)
    """
    result = []
    for segment in segments:
        if segment.startswith(segment_name + "|") or segment == segment_name:
            result.append(segment)
    return result
