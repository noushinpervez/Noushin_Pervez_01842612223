#!/usr/bin/env python3
"""
HL7 SIU S12 Appointment Parser - Command Line Interface

This script provides a command-line interface for parsing HL7 files
and outputting JSON-formatted appointment data.

Usage:
    python hl7_parser_cli.py input.hl7
    python hl7_parser_cli.py input.hl7 -o output.json
    python hl7_parser_cli.py input.hl7 --pretty
"""

import argparse
import sys
import json
from pathlib import Path

# Add parent directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

from hl7_parser import (
    parse_hl7_file,
    parse_hl7_file_with_errors,
    parse_hl7_file_streaming,
    appointments_to_json,
    HL7ParserError,
)


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser.

    Returns:
        Configured ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="Parse HL7 SIU S12 messages and convert to JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s appointments.hl7
      Parse file and print JSON to stdout

  %(prog)s appointments.hl7 -o result.json
      Parse file and save JSON to result.json

  %(prog)s appointments.hl7 -v
      Parse file with detailed output

  %(prog)s appointments.hl7 -e
      Continue parsing even if some messages fail

  %(prog)s appointments.hl7 -s
      Memory-efficient streaming for large files (JSON Lines format)

  %(prog)s appointments.hl7 -d
      Show errors/warnings and output together
        """,
    )

    # Required argument: input file
    parser.add_argument("input_file", type=str, help="Path to the HL7 file to parse")

    # Optional argument: output file
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        dest="output_file",
        help="Path to save JSON output (default: print to stdout)",
    )

    # Optional flag: compact output
    parser.add_argument(
        "-c",
        "--compact",
        action="store_true",
        help="Output compact JSON without indentation",
    )

    # Optional flag: verbose output
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output including parsing details",
    )

    # Optional flag: continue on error
    parser.add_argument(
        "-e",
        "--continue-on-error",
        action="store_true",
        dest="continue_on_error",
        help="Continue parsing remaining messages if one fails",
    )

    # Optional flag: streaming mode
    parser.add_argument(
        "-s",
        "--streaming",
        action="store_true",
        help="Use streaming mode for memory-efficient parsing of large files (outputs JSON Lines format)",
    )

    # Optional flag: debug mode
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show both errors/warnings and output data together in a single stream",
    )

    return parser


def print_verbose(message: str, verbose: bool, debug: bool = False) -> None:
    """Print message only if verbose mode is enabled."""
    if verbose:
        if debug:
            print(f"[INFO] {message}")
        else:
            print(f"[INFO] {message}", file=sys.stderr)


def print_error(message: str, debug: bool = False, verbose: bool = False) -> None:
    """Print error message to stderr, or stdout in debug mode, or also when verbose."""
    if debug:
        print(f"[ERROR] {message}")
    elif verbose:
        print(f"[ERROR] {message}", file=sys.stderr)
    else:
        print(f"[ERROR] {message}", file=sys.stderr)


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse command-line arguments
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input_file)
    if not input_path.exists():
        print_error(f"File not found: {args.input_file}", args.debug, args.verbose)
        return 1

    if not input_path.is_file():
        print_error(f"Not a file: {args.input_file}", args.debug, args.verbose)
        return 1

    print_verbose(f"Parsing file: {input_path}", args.verbose, args.debug)

    # Parse the HL7 file
    try:
        if args.streaming:
            # Use streaming parsing for memory efficiency
            print_verbose("Using streaming mode", args.verbose, args.debug)
            appointment_generator = parse_hl7_file_streaming(
                str(input_path), continue_on_error=args.continue_on_error
            )

            # Determine JSON formatting for streaming output
            indent = None if args.compact else 2

            if args.output_file:
                # Write to file in JSON Lines format
                output_path = Path(args.output_file)
                with open(output_path, "w", encoding="utf-8") as f:
                    count = 0
                    for appointment in appointment_generator:
                        json_line = json.dumps(appointment.to_dict(), indent=indent)
                        f.write(json_line + "\n")
                        count += 1
                    print_verbose(
                        f"Streamed {count} appointments to: {output_path}",
                        args.verbose,
                        args.debug,
                    )
            else:
                # Print to stdout in JSON Lines format
                count = 0
                for appointment in appointment_generator:
                    json_line = json.dumps(appointment.to_dict(), indent=indent)
                    print(json_line)
                    count += 1
                print_verbose(
                    f"Streamed {count} appointments to stdout", args.verbose, args.debug
                )

        elif args.continue_on_error or args.verbose:
            # Use error-tolerant parsing (when continue_on_error is set or verbose is enabled)
            appointments, errors = parse_hl7_file_with_errors(str(input_path))

            if errors:
                for error in errors:
                    print_error(error, args.debug, args.verbose)

            if not appointments:
                print_error(
                    "No valid appointments parsed from file", args.debug, args.verbose
                )
                return 1

            print_verbose(
                f"Parsed {len(appointments)} appointments, {len(errors)} errors",
                args.verbose,
                args.debug,
            )
        else:
            # Use strict parsing (raises on first error)
            appointments = parse_hl7_file(str(input_path))
            print_verbose(
                f"Parsed {len(appointments)} appointments", args.verbose, args.debug
            )

    except FileNotFoundError:
        print_error(
            f"File not found: {args.input_file}", debug=False, verbose=args.verbose
        )
        return 1

    except HL7ParserError as e:
        print_error(str(e), args.debug, args.verbose)
        return 1

    except Exception as e:
        print_error(f"Unexpected error: {str(e)}", args.debug, args.verbose)
        return 1

    # Print warnings if debug mode or verbose mode
    if (args.debug or args.verbose) and not args.streaming:
        for i, appointment in enumerate(appointments):
            if appointment.patient is None:
                print(
                    f"[WARNING] Appointment {i+1}: Missing patient information (PID segment)"
                )
            if appointment.provider is None:
                print(
                    f"[WARNING] Appointment {i+1}: Missing provider information (PV1 segment)"
                )
            if not appointment.location:
                print(f"[WARNING] Appointment {i+1}: Missing location information")
            if not appointment.reason:
                print(f"[WARNING] Appointment {i+1}: Missing appointment reason")

    # For non-streaming mode, output the collected appointments
    if not args.streaming:
        # Determine JSON formatting
        indent = None if args.compact else 2

        # Convert appointments to JSON
        json_output = appointments_to_json(appointments, indent=indent if indent else 0)

        if args.compact:
            # Re-serialize without indentation for compact output
            data = [appt.to_dict() for appt in appointments]
            json_output = json.dumps(data)

        # Output JSON
        if args.output_file:
            # Write to file
            output_path = Path(args.output_file)
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(json_output)
                print_verbose(
                    f"Output written to: {output_path}", args.verbose, args.debug
                )
            except IOError as e:
                print_error(f"Could not write to file: {e}", args.debug, args.verbose)
                return 1
        else:
            # Print to stdout
            print(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
