"""
Custom Exceptions for HL7 Parser

This module defines specific exceptions for different error scenarios
that can occur during HL7 message parsing. Clear error messages help
with debugging and understanding what went wrong.
"""


class HL7ParserError(Exception):
    """
    Base exception for all HL7 parsing errors.
    All other exceptions inherit from this one.
    """

    pass


class InvalidMessageTypeError(HL7ParserError):
    """
    Raised when the message type is not SIU^S12.

    Example: If an ADT message is received instead of SIU,
    this error is raised because only SIU S12 messages are handled.
    """

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        message = f"Invalid message type. Expected '{expected}', got '{actual}'"
        super().__init__(message)


class MissingSegmentError(HL7ParserError):
    """
    Raised when a required segment is missing from the message.

    Example: If MSH segment is missing, the message cannot be validated.
    """

    def __init__(self, segment_name: str):
        self.segment_name = segment_name
        message = f"Required segment '{segment_name}' is missing from the message"
        super().__init__(message)


class MalformedSegmentError(HL7ParserError):
    """
    Raised when a segment cannot be parsed properly.

    Example: If a segment doesn't have enough fields or has
    unexpected formatting.
    """

    def __init__(self, segment_name: str, reason: str):
        self.segment_name = segment_name
        self.reason = reason
        message = f"Malformed segment '{segment_name}': {reason}"
        super().__init__(message)


class InvalidHL7FormatError(HL7ParserError):
    """
    Raised when the input doesn't conform to basic HL7 format.

    Example: If the message doesn't start with MSH or
    doesn't have proper delimiters.
    """

    def __init__(self, reason: str):
        self.reason = reason
        message = f"Invalid HL7 format: {reason}"
        super().__init__(message)
