# Testing Philosophy

## Core Principle

**We test READERS, not WRITERS.**

The sensor simulator (`main.py`) is the ONLY source of truth for writing sensor data. All testing should focus on validating that external systems can successfully read from the database while the real sensor simulator is writing.

## Why This Approach?

1. **Single Source of Truth**: Only `main.py` knows the correct schema, data patterns, and business logic
2. **Real-World Testing**: Tests validate actual production behavior, not mocked scenarios
3. **Schema Consistency**: Prevents drift between test data and production data
4. **Simplicity**: No need to maintain separate mock data generators

## Testing Patterns

### ✅ CORRECT: Test Readers Against Live Sensor

```bash
# Start the real sensor in one terminal
uv run main.py

# In another terminal, test readers
uv run scripts/testing/test_readers.py -r 10
```

### ❌ WRONG: Mock Data Generation

```python
# DON'T DO THIS - Never create fake sensor data
conn.execute("INSERT INTO sensor_readings VALUES (...)")
```

## Test Scripts

### Reader Tests (Correct)
- `test_readers.py` - Tests concurrent reading while sensor writes
- `test_readers_containerized.py` - Tests containerized readers
- `read_safe.py` - Example of safe reading patterns

### Writer Tests (Need Updating)
These scripts currently violate our philosophy by creating mock data:
- `stress_test.py` - Should be updated to use real sensor
- `test_containers_rw.py` - Should be updated to use real sensor

## Implementation Guidelines

1. **All write operations** must come from `main.py`
2. **Test scripts** should ONLY read from the database
3. **Performance tests** should start multiple instances of the real sensor
4. **Container tests** should use the actual sensor Docker image

## Benefits

- **No schema drift** between tests and production
- **Realistic testing** of actual sensor behavior
- **Simpler codebase** with no mock data generators
- **Better validation** of real-world scenarios

## Migration Plan

Scripts that need updating to follow this philosophy:
1. Remove INSERT statements from test scripts
2. Replace with calls to start the real sensor
3. Update documentation to reflect this approach
