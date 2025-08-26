# Container Database Testing

This directory includes specialized testing scripts for validating SQLite database access patterns across Docker container boundaries.

## Test Scripts

### 1. test_readers_containerized.py
Tests multiple Docker containers reading from the same SQLite database.

**Purpose**: Validate that SQLite's WAL mode works correctly when multiple containers mount and read from the same database file.

**Usage**:
```bash
# Test with 3 reader containers for 30 seconds
./test_readers_containerized.py

# Test with 5 containers reading every 0.2 seconds
./test_readers_containerized.py -c 5 -i 0.2

# Use existing database
./test_readers_containerized.py -p data/sensor_data.db
```

**What it does**:
1. Builds a lightweight Python container image with SQLite
2. Spawns N reader containers that mount the database read-only
3. Each container performs continuous reads (COUNT, SELECT, AVG queries)
4. Displays real-time statistics in a rich UI dashboard
5. Reports success rates and performance metrics

### 2. test_containers_rw.py
Tests concurrent read/write operations across containers.

**Purpose**: Validate SQLite's WAL mode with one writer and multiple readers in separate containers.

**Usage**:
```bash
# Default: 1 writer + 3 readers for 30 seconds
./test_containers_rw.py

# Higher write rate with more readers
./test_containers_rw.py -r 5 -w 20

# Longer test with faster reads
./test_containers_rw.py -d 60 -i 0.2
```

**What it does**:
1. Builds two container images: reader and writer
2. Spawns 1 writer container (read-write mount)
3. Spawns N reader containers (read-only mounts)
4. Writer generates sensor data at specified rate
5. Readers perform continuous queries
6. Live dashboard shows both writer and reader statistics
7. Final report shows write/read ratios and success rates

## Container Architecture

### Reader Containers
- Mount database directory as **read-only** (`/data:ro`)
- Use SQLite read-only connection mode (`file:db?mode=ro`)
- Set `PRAGMA query_only = ON` for safety
- Perform various SELECT queries

### Writer Container
- Mounts database directory as **read-write** (`/data`)
- Uses standard SQLite connection with WAL mode
- Writes sensor data in batches
- Commits periodically for consistency

## Requirements

- Docker installed and running
- Python 3.11+ with uv
- At least 100MB free disk space for container images

## How It Works

1. **Image Building**: Scripts build minimal Python containers (~50MB) on first run
2. **Volume Mounting**: Database directory is mounted into containers
3. **Process Isolation**: Each container runs as separate process
4. **Statistics Collection**: JSON output from containers is parsed in real-time
5. **Dashboard Display**: Rich UI shows live statistics

## Expected Results

### Successful Test
- **Success Rate**: > 99%
- **Read Errors**: 0 (WAL mode handles concurrent access)
- **Write Errors**: 0 (single writer, no conflicts)
- **Performance**:
  - Reads: < 10ms average
  - Writes: < 5ms average (batched)

### Common Issues

1. **"Database is locked"**: Should NOT occur with WAL mode
2. **"Permission denied"**: Check file permissions on database
3. **"No such file"**: Ensure database exists before testing
4. **High read latency**: Normal during checkpointing

## Testing Scenarios

### Scenario 1: Read Scalability
```bash
# Test with increasing reader count
for readers in 1 2 5 10 20; do
    ./test_readers_containerized.py -c $readers -d 10
done
```

### Scenario 2: Write Pressure
```bash
# Test with varying write rates
for rate in 10 50 100 200; do
    ./test_containers_rw.py -w $rate -d 20
done
```

### Scenario 3: Production Simulation
```bash
# Long-running test with realistic rates
./test_containers_rw.py -r 10 -w 30 -d 300 -i 1.0
```

## Monitoring

Both scripts provide:
- Real-time dashboard with color-coded status
- Per-container statistics
- Average latency measurements
- Error tracking and reporting
- Final summary with success rates

## Cleanup

Containers are automatically removed (`--rm` flag) when stopped.
To manually clean up:

```bash
# Stop all test containers
docker stop $(docker ps -q --filter "name=sensor-")

# Remove test images
docker rmi sensor-reader-test sensor-writer-test
```

## Notes

- WAL mode is essential for cross-container access
- Read-only mounts prevent accidental writes
- Containers provide perfect process isolation for testing
- Performance may vary based on Docker storage driver
