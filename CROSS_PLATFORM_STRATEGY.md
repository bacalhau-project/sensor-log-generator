# Cross-Platform Database Strategy (Mac Development & Linux Production)

## Recommended Approach: DELETE Mode + Named Volumes

For maximum compatibility between Mac development and Linux production, use:
1. **DELETE mode** (default - don't set SENSOR_WAL)
2. **Docker named volumes** (not host mounts)
3. **Same docker-compose.yml** for both platforms

This approach works identically on Mac and Linux with zero configuration changes.

## Implementation

### docker-compose.yml (Works on Both Mac & Linux)

```yaml
version: '3.8'

services:
  # Sensor simulator (writer)
  sensor:
    build: .
    image: sensor-simulator:latest
    container_name: sensor-writer
    environment:
      - LOG_LEVEL=INFO
      # Don't set SENSOR_WAL - DELETE mode works everywhere
    volumes:
      - sensor-data:/app/data  # Named volume (not host mount)
    ports:
      - "8080:8080"

  # Your reader process (second container)
  reader:
    build: .
    image: sensor-simulator:latest
    container_name: sensor-reader
    depends_on:
      - sensor
    volumes:
      - sensor-data:/app/data:ro  # Same volume, read-only
    command: python /app/reader_example.py

# Named volume - works identically on Mac and Linux
volumes:
  sensor-data:
    driver: local
```

## Key Principles

### 1. Use Named Volumes, Not Host Mounts

**❌ Avoid (causes issues on Mac):**
```yaml
volumes:
  - ./data:/app/data  # Host mount - problematic on Mac
```

**✅ Use instead:**
```yaml
volumes:
  - sensor-data:/app/data  # Named volume - works everywhere
```

### 2. Stick with DELETE Mode

**❌ Don't enable WAL on Mac:**
```yaml
environment:
  - SENSOR_WAL=true  # Causes issues on Mac Docker Desktop
```

**✅ Use default DELETE mode:**
```yaml
environment:
  # Don't set SENSOR_WAL - uses DELETE mode
```

### 3. Handle Database Locks Gracefully

In DELETE mode, readers may occasionally get "database locked" errors. This is normal and should be handled with retries:

```python
def connect_with_retry(db_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise
```

## Running Your Setup

### Start Both Containers
```bash
# Start sensor and reader
docker-compose -f docker-compose.dev.yml up

# Or in detached mode
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### Access the Database from Host (for debugging)

```bash
# Copy database from volume to host
docker run --rm -v sensor-data:/data -v $(pwd):/host alpine \
  cp /data/sensor_data.db /host/

# Now you can inspect it
sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

### Access from Another Container

```bash
# Run a one-off container with access to the volume
docker run --rm -it -v sensor-data:/data alpine sh
apk add sqlite
sqlite3 /data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

## Performance Expectations

### DELETE Mode Characteristics
- **Writes**: Single writer at a time (sensor simulator)
- **Reads**: May briefly lock during writes
- **Lock Duration**: Typically < 100ms
- **Retry Strategy**: 3 retries with 1 second delay usually sufficient

### Handling in Your Reader

```python
class DatabaseReader:
    def read_data(self):
        """Read with automatic retry on lock."""
        for attempt in range(3):
            try:
                conn = sqlite3.connect("/app/data/sensor_data.db", timeout=5.0)
                # Your query here
                data = conn.execute("SELECT * FROM sensor_readings").fetchall()
                conn.close()
                return data
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < 2:
                    print(f"Database locked, retrying...")
                    time.sleep(1)
                else:
                    raise
```

## Alternative: Host-Specific Configurations

If you absolutely need different behaviors on Mac vs Linux:

### Option 1: Environment-based Configuration
```bash
# Mac development
docker-compose up  # Uses DELETE mode

# Linux production (if you want WAL)
SENSOR_WAL=true docker-compose up
```

### Option 2: Separate Compose Files
```bash
# Mac
docker-compose -f docker-compose.mac.yml up

# Linux
docker-compose -f docker-compose.linux.yml up
```

### Option 3: Override Files
```yaml
# docker-compose.yml (base)
services:
  sensor:
    image: sensor-simulator

# docker-compose.override.yml (for local dev)
services:
  sensor:
    environment:
      - LOG_LEVEL=DEBUG

# docker-compose.prod.yml (for production)
services:
  sensor:
    environment:
      - SENSOR_WAL=true  # Enable on Linux only
```

## Testing Your Setup

### Test Script (works on both platforms)
```bash
#!/bin/bash
# test_setup.sh

echo "Starting sensor and reader..."
docker-compose -f docker-compose.dev.yml up -d

echo "Waiting for initialization..."
sleep 10

echo "Checking sensor writes..."
docker logs sensor-writer 2>&1 | grep "readings" | tail -5

echo "Checking reader access..."
docker logs sensor-reader 2>&1 | tail -10

echo "Database stats:"
docker exec sensor-reader sqlite3 /app/data/sensor_data.db \
  "SELECT COUNT(*) as total_readings FROM sensor_readings;"

echo "Cleanup..."
docker-compose -f docker-compose.dev.yml down
```

## Summary

**For your use case** (single writer, single reader, both in containers):

1. **Use DELETE mode** - Works identically on Mac and Linux
2. **Use named volumes** - Avoids Docker Desktop file sharing issues
3. **Handle locks gracefully** - Simple retry logic in your reader
4. **Same config everywhere** - No platform-specific changes needed

This approach requires **zero platform-specific configuration** and works reliably on both Mac development and Linux production environments.

## FAQ

**Q: Will DELETE mode be slow?**
A: No, for single writer/reader it's very fast. Locks are typically < 100ms.

**Q: Can I read from the host while containers run?**
A: Not recommended with named volumes. Use `docker exec` or copy the database out first.

**Q: What if I need multiple readers?**
A: DELETE mode handles multiple readers, just implement retry logic for occasional locks.

**Q: When should I use WAL mode?**
A: Only on Linux with many concurrent readers and when not using Docker Desktop.