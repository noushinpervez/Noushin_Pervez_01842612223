"""
HL7 SIU S12 Message Parser

This is the main parser module that coordinates parsing of HL7 SIU S12
messages. It combines the segment parsers and domain models to produce
structured appointment data.

The flow is:
1. Read file or accept message string
2. Split into individual messages (files can have multiple)
3. For each message:
   a. Split into segments
   b. Validate it's an SIU^S12 message
   c. Parse MSH, SCH, PID, PV1 segments
   d. Build Appointment object
4. Return list of appointments

Usage:
    from hl7_parser import parse_hl7_file, parse_hl7_message

    # Parse a file with one or more messages
    appointments = parse_hl7_file("appointments.hl7")

    # Parse a single message string
    appointment = parse_hl7_message(message_text)
"""

from typing import List, Iterator
import json

from .models import Patient, Provider, Appointment
from .exceptions import (
    HL7ParserError,
    InvalidMessageTypeError,
    MissingSegmentError,
    MalformedSegmentError,
    InvalidHL7FormatError,
)
from .segment_parsers import (
    split_message_into_segments,
    get_segment,
    parse_msh_segment,
    parse_sch_segment,
    parse_pid_segment,
    parse_pv1_segment,
)


# Supported message type
SUPPORTED_MESSAGE_TYPE = "SIU^S12"


def validate_message_type(msh_data: dict) -> None:
    """
    Validate that the message is an SIU^S12 message.

    Only SIU (Scheduling Information Unsolicited) messages
    with trigger event S12 (New Appointment Notification) are supported.

    Args:
        msh_data: Parsed MSH segment data

    Raises:
        InvalidMessageTypeError: If message type is not SIU^S12
    """
    message_type = msh_data.get("message_type", "")

    # Handle different formats of message type
    # Could be "SIU^S12", "SIU^S12^SIU_S12", or variations
    type_parts = message_type.split("^")

    if len(type_parts) >= 2:
        msg_type = type_parts[0].upper()
        trigger_event = type_parts[1].upper()
        full_type = f"{msg_type}^{trigger_event}"
    else:
        full_type = message_type.upper()

    if not full_type.startswith("SIU^S12"):
        raise InvalidMessageTypeError(SUPPORTED_MESSAGE_TYPE, message_type)


def parse_single_message(message: str) -> Appointment:
    """
    Parse a single HL7 SIU S12 message into an Appointment object.

    This function:
    1. Splits the message into segments
    2. Validates it's an SIU^S12 message
    3. Extracts data from MSH, SCH, PID, and PV1 segments
    4. Creates and returns an Appointment object

    Args:
        message: Raw HL7 message string

    Returns:
        Appointment object with parsed data

    Raises:
        InvalidHL7FormatError: If message format is invalid
        InvalidMessageTypeError: If message is not SIU^S12
        MissingSegmentError: If required segments are missing
    """
    # Split message into segments
    segments = split_message_into_segments(message)

    if not segments:
        raise InvalidHL7FormatError("Message is empty or contains no segments")

    # ----- Parse MSH Segment -----
    msh_segment = get_segment(segments, "MSH")
    if not msh_segment:
        raise MissingSegmentError("MSH")

    msh_data = parse_msh_segment(msh_segment)

    # Validate message type
    validate_message_type(msh_data)

    # ----- Parse SCH Segment (Required for appointment info) -----
    sch_segment = get_segment(segments, "SCH")

    # SCH is required for appointment data
    if not sch_segment:
        raise MissingSegmentError("SCH")

    sch_data = parse_sch_segment(sch_segment)

    # Validate that minimum required appointment data is present
    if not sch_data.get("appointment_id"):
        raise MalformedSegmentError("SCH", "Missing appointment ID")

    if not sch_data.get("appointment_datetime"):
        raise MalformedSegmentError("SCH", "Missing or invalid appointment datetime")

    # ----- Parse PID Segment -----
    pid_segment = get_segment(segments, "PID")
    patient = None

    if pid_segment:
        pid_data = parse_pid_segment(pid_segment)

        # Only create Patient if at least an ID or name is present
        if pid_data.get("patient_id") or pid_data.get("last_name"):
            patient = Patient(
                id=pid_data.get("patient_id", "UNKNOWN"),
                first_name=pid_data.get("first_name", ""),
                last_name=pid_data.get("last_name", ""),
                dob=pid_data.get("dob"),
                gender=pid_data.get("gender"),
            )

    # ----- Parse PV1 Segment (Optional) -----
    pv1_segment = get_segment(segments, "PV1")
    provider = None
    pv1_location = None

    if pv1_segment:
        pv1_data = parse_pv1_segment(pv1_segment)

        # Extract provider if ID or name is present
        if pv1_data.get("provider_id") or pv1_data.get("provider_name"):
            provider = Provider(
                id=pv1_data.get("provider_id", "UNKNOWN"),
                name=pv1_data.get("provider_name", "Unknown Provider"),
            )

        # Save location from PV1 as backup
        pv1_location = pv1_data.get("location")

    # ----- Build Appointment Object -----
    # Use SCH location first, fall back to PV1 location
    location = sch_data.get("location") or pv1_location

    appointment = Appointment(
        appointment_id=sch_data["appointment_id"],
        appointment_datetime=sch_data["appointment_datetime"],
        patient=patient,
        provider=provider,
        location=location,
        reason=sch_data.get("reason"),
    )

    return appointment


