# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the parser module and CLI
COPY hl7_parser/ ./hl7_parser/
COPY hl7_parser_cli.py .

# Create a non-root user for security
RUN useradd --create-home appuser
USER appuser

# Set the entrypoint to the CLI script
ENTRYPOINT ["python", "hl7_parser_cli.py"]

# Default command shows help if no arguments provided
CMD ["--help"]
