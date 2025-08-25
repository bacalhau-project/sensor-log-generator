import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.database import SensorDatabase, SensorReadingSchema


class TestSensorDatabase:
    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_init_creates_database(self):
        """Test that database is created successfully."""
        db = SensorDatabase(self.db_path)
        assert Path(self.db_path).exists()
        assert db.is_healthy()
        db.close()

    def test_init_preserves_existing_db(self):
        """Test that existing database is preserved when requested."""
        # Create initial database
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="TEST001", temperature=25.0, vibration=0.1, voltage=12.0, status_code=0
        )
        db1.commit_batch()
        db1.close()

        # Open with preserve flag
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        readings = db2.get_readings()
        assert len(readings) == 1
        assert readings[0]["sensor_id"] == "TEST001"
        db2.close()

    def test_init_deletes_existing_db(self):
        """Test that existing database is deleted by default."""
        # Create initial database
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="TEST001", temperature=25.0, vibration=0.1, voltage=12.0, status_code=0
        )
        db1.commit_batch()
        db1.close()

        # Open without preserve flag (should delete)
        db2 = SensorDatabase(self.db_path, preserve_existing_db=False)
        readings = db2.get_readings()
        assert len(readings) == 0
        db2.close()

    def test_store_reading(self):
        """Test storing a reading using Pydantic schema."""
        db = SensorDatabase(self.db_path)

        reading = SensorReadingSchema(
            timestamp=datetime.now(UTC).isoformat(),
            sensor_id="TEST001",
            temperature=25.0,
            humidity=60.0,
            pressure=1013.25,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
        )

        db.store_reading(reading)
        db.commit_batch()

        readings = db.get_readings()
        assert len(readings) == 1
        assert readings[0]["sensor_id"] == "TEST001"
        assert readings[0]["temperature"] == 25.0
        db.close()

    def test_get_unsynced_readings(self):
        """Test getting unsynced readings."""
        db = SensorDatabase(self.db_path)

        # Insert some readings
        for i in range(5):
            db.insert_reading(
                sensor_id=f"TEST{i:03d}",
                temperature=20.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )
        db.commit_batch()

        # Get unsynced readings
        unsynced = db.get_unsynced_readings(limit=3)
        assert len(unsynced) == 3
        assert all(r["synced"] == 0 for r in unsynced)

        db.close()

    def test_mark_readings_as_synced(self):
        """Test marking readings as synced."""
        db = SensorDatabase(self.db_path)

        # Insert readings
        for i in range(3):
            db.insert_reading(
                sensor_id=f"TEST{i:03d}",
                temperature=20.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )
        db.commit_batch()

        # Get readings and mark as synced
        readings = db.get_unsynced_readings()
        reading_ids = [r["id"] for r in readings]
        db.mark_readings_as_synced(reading_ids)

        # Verify they're marked as synced
        unsynced = db.get_unsynced_readings()
        assert len(unsynced) == 0

        stats = db.get_reading_stats()
        assert stats["synced_readings"] == 3
        assert stats["unsynced_readings"] == 0

        db.close()

    def test_get_reading_stats(self):
        """Test getting reading statistics."""
        db = SensorDatabase(self.db_path)

        # Insert readings
        for i in range(10):
            db.insert_reading(
                sensor_id=f"TEST{i:03d}",
                temperature=20.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )
        db.commit_batch()

        stats = db.get_reading_stats()
        assert stats["total_readings"] == 10
        assert stats["unsynced_readings"] == 10
        assert stats["synced_readings"] == 0

        db.close()

    def test_is_healthy(self):
        """Test database health check."""
        db = SensorDatabase(self.db_path)
        assert db.is_healthy() is True

        # Close and check again
        db.close()
        assert db.is_healthy() is False

    def test_batch_operations(self):
        """Test batch insert operations."""
        db = SensorDatabase(self.db_path)
        db.batch_size = 5

        # Insert exactly batch_size readings
        for i in range(5):
            db.insert_reading(
                sensor_id=f"BATCH{i:03d}",
                temperature=25.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )

        # Should auto-commit when batch size reached
        readings = db.get_readings()
        assert len(readings) == 5

        db.close()

    def test_database_error_handling(self):
        """Test error handling for invalid operations."""
        db = SensorDatabase(self.db_path)

        # Try to mark non-existent readings as synced
        db.mark_readings_as_synced([999, 1000])  # Should not raise

        # Try to get readings with invalid limit
        readings = db.get_readings(limit=-1)
        assert isinstance(readings, list)

        db.close()

    def test_memory_database(self):
        """Test in-memory database functionality."""
        db = SensorDatabase(":memory:")

        # Insert data
        db.insert_reading(
            sensor_id="MEMORY001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
        )
        db.commit_batch()

        # Verify data
        readings = db.get_readings()
        assert len(readings) == 1
        assert readings[0]["sensor_id"] == "MEMORY001"

        # Check stats
        stats = db.get_database_stats()
        assert stats["total_readings"] == 1
        assert "database_size_bytes" not in stats  # No file size for in-memory

        db.close()
