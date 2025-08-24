# WAL Mode Configuration Summary

## For Linux Production Deployments ✅

**WAL mode works great on Linux!** Since you're deploying to Linux, you can safely use WAL mode for better performance:

```bash
# Enable WAL mode on Linux
docker run -v /data:/app/data -e SENSOR_WAL=true sensor-simulator

# Or in docker-compose.yml
services:
  sensor:
    image: sensor-simulator
    environment:
      - SENSOR_WAL=true  # ✅ Safe on Linux
    volumes:
      - ./data:/app/data
```

### Benefits on Linux:
- Better concurrent read/write performance
- Multiple readers can access while writing
- No locking issues
- Faster write performance

## For Local Development (Mac/Windows) ⚠️

If developers use Docker Desktop on Mac/Windows, they should use DELETE mode (default):

```bash
# On Mac/Windows with Docker Desktop - don't set SENSOR_WAL
docker run -v $(pwd)/data:/app/data sensor-simulator
```

## Quick Decision Guide

```
Are you deploying to Linux?
├── Yes → Use WAL mode (SENSOR_WAL=true) ✅
└── No → Are you using Docker Desktop?
    ├── Yes → Use DELETE mode (default) ⚠️
    └── No → Use WAL mode (SENSOR_WAL=true) ✅
```

## Testing Your Environment

```bash
# Test if WAL works in your environment
./test_linux_wal.sh

# Or comprehensive Docker tests
./test_docker_wal.sh
```

## Environment Variable Options

The `SENSOR_WAL` environment variable accepts:
- `true`, `1`, `yes`, `on` → Enable WAL mode
- `false`, `0`, `no`, `off`, or unset → Use DELETE mode (default)

## Summary for Your Use Case

Since you're **deploying to Linux**, you can:

1. **Use WAL mode in production** for better performance
2. **Keep DELETE mode as default** for developer compatibility
3. **Document the difference** for your team

Example configuration:
```yaml
# production.yml (Linux)
environment:
  - SENSOR_WAL=true  # Better performance on Linux

# development.yml (Mac/Windows)
environment:
  # Don't set SENSOR_WAL - uses DELETE mode for compatibility
```