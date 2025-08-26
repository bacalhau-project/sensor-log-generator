# Database Usage Guide 🗄️

## Overview

The sensor log generator uses a **simplified, single-threaded SQLite database** optimized for high-performance concurrent access. The database runs in WAL (Write-Ahead Logging) mode by default, providing excellent read/write separation without the complexity of threading.

## Key Features

- **90,000+ writes/second** throughput capability
- **Zero-threading architecture** - no deadlocks, no race conditions
- **WAL mode by default** - natural read/write separation
- **Automatic batching** - writes are batched every 10 seconds or 50 records
- **Read-only access support** - safe concurrent reading from multiple processes
- **~400 lines of code** - simple, maintainable, reliable

## Database Modes

### WAL Mode (Default - Recommended)
```bash
# WAL mode is the default - best performance
docker run -v $(pwd)/data:/app/data sensor-simulator:latest

# Explicitly set WAL mode
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=true sensor-simulator:latest
```

**Benefits:**
- Concurrent readers don't block writers
- Writers don't block readers
- Better performance for continuous operations
- Automatic checkpointing

**Best for:**
- Linux systems
- Production deployments
- Continuous operation
- High-performance requirements

### DELETE Mode (Compatibility)
```bash
# Use DELETE mode for compatibility (Mac/Windows Docker Desktop)
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=false sensor-simulator:latest
```

**When to use:**
- Docker Desktop on Mac/Windows with file sync issues
- Older SQLite versions
- Specific compatibility requirements

## Reading from the Database

### IMPORTANT: Always Use Read-Only Mode

When reading from the database while the sensor is writing, **always use read-only mode** to prevent corruption:

```bash
# ✅ CORRECT - Read-only mode
sqlite3 "file:data/sensor_data.db?mode=ro" "SELECT COUNT(*) FROM sensor_readings;"

# ❌ WRONG - Can cause corruption
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

### Python Reading Example

```python
import sqlite3

# ✅ CORRECT - Read-only connection
conn = sqlite3.connect("file:data/sensor_data.db?mode=ro", uri=True)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM sensor_readings")
count = cursor.fetchone()[0]
conn.close()

# ❌ WRONG - Read-write connection
conn = sqlite3.connect("data/sensor_data.db")  # Don't do this!
```

### Safe Reader Script

We provide a dedicated reader example that safely reads from the database:

```bash
# Use the provided reader example
uv run scripts/readers/reader_example.py

# Output shows safe reading patterns
Connected to database (read-only): data/sensor_data.db
Database contains 150000 records
Latest reading: SENSOR_001 - Temp: 22.5°C
```

## Testing Concurrent Access

### Test Multiple Readers

Use our concurrent reader test scripts to verify database performance:

```bash
# Python version with rich UI (recommended)
uv run scripts/testing/test_readers.py                    # 10 readers for 30 seconds
uv run scripts/testing/test_readers.py -r 50 -t 60       # 50 readers for 60 seconds
uv run scripts/testing/test_readers.py --check-writes    # Check if DB is being written to

# Bash version for quick testing
./scripts/testing/test_readers.sh
NUM_READERS=20 DURATION=60 ./scripts/testing/test_readers.sh
```

The test scripts:
- **Only read** from the database (don't start the sensor)
- Use **read-only connections** for safety
- Show **real-time statistics** and performance metrics
- Test with **configurable load** (1-100 concurrent readers)

### Expected Performance

With the simplified database architecture:
- **20 concurrent writers**: ~90,000 writes/second
- **50 concurrent readers**: No impact on write performance
- **Zero data loss** under aggressive concurrent load
- **No deadlocks** or threading issues

## Best Practices

### ✅ DO

1. **Always use read-only mode** when reading while sensor is running
   ```bash
   sqlite3 "file:data/sensor_data.db?mode=ro"
   ```

2. **Use WAL mode** (default) for best performance
   ```bash
   # This is the default, but you can be explicit
   docker run -e SENSOR_WAL=true ...
   ```

3. **Let batching work** - the database commits every 10 seconds automatically

4. **Use provided scripts** for reading and testing
   ```bash
   uv run scripts/readers/reader_example.py     # Safe reading example
   uv run scripts/testing/test_readers.py       # Concurrent reader testing
   ```

### ❌ DON'T

1. **Never write to the database** from external processes while sensor is running

2. **Don't open read-write connections** for reading
   ```bash
   # WRONG - can cause corruption
   sqlite3 data/sensor_data.db
   ```

3. **Don't modify database files** directly (`.db`, `.db-wal`, `.db-shm`)

4. **Don't use threading** in readers - not needed with WAL mode

## Troubleshooting

### "Database is locked" Error

**Cause**: Another process has a write lock on the database.

**Solution**:
- Ensure only one sensor simulator is running
- Use read-only mode for all readers
- Check for stuck processes: `lsof data/sensor_data.db`

### "Disk I/O Error"

**Cause**: File system issues or permissions.

**Solution**:
- Check disk space: `df -h`
- Verify permissions: `ls -la data/`
- For Docker: ensure volume is mounted correctly

### Slow Performance on Mac/Windows

**Cause**: Docker Desktop file sync overhead with WAL mode.

**Solution**:
```bash
# Switch to DELETE mode for Docker Desktop
docker run -e SENSOR_WAL=false ...
```

### Corruption Issues

**Prevention is key**: Always use read-only mode for readers!

If corruption occurs:
1. Stop the sensor simulator
2. Remove database files:
   ```bash
   rm data/sensor_data.db*
   ```
3. Restart the sensor (it will create a fresh database)

## Architecture Details

### Simplified Design

The database uses a **single-threaded architecture** that eliminates complexity:

- **No background threads** - all operations are synchronous
- **No connection pools** - single connection per process
- **No complex locking** - SQLite handles everything
- **Automatic batching** - buffers writes for efficiency

### Write Flow

1. Sensor generates reading
2. Reading added to in-memory buffer
3. When buffer reaches 50 items OR 10 seconds pass:
   - Batch insert to database
   - Single COMMIT operation
4. SQLite WAL handles concurrent readers transparently

### Read Flow

1. Reader opens read-only connection
2. SQLite serves data from main database or WAL
3. No blocking between readers and writers
4. Connection closed after query

## Performance Tuning

### For Maximum Write Performance

```yaml
# config.yaml
database:
  batch_size: 100        # Larger batches
  batch_timeout: 30      # Less frequent commits
```

### For Maximum Read Performance

```bash
# Use multiple reader processes
for i in {1..10}; do
  ./reader_example.py &
done
```

### For Docker Desktop (Mac/Windows)

```bash
# Use DELETE mode to avoid file sync issues
docker run -e SENSOR_WAL=false ...
```

## Summary

The simplified database architecture provides:
- **Excellent performance** without complexity
- **Safe concurrent access** with read-only connections
- **Zero maintenance** - it just works
- **Production-ready** reliability

Remember: **Always use read-only mode when reading!** This simple rule prevents all corruption issues.
