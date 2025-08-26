# Testing Scripts

This directory contains various testing and stress-testing scripts for the sensor log generator.

## Python Scripts

- **test_readers.py** - Tests concurrent database readers
- **test_containers_rw.py** - Tests concurrent read/write with Docker containers
- **test_readers_containerized.py** - Tests multiple Docker containers reading from same database
- **test_production_load.py** - Simulates production load scenarios
- **stress_test.py** - General stress testing tool
- **run_tests_serial.py** - Runs tests serially to avoid concurrency issues
- **fix_tests.py** - Utility to fix common test issues

## Shell Scripts

- **test_readers.sh** - Shell wrapper for reader tests
- **test_container.sh** - Tests Docker container functionality
- **test_concurrent_readers.sh** - Tests concurrent reading scenarios
- **run_stress_test.sh** - Runs stress tests with configurable parameters
- **stress_test_production.sh** - Production-level stress testing

## Usage Examples

```bash
# Test concurrent readers
uv run scripts/testing/test_readers.py

# Test containerized read/write
uv run scripts/testing/test_containers_rw.py

# Run stress test
./scripts/testing/run_stress_test.sh
```
