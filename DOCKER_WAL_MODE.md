# Docker and SQLite WAL Mode - Platform-Specific Guide

## ⚠️ CRITICAL: Data Loss on macOS/Windows

**Docker Desktop on macOS/Windows does NOT properly sync SQLite WAL files!**
- Container shows correct count (e.g., 4500 records)
- Host database is missing data (e.g., only 1100 records)
- **Solution: Use DELETE mode or the macOS-specific compose file**

## Quick Summary

| Platform | WAL Mode Support | Recommendation |
|----------|-----------------|----------------|
| **Linux (Production)** | ✅ Works Great | Use WAL for better performance |
| **macOS (Docker Desktop)** | ❌ Has Issues | Use DELETE mode (default) |
| **Windows (Docker Desktop)** | ❌ Has Issues | Use DELETE mode (default) |

## Platform Details

### 🐧 Linux (Production Deployments)
✅ **WAL mode works excellently on Linux**

```bash
# On Linux, WAL mode is recommended for better performance
docker run -v /data:/app/data -e SENSOR_WAL=true sensor-simulator
```

**Why it works on Linux:**
- Native Docker (no virtualization layer)
- Direct filesystem access
- Proper mmap and file locking support
- No file sharing translation layer

### 🍎 macOS (Development with Docker Desktop)
❌ **WAL mode has issues - Use DELETE mode**

```bash
# On macOS, use DELETE mode (don't set SENSOR_WAL)
docker run -v $(pwd)/data:/app/data sensor-simulator
```

**Why it fails on macOS:**
- Docker Desktop runs in a VM
- File sharing layer (osxfs/VirtioFS/gRPC-FUSE) doesn't support mmap
- Cross-VM boundary causes synchronization issues

### 🪟 Windows (Development with Docker Desktop)
❌ **WAL mode has issues - Use DELETE mode**

```bash
# On Windows, use DELETE mode (don't set SENSOR_WAL)
docker run -v %cd%/data:/app/data sensor-simulator
```

**Why it fails on Windows:**
- Similar to macOS - runs in a VM
- File sharing doesn't support SQLite's requirements
- WSL2 might work better but still has limitations

## The Technical Details

WAL mode issues occur when:

1. **Docker Desktop file sharing**: The virtualization layer between Mac/Windows and the Linux VM doesn't properly handle memory-mapped I/O
2. **Network filesystems**: NFS, CIFS, or similar don't support the locking mechanisms WAL requires
3. **Cross-VM boundaries**: Docker Desktop runs in a VM, and the file sharing crosses this boundary

## Testing WAL Mode in Docker

### Quick Test

```bash
# Test DELETE mode (default - recommended)
docker run -v $(pwd)/data:/app/data sensor-simulator

# Test WAL mode (may have issues)
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=true sensor-simulator

# Check from host while container runs
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

### Comprehensive Test Suite

```bash
# Test container functionality
uv run scripts/testing/test_container.sh

# Test containerized readers
uv run scripts/testing/test_readers_containerized.py

# Test concurrent read/write in containers
uv run scripts/testing/test_containers_rw.py
```

## Common Issues and Solutions

### Issue 1: Database Locked Errors

**Symptom**: "database is locked" when accessing from host while container writes

**Solution**: Use DELETE mode (default)
```bash
# Don't set SENSOR_WAL, or explicitly set to false
docker run -v $(pwd)/data:/app/data sensor-simulator
```

### Issue 2: WAL Files Not Visible

**Symptom**: `-wal` and `-shm` files not visible on host

**Cause**: File synchronization issues with Docker volumes

**Solution**:
- Use DELETE mode for cross-boundary access
- Or use named volumes for container-only access

### Issue 3: Corrupt Database

**Symptom**: "database disk image is malformed" after container restart

**Cause**: Incomplete WAL checkpoint on container stop

**Solution**:
```bash
# Ensure proper shutdown
docker stop -t 30 container_name  # Give time for checkpoint

# Or use DELETE mode
docker run -v $(pwd)/data:/app/data sensor-simulator
```

### Issue 4: Permission Denied

**Symptom**: Cannot read database from host after container writes

**Solution**:
```bash
# Run container with same UID as host
docker run --user $(id -u):$(id -g) -v $(pwd)/data:/app/data sensor-simulator

# Or fix permissions after
sudo chown -R $(id -u):$(id -g) data/
```

## Recommendations by Use Case

### 1. Single Container, No External Access
✅ **WAL mode works fine**
```yaml
services:
  sensor:
    image: sensor-simulator
    environment:
      - SENSOR_WAL=true  # OK for single container
    volumes:
      - sensor-data:/app/data  # Named volume

