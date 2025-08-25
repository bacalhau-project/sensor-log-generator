# Changes Summary

## 1. WAL Mode is Now Default

### Before:
- DELETE mode was the default
- WAL mode required setting `SENSOR_WAL=true`

### After:
- **WAL mode is the default** for better performance
- DELETE mode requires setting `SENSOR_WAL=false`
- Database mode is logged at startup: `"Database using WAL journal mode"`

### Impact:
- Better performance on Linux (production)
- Mac/Windows Docker Desktop users should set `SENSOR_WAL=false`

## 2. Removed Legacy Support

### Removed:
- Migration code for old config formats
- Version-based configuration handling
- Legacy flat identity format support
- Backward compatibility code

### Required Now:
- Nested identity format only
- Monitoring must be enabled
- Dynamic reloading must be enabled

### Simplified Code:
- Removed `migrate_config_format()` function
- Removed `version` field from configs
- Removed legacy field handling in identity
- Cleaner, more maintainable codebase

## 3. Configuration Changes

### Monitoring & Dynamic Reloading:
- **Now automatically enabled** - no longer optional
- Required for proper operation
- Warnings shown if disabled in config

### Config Processing:
- Simplified config processing
- Automatic enforcement of required features
- No version checks or migrations

## 4. Testing the Changes

### Check Database Mode:
```bash
# Default (WAL mode)
uv run main.py
# Output: "Database using WAL journal mode"

# DELETE mode
SENSOR_WAL=false uv run main.py  
# Output: "Database using DELETE journal mode"
```

### Docker Usage:
```bash
# Linux production (WAL works great)
docker run -v /data:/app/data sensor-simulator

# Mac/Windows development (use DELETE)
docker run -e SENSOR_WAL=false -v $(pwd)/data:/app/data sensor-simulator
```

## 5. Files Modified

### Core Changes:
- `src/database.py` - WAL mode default, improved logging
- `main.py` - Removed legacy support, simplified config
- `README.md` - Updated documentation
- `CLAUDE.md` - Updated guidance

### Cleanup:
- Removed 24+ test files
- Removed redundant documentation
- Simplified configuration handling

## 6. Benefits

1. **Better Performance**: WAL mode default improves concurrent access
2. **Cleaner Code**: Removed ~200+ lines of legacy support
3. **Clearer Logging**: Database mode shown at startup
4. **Simpler Maintenance**: No version migrations to maintain
5. **Required Features**: Monitoring and dynamic reloading always available

## 7. Breaking Changes

⚠️ **Users must**:
1. Use nested identity format (no flat format)
2. Accept monitoring being enabled
3. Accept dynamic reloading being enabled
4. Set `SENSOR_WAL=false` on Mac/Windows Docker Desktop

## 8. Recommendations

### For Production (Linux):
- Use default settings (WAL mode enabled)
- Benefits from improved performance

### For Development (Mac/Windows):
- Set `SENSOR_WAL=false` in docker-compose
- Or use environment variable

### Example docker-compose.yml:
```yaml
services:
  sensor:
    image: sensor-simulator
    environment:
      # For Mac/Windows Docker Desktop
      - SENSOR_WAL=false
    volumes:
      - ./data:/app/data
```