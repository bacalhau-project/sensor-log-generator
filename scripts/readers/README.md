# Reader Scripts

This directory contains utilities for reading and analyzing sensor data.

## Scripts

- **read_safe.py** - Safe database reader with proper error handling
- **read_sensor_data.py** - General purpose sensor data reader
- **reader_example.py** - Example implementation of a data reader

## Usage Examples

```bash
# Read sensor data safely
uv run scripts/readers/read_safe.py

# Read with specific parameters
uv run scripts/readers/read_sensor_data.py --limit 100

# See example implementation
uv run scripts/readers/reader_example.py
```

## Notes

All readers use read-only database connections to prevent accidental modifications.
They handle WAL mode and support concurrent access.
