"""
Domain Models for HL7 SIU Appointment Parser

The module contains simple data classes that represent the structured
output of our HL7 parser. These models define the shape of our JSON output.
"""

from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class Patient:
    """
    Represents patient information extracted from PID segment.

    Attributes:
        id: Patient identifier (PID-3)
        first_name: Patient's first name (PID-5)
        last_name: Patient's last name (PID-5)
        dob: Date of birth in YYYY-MM-DD format (PID-7)
        gender: Gender code M/F/O/U (PID-8)
    """

    id: str
    first_name: str
    last_name: str
    dob: Optional[str] = None
    gender: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert patient to dictionary, excluding None values."""
        result = {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }
        if self.dob is not None:
            result["dob"] = self.dob
        if self.gender is not None:
            result["gender"] = self.gender
        return result


@dataclass
class Provider:
    """
    Represents provider/clinician information extracted from PV1 segment.

    Attributes:
        id: Provider identifier (PV1-7 or PV1-17)
        name: Provider's name
    """

    id: str
    name: str

    def to_dict(self) -> dict:
        """Convert provider to dictionary."""
        return {"id": self.id, "name": self.name}


@dataclass
class Appointment:
    """
    Represents a scheduled appointment extracted from SIU S12 message.

    This is the main output model that combines data from multiple
    HL7 segments (MSH, SCH, PID, PV1).

    Attributes:
        appointment_id: Unique appointment identifier (SCH-1 or SCH-2)
        appointment_datetime: ISO 8601 formatted datetime (SCH-11)
        patient: Patient information from PID segment
        provider: Provider information from PV1 segment
        location: Appointment location (SCH-9 or PV1-3)
        reason: Reason for appointment (SCH-7)
    """

    appointment_id: str
    appointment_datetime: str
    patient: Optional[Patient] = None
    provider: Optional[Provider] = None
    location: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Convert appointment to dictionary suitable for JSON output.
        Only includes fields that have values.
        """
        result = {
            "appointment_id": self.appointment_id,
            "appointment_datetime": self.appointment_datetime,
        }

        if self.patient is not None:
            result["patient"] = self.patient.to_dict()

        if self.provider is not None:
            result["provider"] = self.provider.to_dict()

        if self.location is not None:
            result["location"] = self.location

        if self.reason is not None:
            result["reason"] = self.reason

        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert appointment to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
