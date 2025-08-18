# Sensor Log Generator 🌡️

**A robust, production-ready sensor data simulation system for testing, development, and training!**

This sensor log generator creates hyper-realistic environmental sensor data with configurable anomalies, making it perfect for:

- **Testing data ingestion pipelines** without expensive hardware
- **Developing anomaly detection algorithms** with controlled, reproducible scenarios
- **Load testing time-series databases** with concurrent sensor streams
- **Training machine learning models** on realistic sensor patterns
- **Demonstrating monitoring systems** with real-time dashboards
- **Validating alerting systems** with predictable anomalies

The simulator generates authentic sensor readings (temperature, humidity, pressure, voltage) with manufacturer-specific behaviors, firmware quirks, and location-based patterns—just like real IoT deployments!

## ⚡ Why This Simulator?

Unlike basic data generators that produce random numbers, this simulator models **real-world sensor complexity**:

- **📦 Hardware variations**: Different manufacturers have unique failure characteristics (SensorTech fails 20% more often!)
- **💾 Firmware behaviors**: Beta versions are 50% more likely to produce anomalies
- **🌡️ Environmental patterns**: Temperature, humidity, and pressure follow realistic daily cycles
- **⚙️ Realistic anomalies**: Five different anomaly types (spikes, drifts, dropouts, noise, patterns) that mirror actual sensor failures
- **🔄 Resilient operation**: Automatic retry logic, corruption recovery, and graceful degradation
- **📈 Production-ready**: HTTP monitoring API, health checks, and metrics endpoints for observability

Perfect for teams who need to test their systems against realistic sensor behavior without expensive hardware!

## 🚀 Key Features

### Realistic Data Generation
- **Multi-metric readings**: Temperature, humidity, pressure, and voltage with realistic patterns
- **Manufacturer behaviors**: Different brands exhibit unique failure rates and characteristics
- **Firmware quirks**: Beta versions produce more anomalies than stable releases
- **Location intelligence**: City-based simulation with real coordinates and timezones

### Comprehensive Anomaly Types
Test your detection systems with five anomaly patterns:
- **🔥 Spike anomalies**: Sudden value jumps (sensor malfunctions)
- **📈 Trend anomalies**: Gradual drift from baseline (sensor degradation)
- **🔄 Pattern anomalies**: Disrupted normal cycles (timing issues)
- **🚫 Missing data**: Simulated dropouts (network/power failures)
- **📊 Noise anomalies**: Increased variance (environmental interference)

### Production Features
- **🔄 Dynamic configuration**: Hot-reload config changes without restart
- **🎯 Resilient database**: Automatic retries and corruption recovery
- **📡 HTTP monitoring**: Real-time metrics and health check endpoints
- **🏷️ Semantic versioning**: Multi-platform Docker images with proper versioning
- **🔐 Checkpoint system**: Resume from last state after restarts
- **📝 Flexible identity**: Support for legacy and enhanced sensor metadata

## 🎯 Common Use Cases

### Testing Anomaly Detection Systems
Validate your detection algorithms with controlled anomalies:

```yaml
# chaos-test.yaml
anomalies:
  enabled: true
  probability: 0.20  # 20% anomaly rate for stress testing
  types:
    spike:
      enabled: true
      weight: 0.5  # Test threshold-based detection
    trend:
      enabled: true
      weight: 0.3
      duration_seconds: 600  # Test drift detection
```

### Load Testing Time-Series Databases
Stress test with multiple concurrent sensors:

```yaml
# load-test.yaml
replicas:
  count: 100  # 100 concurrent sensors
  prefix: "LOAD"
simulation:
  readings_per_second: 10  # 1,000 total readings/second
```

### Training ML Models
Generate labeled training data with known anomaly patterns:

```yaml
# ml-training.yaml
anomalies:
  enabled: true
  probability: 0.05  # Realistic 5% anomaly rate
sensor:
  manufacturer: "SensorTech"  # Higher failure rate
  firmware_version: "3.0.0-beta"  # More anomalies
```

## 🚀 Quick Start

### Prerequisites
- Docker (recommended) or Python 3.11+ with uv
- SQLite3 (for data analysis)

### Running with Docker

