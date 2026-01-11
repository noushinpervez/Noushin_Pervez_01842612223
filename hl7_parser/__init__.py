"""
HL7 SIU S12 Appointment Parser

A Python module for parsing HL7 v2.x SIU S12 (Scheduling Information Unsolicited)
messages and converting them to structured JSON format.

Example usage:
    from hl7_parser import parse_hl7_file, parse_hl7_message

    # Parse a file
    appointments = parse_hl7_file("appointments.hl7")

    # Parse a single message
    appointment = parse_hl7_message(message_text)
    print(appointment.to_json())
"""

from .parser import (
    parse_hl7_file,
    parse_hl7_message,
    parse_hl7_file_with_errors,
    parse_hl7_file_streaming,
    appointments_to_json,
)

from .models import Patient, Provider, Appointment

from .exceptions import (
    HL7ParserError,
    InvalidMessageTypeError,
    MissingSegmentError,
    MalformedSegmentError,
    InvalidHL7FormatError,
)

__all__ = [
    # Main parsing functions
    "parse_hl7_file",
    "parse_hl7_message",
    "parse_hl7_file_with_errors",
    "parse_hl7_file_streaming",
    "appointments_to_json",
    # Domain models
    "Patient",
    "Provider",
    "Appointment",
    # Exceptions
    "HL7ParserError",
    "InvalidMessageTypeError",
    "MissingSegmentError",
    "MalformedSegmentError",
    "InvalidHL7FormatError",
]

__version__ = "1.0.0"