def split_hl7_file_into_messages(content: str) -> List[str]:
    """
    Split file content into individual HL7 messages.

    Multiple HL7 messages in a file are typically separated by:
    - Blank lines
    - Each message starts with "MSH|"

    Args:
        content: Raw file content

    Returns:
        List of individual message strings
    """
    messages = []
    current_message_lines = []

    # Normalize line endings
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    for line in lines:
        stripped_line = line.strip()

        # Skip empty lines between messages
        if not stripped_line:
            # If lines have been accumulated, this might be end of a message
            if current_message_lines:
                message = "\n".join(current_message_lines)
                messages.append(message)
                current_message_lines = []
            continue

        # If line starts with MSH, it's a new message
        if stripped_line.startswith("MSH|"):
            # Save previous message if exists
            if current_message_lines:
                message = "\n".join(current_message_lines)
                messages.append(message)
                current_message_lines = []

        # Add line to current message
        current_message_lines.append(stripped_line)

    # Last message
    if current_message_lines:
        message = "\n".join(current_message_lines)
        messages.append(message)

    return messages


def parse_hl7_message(message: str) -> Appointment:
    """
    Parse a single HL7 SIU S12 message string.

    This is a convenience function that wraps parse_single_message
    with additional input validation.

    Args:
        message: Raw HL7 message string

    Returns:
        Appointment object

    Raises:
        InvalidHL7FormatError: If message format is invalid
        InvalidMessageTypeError: If not an SIU^S12 message
        MissingSegmentError: If required segments missing
        MalformedSegmentError: If segment data is invalid

    Example:
        message = '''
        MSH|^~\\&|SENDER|FAC|REC|FAC|20250502130000||SIU^S12|123|P|2.5
        SCH|1||||||Checkup||||20250502130000
        PID|||P12345||Doe^John||19850210|M
        PV1||O|||||||D67890^Smith^Dr
        '''
        appointment = parse_hl7_message(message)
    """
    if not message or not message.strip():
        raise InvalidHL7FormatError("Message is empty")

    return parse_single_message(message.strip())


