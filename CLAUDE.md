# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- Build Docker image: `docker build -t sensor-simulator .`
- Run with Docker (WAL mode - default): `docker run -v $(pwd)/data:/app/data sensor-simulator`
- Run with Docker (DELETE mode for Mac/Windows): `docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=false sensor-simulator`
- Run directly: `uv run main.py --config config.yaml --identity node_identity.json`
- Generate identity template: `uv run main.py --generate-identity`
- Build multi-platform images: `./build.sh`
- Test container: `./test_container.sh`
- Run tests: `uv run pytest tests/`
- Keep existing database on startup: `docker run -v $(pwd)/data:/app/data -e PRESERVE_EXISTING_DB=true sensor-simulator`

## Database Modes
- **WAL mode (default)**: Better performance, works great on Linux
- **DELETE mode**: Set `SENSOR_WAL=false` for Docker Desktop on Mac/Windows

## Code Style Guidelines
- Python 3.11+ with type annotations (from typing import Dict, Optional, etc.)
- Google-style docstrings for functions and classes
- 4-space indentation following PEP 8
- Modular architecture with clear separation of concerns
- Exception handling with specific error logging
- Configuration loaded from YAML and JSON files
- Environment variables prefixed with SENSOR_
- Comprehensive error handling with retry logic and graceful degradation
- Logging with different levels and both file and console output

## Identity File Format
The system uses a nested identity format:

### Standard Format
```json
{
  "sensor_id": "SENSOR_CO_DEN_8548",
  "location": {
    "city": "Denver",
    "state": "CO",
    "coordinates": {
      "latitude": 39.733741,
      "longitude": -104.990653
    },
    "timezone": "America/Denver",
    "address": "Denver, CO, USA"
  },
  "device_info": {
    "manufacturer": "DataLogger",
    "model": "AirData-Plus",
    "firmware_version": "DLG_v3.15.21",
    "serial_number": "DataLogger-578463",
    "manufacture_date": "2025-03-24"
  },
  "deployment": {
    "deployment_type": "mobile_unit",
    "installation_date": "2025-03-24",
    "height_meters": 8.3,
    "orientation_degrees": 183
  },
  "metadata": {
    "instance_id": "i-04d485582534851c9",
    "sensor_type": "environmental_monitoring"
  }
}
```

## Important Configuration Notes
- **Dynamic reloading is now required** - monitoring and dynamic_reloading are automatically enabled
- **WAL mode is the default** - the database uses WAL mode unless SENSOR_WAL=false is set
- **No legacy support** - only the nested identity format is supported
- **Database commits every 10 seconds** - provides consistent read windows
- **Always use read-only mode for reading**: `sqlite3 "file:data/sensor_data.db?mode=ro"`

## Development Guidelines  
- **CRITICAL: Always run pre-commit hooks before committing code**
  - Setup: `./scripts/setup-pre-commit.sh`
  - Manual run: `uv run pre-commit run --all-files`
  - Pre-commit runs: syntax checks, linting, type checking, and fast tests
  - Pre-push runs: full test suite with coverage requirements
- Always use ruff for python lint checking
- Always use uv, instead of python, when writing python scripts
- Make sure each CLI line is correctly terminated or has a \ for continuation at 80 characters
- Ensure database mode is logged at startup
- Use read-only connections when reading from the database
- **Never use `git commit --no-verify` unless absolutely necessary**