```bash
# Quick start with defaults
docker run -v $(pwd)/data:/app/data sensor-simulator:latest

# Custom sensor identity
docker run -v $(pwd)/data:/app/data \
  -e SENSOR_ID=SENSOR_001 \
  -e SENSOR_LOCATION="San Francisco" \
  sensor-simulator:latest

# With monitoring dashboard
docker run -v $(pwd)/data:/app/data \
  -e MONITORING_ENABLED=true \
  -p 8080:8080 \
  sensor-simulator:latest
```

### Using Docker Compose

```yaml
# docker-compose.yml
services:
  sensor:
    image: sensor-simulator:latest
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - CONFIG_FILE=/app/config/config.yaml
      - MONITORING_ENABLED=true
    ports:
      - "8080:8080"
```

```bash
# Start the simulator
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the simulator
docker-compose down
```

### Running with Python

```bash
# Install uv package manager
pip install uv

# Install dependencies
uv sync

# Run with defaults
uv run main.py

# Run with custom config
uv run main.py --config config/config.yaml --identity config/identity.json

# Generate identity template
uv run main.py --generate-identity

# Run tests
uv run pytest tests/
```

### Building from Source

```bash
# Clone the repository
git clone <repository-url>
cd sensor-log-generator

# Build Docker image
docker build -t sensor-simulator .

# Build multi-platform (AMD64 + ARM64)
./build.py

# Test the container
./test_container.sh
```

## 📋 Configuration

### Environment Variables

Configure the simulator through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SENSOR_ID` | Unique sensor identifier | Auto-generated |
| `SENSOR_LOCATION` | Sensor location/city | Random city |
| `SENSOR_INTERVAL` | Reading interval (seconds) | 5 |
| `ANOMALY_PROBABILITY` | Chance of anomalies (0-1) | 0.05 |
| `LOG_LEVEL` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) | INFO |
| `PRESERVE_EXISTING_DB` | Keep existing database on startup | false |
| `MONITORING_ENABLED` | Enable web monitoring dashboard | false |
| `MONITORING_PORT` | Dashboard port number | 8080 |
| `CONFIG_FILE` | Path to configuration YAML | config.yaml |
| `IDENTITY_FILE` | Path to identity JSON | identity.json |
| `SQLITE_TMPDIR` | SQLite temp directory (containers) | /tmp |

### Configuration Files

The simulator uses two configuration files:

1. **config.yaml**: Main configuration with simulation parameters
2. **identity.json**: Sensor-specific metadata and location

### Identity Formats

The system supports both legacy and enhanced identity formats:

**Legacy Format** (backward compatible):
```json
{
  "id": "SENSOR_NY_001",
  "location": "New York",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "timezone": "America/New_York",
  "manufacturer": "SensorTech",
  "model": "TempSensor Pro",
  "firmware_version": "1.2.0"
}
```

**Enhanced Format** (recommended):
```json
{
  "sensor_id": "SENSOR_CO_DEN_001",
  "location": {
    "city": "Denver",
    "state": "CO",
    "coordinates": {
      "latitude": 39.7337,
      "longitude": -104.9906
    },
    "timezone": "America/Denver"
  },
  "device_info": {
    "manufacturer": "DataLogger",
    "model": "AirData-Plus",
    "firmware_version": "3.15.21",
    "serial_number": "DL-578463"
  },
  "deployment": {
    "deployment_type": "mobile_unit",
    "installation_date": "2025-03-24",
    "height_meters": 8.3
  }
}
```

### Sample Configuration (config.yaml)

```yaml
# Sensor configuration
sensor:
  type: "environmental"
  location: "San Francisco"  # Required
  manufacturer: "SensorTech"
  model: "EnvMonitor-3000"
  firmware_version: "1.4"

# Simulation settings
simulation:
  readings_per_second: 1
  run_time_seconds: 3600  # 1 hour

# Normal operating ranges
normal_parameters:
  temperature:
    mean: 22.0
    std_dev: 2.0
    min: 15.0
    max: 30.0
  humidity:
    mean: 65.0
    std_dev: 5.0
    min: 30.0
    max: 90.0
  pressure:
    mean: 1013.0
    std_dev: 10.0
    min: 990.0
    max: 1040.0

# Anomaly configuration
anomalies:
  enabled: true
  probability: 0.05  # 5% chance
  types:
    spike:
      enabled: true
      weight: 0.4
    trend:
      enabled: true
      weight: 0.2
      duration_seconds: 300
    pattern:
      enabled: true
      weight: 0.1
      duration_seconds: 600
    missing_data:
      enabled: true
      weight: 0.1
      duration_seconds: 30
    noise:
      enabled: true
      weight: 0.2
      duration_seconds: 180