def parse_hl7_file(file_path: str) -> List[Appointment]:
    """
    Parse an HL7 file containing one or more SIU S12 messages.

    This function:
    1. Reads the file from disk
    2. Splits it into individual messages
    3. Parses each message
    4. Returns list of Appointment objects

    Args:
        file_path: Path to the .hl7 file

    Returns:
        List of Appointment objects (one per valid message)

    Raises:
        FileNotFoundError: If file doesn't exist
        InvalidHL7FormatError: If file contains no valid messages
        Various parsing errors for invalid messages

    Example:
        appointments = parse_hl7_file("appointments.hl7")
        for appt in appointments:
            print(appt.to_json())
    """
    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        raise InvalidHL7FormatError("File is empty")

    # Split into individual messages
    raw_messages = split_hl7_file_into_messages(content)

    if not raw_messages:
        raise InvalidHL7FormatError("No HL7 messages found in file")

    # Parse each message
    appointments = []
    errors = []

    for i, raw_message in enumerate(raw_messages, start=1):
        try:
            appointment = parse_single_message(raw_message)
            appointments.append(appointment)
        except HL7ParserError as e:
            # Record error but continue parsing other messages
            errors.append(f"Message {i}: {str(e)}")

    # If no messages were parsed successfully, raise error
    if not appointments and errors:
        raise InvalidHL7FormatError(
            f"No valid SIU^S12 messages found. Errors: {'; '.join(errors)}"
        )

    return appointments


def parse_hl7_file_with_errors(file_path: str) -> tuple:
    """
    Parse an HL7 file and return both successes and errors.

    Unlike parse_hl7_file, this function doesn't raise an error
    if some messages fail to parse. Instead, it returns both
    the successful appointments and the error messages.

    Args:
        file_path: Path to the .hl7 file

    Returns:
        Tuple of (appointments, errors) where:
        - appointments: List of successfully parsed Appointment objects
        - errors: List of error messages for failed parses

    Example:
        appointments, errors = parse_hl7_file_with_errors("data.hl7")
        print(f"Parsed {len(appointments)} appointments")
        if errors:
            print(f"Encountered {len(errors)} errors")
    """
    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        return [], ["File is empty"]

    # Split into individual messages
    raw_messages = split_hl7_file_into_messages(content)

    if not raw_messages:
        return [], ["No HL7 messages found in file"]

    # Parse each message
    appointments = []
    errors = []

    for i, raw_message in enumerate(raw_messages, start=1):
        try:
            appointment = parse_single_message(raw_message)
            appointments.append(appointment)
        except HL7ParserError as e:
            errors.append(f"Message {i}: {str(e)}")

    return appointments, errors


def parse_hl7_file_streaming(
    file_path: str, continue_on_error: bool = False
) -> Iterator[Appointment]:
    """
    Parse an HL7 file using streaming (memory-efficient for large files).

    This function reads the file line by line and processes messages as they
    are encountered, rather than loading the entire file into memory first.
    This is more memory-efficient for large HL7 files.

    Args:
        file_path: Path to the .hl7 file
        continue_on_error: If True, continue parsing other messages when one fails

    Yields:
        Appointment objects as they are parsed

    Raises:
        FileNotFoundError: If file doesn't exist
        HL7ParserError: If parsing fails and continue_on_error is False

    Example:
        for appointment in parse_hl7_file_streaming("large_file.hl7"):
            print(appointment.to_json())
    """
    current_message_lines = []
    message_count = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            # Normalize line endings
            line = line.rstrip("\r\n")

            # Check if this is the start of a new message
            if line.startswith("MSH|") and current_message_lines:
                # Process the previous complete message
                message_count += 1
                message = "\n".join(current_message_lines)
                try:
                    appointment = parse_single_message(message)
                    yield appointment
                except HL7ParserError as e:
                    if not continue_on_error:
                        raise HL7ParserError(
                            f"Message {message_count}: {str(e)}"
                        ) from e
                    # If continue_on_error, skip this message

                # Reset for next message
                current_message_lines = []

            # Add non-empty lines to current message
            if line.strip():
                current_message_lines.append(line)

        # Process the last message if any
        if current_message_lines:
            message_count += 1
            message = "\n".join(current_message_lines)
            try:
                appointment = parse_single_message(message)
                yield appointment
            except HL7ParserError as e:
                if not continue_on_error:
                    raise HL7ParserError(f"Message {message_count}: {str(e)}") from e


def appointments_to_json(appointments: List[Appointment], indent: int = 2) -> str:
    """
    Convert a list of appointments to JSON string.

    Args:
        appointments: List of Appointment objects
        indent: JSON indentation level (default 2)

    Returns:
        JSON string representation
    """
    return json.dumps([appt.to_dict() for appt in appointments], indent=indent)
