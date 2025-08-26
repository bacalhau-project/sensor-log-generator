# Quick Reference Guide

## Common Commands

### Running the Simulator
```bash
# Run directly (ALWAYS creates new database - this is correct!)
uv run main.py

# Run with Docker (creates new database)
docker run -v $(pwd)/data:/app/data sensor-simulator

# Generate identity file
uv run main.py --generate-identity > config/node-identity.json
```

### Testing Scripts

#### Test Database Readers
```bash
# Test concurrent readers
uv run scripts/testing/test_readers.py -r 10 -t 30

# Test containerized readers
uv run scripts/testing/test_readers_containerized.py -c 5

# Test read/write concurrency
uv run scripts/testing/test_containers_rw.py -r 5 -w 20
```

#### Reader Examples
```bash
# Safe database reader
uv run scripts/readers/read_safe.py

# General reader
uv run scripts/readers/read_sensor_data.py

# Example implementation
uv run scripts/readers/reader_example.py
```

#### Monitoring
```bash
# Monitor database
./scripts/monitoring/monitor_db.sh

# Check database health
./scripts/monitoring/check_db.sh

# Query logs
./scripts/monitoring/query_all_log_files.sh
```

### Building & Testing

```bash
# Build Docker images
uv run build.py

# Test container
uv run scripts/testing/test_container.sh

# Run unit tests
uv run pytest tests/

# Run stress test
./scripts/testing/run_stress_test.sh
```

## Project Structure

```
sensor-log-generator/
├── src/               # Core application code
├── tests/             # Unit tests
├── scripts/           # Utility scripts
│   ├── testing/       # Test & stress test scripts
│   ├── readers/       # Database readers
│   └── monitoring/    # Monitoring tools
├── config/            # Configuration files
├── data/              # Database files
└── logs/              # Application logs
```

## Key Files

- `main.py` - Main application entry point
- `collector.py` - Data collection script (deprecated)
- `build.py` - Docker image builder
- `config/config.yaml` - Main configuration
- `config/node-identity.json` - Sensor identity

## Environment Variables

- `SENSOR_WAL` - Enable/disable WAL mode (default: true)
- `PRESERVE_EXISTING_DB` - Keep existing database (default: false)
- `SENSOR_CONFIG` - Path to config file
- `SENSOR_IDENTITY` - Path to identity file

## Database Access

Always use read-only mode when reading while simulator is running:

```bash
# Command line
sqlite3 "file:data/sensor_data.db?mode=ro" "SELECT COUNT(*) FROM sensor_readings;"

# Python
import sqlite3
conn = sqlite3.connect("file:data/sensor_data.db?mode=ro", uri=True)
```

## Getting Help

- View this guide: `cat QUICK_REFERENCE.md`
- Project README: `cat README.md`
- Database guide: `cat README_DATABASE.md`
- Container testing: `cat TESTING_CONTAINERS.md`