# Database settings
database:
  path: "data/sensor_data.db"

# Logging configuration
logging:
  level: "INFO"
  file: "logs/sensor_simulator.log"
  console_output: true

# Monitoring API (optional)
monitoring:
  enabled: false
  port: 8080
  host: "0.0.0.0"
```

### Manufacturer and Firmware Effects

Different manufacturers and firmware versions affect anomaly rates:

**Manufacturers:**
- **SensorTech**: 20% more anomalies (budget hardware)
- **DataLogger**: 10% more anomalies
- **DataSense**: 20% fewer anomalies (premium)
- **MonitorPro**: 10% fewer anomalies

**Firmware Versions:**
- **1.x versions**: 30% fewer anomalies (stable)
- **2.x versions**: 15% fewer anomalies
- **3.x-beta/alpha**: 50% more anomalies (unstable)



## 📊 Data Output

### Database Schema

The SQLite database stores comprehensive sensor data:

```sql
CREATE TABLE sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME,
    sensor_id TEXT,
    
    -- Sensor readings
    temperature REAL,
    humidity REAL,
    pressure REAL,
    voltage REAL,
    
    -- Anomaly tracking
    status_code INTEGER,
    anomaly_flag BOOLEAN,
    anomaly_type TEXT,
    
    -- Device metadata
    firmware_version TEXT,
    model TEXT,
    manufacturer TEXT,
    serial_number TEXT,
    
    -- Location data
    location TEXT,
    latitude REAL,
    longitude REAL,
    timezone TEXT,
    
    -- Deployment info
    deployment_type TEXT,
    installation_date TEXT,
    height_meters REAL,
    
    -- Sync status
    synced BOOLEAN DEFAULT 0
);
```

### JSON Output Format

When JSON logging is enabled:

```json
{
  "timestamp": "2025-01-18T10:30:45.123456",
  "sensor_id": "SENSOR_SF_001",
  "readings": {
    "temperature": 22.5,
    "humidity": 65.3,
    "pressure": 1013.25,
    "voltage": 12.1
  },
  "location": {
    "name": "San Francisco",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "timezone": "America/Los_Angeles"
  },
  "anomaly": {
    "detected": false,
    "type": null
  },
  "device": {
    "manufacturer": "SensorTech",
    "model": "EnvMonitor-3000",
    "firmware": "1.4"
  }
}

### Analyzing the Data

Query the SQLite database for insights:

```sql
-- Anomaly rate by manufacturer
SELECT 
  manufacturer,
  COUNT(*) as total,
  SUM(anomaly_flag) as anomalies,
  ROUND(100.0 * SUM(anomaly_flag) / COUNT(*), 2) as anomaly_rate
FROM sensor_data
GROUP BY manufacturer;

-- Temperature patterns by hour
SELECT 
  strftime('%H', timestamp) as hour,
  AVG(temperature) as avg_temp,
  MIN(temperature) as min_temp,
  MAX(temperature) as max_temp
FROM sensor_data
WHERE anomaly_flag = 0
GROUP BY hour
ORDER BY hour;

-- Anomaly types distribution
SELECT 
  anomaly_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM sensor_data
WHERE anomaly_flag = 1
GROUP BY anomaly_type;
```

## 📡 Monitoring Dashboard

Enable the HTTP monitoring API for real-time insights:

### Available Endpoints

| Endpoint | Description | Response |
|----------|-------------|----------|
| `/healthz` | Health check | `{"status": "healthy"}` |
| `/statusz` | System status | Configuration and runtime stats |
| `/metricz` | Metrics data | Reading counts, anomaly statistics |
| `/samplez` | Recent samples | Last 10 sensor readings |
| `/db_stats` | Database info | Record count, file size |

### Enabling Monitoring

```yaml
# In config.yaml
monitoring:
  enabled: true
  port: 8080
  host: "0.0.0.0"
```

```bash
# Run with monitoring
docker run -v $(pwd)/data:/app/data \
  -e MONITORING_ENABLED=true \
  -p 8080:8080 \
  sensor-simulator

# Check health
curl http://localhost:8080/healthz

# View metrics
curl http://localhost:8080/metricz
```

## 🏗️ Architecture

### Project Structure