volumes:
  sensor-data:
```

### 2. Container Writes, Host Reads
❌ **Use DELETE mode (default)**
```yaml
services:
  sensor:
    image: sensor-simulator
    # No SENSOR_WAL - uses DELETE mode
    volumes:
      - ./data:/app/data  # Host mount
```

### 3. Multiple Containers, Shared Database
⚠️ **Use DELETE mode or separate databases**
```yaml
services:
  writer:
    image: sensor-simulator
    # No SENSOR_WAL
    volumes:
      - ./data:/app/data

  reader:
    image: your-reader
    volumes:
      - ./data:/app/data:ro  # Read-only
```

### 4. Docker Desktop (Mac/Windows)
❌ **Always use DELETE mode**

Docker Desktop uses file sharing that doesn't support mmap properly.

```bash
# Mac/Windows with Docker Desktop
docker run -v $(pwd)/data:/app/data sensor-simulator
# Do NOT use SENSOR_WAL=true
```

### 5. Linux Native Docker
✅ **WAL mode usually works**

On Linux with native Docker (not Docker Desktop), WAL mode typically works:

```bash
# Linux native Docker - WAL mode should work
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=true sensor-simulator

# But DELETE mode is still safer for cross-boundary access
docker run -v $(pwd)/data:/app/data sensor-simulator
```

### 6. Production Kubernetes
✅ **WAL works with restrictions**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sensor-data
spec:
  accessModes:
    - ReadWriteOnce  # Single node only for WAL
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 1  # Must be 1 for WAL mode
  template:
    spec:
      containers:
      - name: sensor
        env:
        - name: SENSOR_WAL
          value: "true"  # OK with PVC
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: sensor-data
```

## Performance Comparison

| Mode | Linux Docker | Docker Desktop | Cross-Boundary | Concurrent Read | Write Speed |
|------|-------------|----------------|----------------|-----------------|-------------|
| DELETE (default) | ✅ Excellent | ✅ Excellent | ✅ Works | ⚠️ May lock | Standard |
| WAL | ✅ Good | ❌ Issues | ⚠️ Platform dependent | ✅ Better | Faster |

## Decision Tree

```
What platform are you using?
├── Docker Desktop (Mac/Windows) → Use DELETE mode (default)
├── Linux with native Docker
│   ├── Need host access while container runs?
│   │   ├── Yes → DELETE mode recommended
│   │   └── No → WAL mode OK
│   └── Multiple containers need write access?
│       ├── Yes → Use DELETE mode
│       └── No → WAL mode OK
└── Native (no Docker) → WAL mode works great
```

## Testing Your Setup

### Test Script
```bash
#!/bin/bash
# Save as test_my_setup.sh

echo "Testing your Docker setup..."

# Test DELETE mode
docker run -d --name test-delete \
  -v $(pwd)/test_delete:/app/data \
  sensor-simulator

sleep 5

DELETE_OK=$(sqlite3 test_delete/sensor_data.db \
  "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "FAIL")

docker stop test-delete && docker rm test-delete

# Test WAL mode
docker run -d --name test-wal \
  -v $(pwd)/test_wal:/app/data \
  -e SENSOR_WAL=true \
  sensor-simulator

sleep 5

WAL_OK=$(sqlite3 test_wal/sensor_data.db \
  "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "FAIL")

docker stop test-wal && docker rm test-wal

echo "Results:"
echo "  DELETE mode: $DELETE_OK"
echo "  WAL mode: $WAL_OK"

if [ "$DELETE_OK" != "FAIL" ]; then
  echo "✅ DELETE mode works - recommended!"
fi

if [ "$WAL_OK" = "FAIL" ]; then
  echo "⚠️  WAL mode has issues - use DELETE mode"
fi

# Cleanup
rm -rf test_delete test_wal
```

## Summary

### Recommended Settings by Platform

| Platform | Recommended Mode | SENSOR_WAL Setting |
|----------|-----------------|-------------------|
| Docker Desktop (Mac/Windows) | DELETE | Don't set (or `false`) |
| Linux + Native Docker | DELETE* | Don't set (or `false`) |
| Linux Native (no Docker) | WAL | `true` |
| Kubernetes (Linux nodes) | DELETE* | Don't set (or `false`) |

*WAL can work on Linux but DELETE is safer for cross-boundary access

**The sensor simulator defaults to DELETE mode for maximum compatibility.**

To explicitly ensure DELETE mode:
```bash
# Option 1: Don't set SENSOR_WAL (default)
docker run -v $(pwd)/data:/app/data sensor-simulator

# Option 2: Explicitly set to false
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=false sensor-simulator
```
