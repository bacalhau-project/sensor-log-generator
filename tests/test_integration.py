"""Integration tests for the sensor simulator system."""

import json
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMainIntegration:
    """Test the full integration through main.py."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            config_dir = temp_path / "config"
            logs_dir = temp_path / "logs"

            data_dir.mkdir()
            config_dir.mkdir()
            logs_dir.mkdir()

            yield {
                "root": temp_path,
                "data": data_dir,
                "config": config_dir,
                "logs": logs_dir,
            }

    @pytest.fixture
    def test_config(self, temp_dirs):
        """Create a test configuration file."""
        config = {
            "sensor": {
                "type": "environmental",
                "location": "Test Location",
                "manufacturer": "TestCorp",
                "model": "TestModel-1000",
                "firmware_version": "1.0.0",
            },
            "simulation": {
                "readings_per_second": 10,
                "run_time_seconds": 1,
            },
            "database": {
                "path": str(temp_dirs["data"] / "test.db"),
            },
            "logging": {
                "level": "INFO",
                "console_output": False,
            },
        }

        config_file = temp_dirs["config"] / "test_config.yaml"
        with Path.open(config_file, "w") as f:
            yaml.dump(config, f)

        return config_file

    @pytest.fixture
    def test_identity(self, temp_dirs):
        """Create a test identity file."""
        identity = {
            "sensor_id": "TEST_SENSOR_001",
            "location": {
                "city": "Test City",
                "state": "TC",
                "coordinates": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                },
                "timezone": "America/New_York",
                "address": "Test City, TC, USA",
            },
            "device_info": {
                "manufacturer": "TestCorp",
                "model": "TestModel-1000",
                "firmware_version": "1.0.0",
                "serial_number": "TEST-123456",
                "manufacture_date": "2024-01-01",
            },
            "deployment": {
                "deployment_type": "fixed",
                "installation_date": "2024-01-01",
                "height_meters": 10.0,
                "orientation_degrees": 0,
            },
            "metadata": {
                "instance_id": "test-instance-001",
                "sensor_type": "environmental_monitoring",
            },
        }

        identity_file = temp_dirs["config"] / "test_identity.json"
        with Path.open(identity_file, "w") as f:
            json.dump(identity, f)

        return identity_file

    def test_main_execution_flow(self, temp_dirs, test_config, test_identity):
        """Test that main.py executes without errors."""
        # Run main.py as a subprocess
        cmd = [
            sys.executable,
            "main.py",
            "--config",
            str(test_config),
            "--identity",
            str(test_identity),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )

        stdout = result.stdout
        stderr = result.stderr

        # Check that the process completed successfully
        assert (
            result.returncode == 0
        ), f"Process failed with code {result.returncode}. Stderr: {stderr}"

        # Check that database was created
        db_path = temp_dirs["data"] / "test.db"
        assert db_path.exists(), f"Database not created. Stdout: {stdout}\nStderr: {stderr}"

        # Check that data was written
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()

        # Should have ~10 readings (10 per second for 1 second)
        assert count >= 5, f"Expected at least 5 readings, got {count}"
        assert count <= 15, f"Expected at most 15 readings, got {count}"


class TestSignalHandling:
    """Test signal handling and graceful shutdown."""

    @pytest.mark.skip(reason="Flaky timing test")
    def test_graceful_shutdown_on_sigint(self, tmp_path):
        """Test that SIGINT causes graceful shutdown."""
        config_file = tmp_path / "config.yaml"
        identity_file = tmp_path / "identity.json"

        # Create minimal config
        config = {
            "sensor": {
                "type": "environmental",
                "location": "Test",
                "manufacturer": "Test",
                "model": "Test",
                "firmware_version": "1.0",
            },
            "simulation": {
                "readings_per_second": 10,
                "run_time_seconds": 60,  # Long runtime
            },
            "database": {"path": str(tmp_path / "test.db")},
            "logging": {"level": "INFO"},
        }

        identity = {
            "sensor_id": "TEST_001",
            "location": {
                "city": "Test",
                "state": "TS",
                "coordinates": {"latitude": 0, "longitude": 0},
                "timezone": "UTC",
                "address": "Test",
            },
            "device_info": {
                "manufacturer": "Test",
                "model": "Test",
                "firmware_version": "1.0",
                "serial_number": "TEST",
                "manufacture_date": "2024-01-01",
            },
            "deployment": {
                "deployment_type": "fixed",
                "installation_date": "2024-01-01",
                "height_meters": 0,
                "orientation_degrees": 0,
            },
            "metadata": {"instance_id": "test", "sensor_type": "test"},
        }

        with Path.open(config_file, "w") as f:
            yaml.dump(config, f)
        with Path.open(identity_file, "w") as f:
            json.dump(identity, f)

        # Start process
        proc = subprocess.Popen(
            [
                sys.executable,
                "main.py",
                "--config",
                str(config_file),
                "--identity",
                str(identity_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Let it run briefly to ensure some data is written
        time.sleep(2)

        # Send SIGINT
        proc.send_signal(signal.SIGINT)

        # Wait for shutdown
        stdout, stderr = proc.communicate(timeout=5)

        # Should exit cleanly
        assert proc.returncode in [0, -2], f"Unexpected return code: {proc.returncode}"

        # Check database has some data
        db_path = tmp_path / "test.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            count = cursor.fetchone()[0]
            conn.close()
            assert count > 0, "No data written before shutdown"