```
sensor-log-generator/
├── src/                    # Core modules
│   ├── simulator.py       # Main simulation engine
│   ├── database.py        # SQLite operations with retry logic
│   ├── anomaly.py         # Anomaly generation system
│   ├── location.py        # City database and GPS coords
│   ├── monitor.py         # HTTP monitoring server
│   ├── config.py          # Configuration management
│   └── enums.py           # Valid manufacturers/models
├── tests/                  # Test suite
│   ├── test_simulator.py  # Core functionality tests
│   ├── test_database.py   # Database operation tests
│   ├── test_anomaly.py    # Anomaly generation tests
│   └── test_config.py     # Configuration tests
├── config/                 # Configuration files
│   ├── config.yaml        # Main configuration
│   └── identity.json      # Sensor identity
├── data/                   # Data output
│   └── sensor_data.db     # SQLite database
└── logs/                   # Application logs
```

### Key Design Features

- **Resilient Database Operations**: Automatic retries with exponential backoff
- **Hot Configuration Reload**: Change settings without restart
- **Checkpoint System**: Resume from last state after interruption
- **Concurrent Safety**: WAL mode for multiple writers
- **Memory Efficient**: Streaming design, no large buffers
- **Container Optimized**: Built for Docker and Kubernetes

## 🔬 Advanced Usage

### Simulating Sensor Degradation

Model gradual sensor failure over time:

```yaml
# Start with low anomaly rate
anomalies:
  probability: 0.01  # 1% initially

# Use dynamic reload to increase over time:
# Hour 1: probability: 0.05
# Hour 2: probability: 0.10  
# Hour 3: probability: 0.25
```

### Multi-Location Deployment

Simulate a distributed sensor network:

```yaml
random_location:
  enabled: true
  number_of_cities: 20
  gps_variation: 500  # 500m radius

replicas:
  count: 20
  prefix: "GLOBAL"
```

### Stress Testing

Generate high-volume data:

```bash
# 100 sensors, 10 readings/second each
docker-compose up --scale sensor=100

# Or use configuration
replicas:
  count: 100
simulation:
  readings_per_second: 10
```

## 🤝 Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=src

# Run specific test
uv run pytest tests/test_simulator.py
```

### Building Docker Images

```bash
# Build local image
docker build -t sensor-simulator .

# Build multi-platform
./build.py

# Test the build
./test_container.sh
```

### Adding Features

The codebase is designed for extension:

1. **New Sensor Types**: Add to `src/simulator.py`
2. **Anomaly Patterns**: Extend `src/anomaly.py`
3. **Output Formats**: Modify `src/database.py`
4. **API Endpoints**: Update `src/monitor.py`

### Code Style

- Python 3.11+ with type hints
- Google-style docstrings
- Ruff for linting
- Black for formatting

## 🔧 Troubleshooting

### Common Issues

**Database Locked Error**
```bash
# Multiple writers competing
# Solution: Increase timeout or use single writer
database:
  busy_timeout: 60000  # 60 seconds
```

**Disk I/O Error in Containers**
```bash
# Set custom temp directory
docker run -v $(pwd)/data:/app/data \
  -e SQLITE_TMPDIR=/app/data/tmp \
  sensor-simulator

# Ensure permissions
chmod -R 755 data/
```

**High Memory Usage**
```yaml
# Reduce cache size
database:
  cache_size: 10000  # Smaller cache
simulation:
  batch_size: 100    # Smaller batches
```

**No Data Generated**
```bash
# Check logs for errors
tail -f logs/sensor_simulator.log

# Verify database exists
ls -la data/sensor_data.db

# Test with debug mode
docker run -e LOG_LEVEL=DEBUG sensor-simulator
```

### Performance Tuning

**For High-Volume Data**
- Use WAL mode (enabled by default)
- Increase cache_size for better performance
- Use batch inserts
- Consider PostgreSQL for > 1000 readings/sec

**For Long-Running Simulations**
- Enable checkpoint system
- Use log rotation
- Monitor disk space
- Set database size limits

## 📚 Resources

- **Documentation**: [CLAUDE.md](CLAUDE.md) for AI assistants
- **Examples**: See `config.example.yaml` for all options
- **Tests**: Browse `tests/` for usage examples
- **Support**: Open an issue on GitHub

## 📄 License

MIT License - See LICENSE file for details.

---

Built with ❤️ for reliable sensor data simulation and testing!
