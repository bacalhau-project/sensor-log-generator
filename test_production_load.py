#!/usr/bin/env python3
"""
Production load test for simple database.
Tests aggressive writes with many simultaneous readers.
"""

import multiprocessing
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, Path(Path.absolute(__file__)).parent)

from src.database import SensorDatabase


def writer_process(db_path: str, process_id: int, num_writes: int, results_queue):
    """Simulate aggressive sensor writes."""
    try:
        # Each process gets its own database connection
        db = SensorDatabase(db_path, preserve_existing_db=True)

        start_time = time.time()

        for i in range(num_writes):
            db.insert_reading(
                sensor_id=f"SENSOR_{process_id:03d}",
                temperature=20.0 + (i % 10),
                vibration=0.1 + (i % 5) * 0.01,
                voltage=12.0 + (i % 3) * 0.1,
                status_code=0,
                anomaly_flag=(i % 20 == 0),  # 5% anomalies
                anomaly_type="spike" if i % 20 == 0 else None,
            )

            # Force commit every 10 writes to simulate realistic batching
            if (i + 1) % 10 == 0:
                db.commit_batch()

        # Final commit
        db.commit_batch()
        db.close()

        duration = time.time() - start_time
        writes_per_second = num_writes / duration

        results_queue.put(
            {
                "process_id": process_id,
                "num_writes": num_writes,
                "duration": duration,
                "writes_per_second": writes_per_second,
                "success": True,
            }
        )

    except Exception as e:
        results_queue.put({"process_id": process_id, "error": str(e), "success": False})


def reader_process(db_path: str, reader_id: int, duration: int, results_queue):
    """Simulate continuous reading from the database."""
    try:
        # Use read-only connection
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        start_time = time.time()
        total_reads = 0

        while time.time() - start_time < duration:
            cursor = conn.cursor()

            # Various read operations
            if total_reads % 3 == 0:
                # Get latest readings
                cursor.execute("""
                    SELECT * FROM sensor_readings
                    ORDER BY id DESC
                    LIMIT 100
                """)
            elif total_reads % 3 == 1:
                # Get unsynced readings
                cursor.execute("""
                    SELECT * FROM sensor_readings
                    WHERE synced = 0
                    LIMIT 50
                """)
            else:
                # Get count
                cursor.execute("SELECT COUNT(*) FROM sensor_readings")

            cursor.fetchall()  # Execute the query
            cursor.close()

            total_reads += 1
            time.sleep(0.1)  # Simulate processing time

        conn.close()

        actual_duration = time.time() - start_time
        reads_per_second = total_reads / actual_duration

        results_queue.put(
            {
                "reader_id": reader_id,
                "total_reads": total_reads,
                "duration": actual_duration,
                "reads_per_second": reads_per_second,
                "success": True,
            }
        )

    except Exception as e:
        results_queue.put({"reader_id": reader_id, "error": str(e), "success": False})


def main():
    print("=" * 60)
    print("PRODUCTION LOAD TEST FOR SIMPLE DATABASE")
    print("=" * 60)

    # Test configuration
    NUM_WRITERS = 5  # Concurrent writer processes
    NUM_READERS = 10  # Concurrent reader processes
    WRITES_PER_WRITER = 1000  # Each writer does 1000 inserts
    READER_DURATION = 10  # Readers run for 10 seconds

    print("\nConfiguration:")
    print(f"  Writers: {NUM_WRITERS} processes")
    print(f"  Readers: {NUM_READERS} processes")
    print(f"  Writes per writer: {WRITES_PER_WRITER}")
    print(f"  Reader duration: {READER_DURATION} seconds")
    print(f"  Total expected writes: {NUM_WRITERS * WRITES_PER_WRITER}")

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")

        # Initialize database
        print(f"\nInitializing database at {db_path}...")
        db = SensorDatabase(db_path)
        db.close()

        # Results queue for multiprocessing
        results_queue = multiprocessing.Queue()

        # Start writers
        print(f"\nStarting {NUM_WRITERS} writer processes...")
        writers = []
        for i in range(NUM_WRITERS):
            p = multiprocessing.Process(
                target=writer_process, args=(db_path, i, WRITES_PER_WRITER, results_queue)
            )
            p.start()
            writers.append(p)

        # Start readers
        print(f"Starting {NUM_READERS} reader processes...")
        readers = []
        for i in range(NUM_READERS):
            p = multiprocessing.Process(
                target=reader_process, args=(db_path, i, READER_DURATION, results_queue)
            )
            p.start()
            readers.append(p)

        # Wait for writers to finish
        print("\nWaiting for writers to complete...")
        for p in writers:
            p.join(timeout=30)

        # Wait for readers to finish
        print("Waiting for readers to complete...")
        for p in readers:
            p.join(timeout=15)

        # Collect results
        print("\nCollecting results...")
        writer_results = []
        reader_results = []

        while not results_queue.empty():
            result = results_queue.get()
            if "process_id" in result:
                writer_results.append(result)
            elif "reader_id" in result:
                reader_results.append(result)

        # Analyze writer results
        print("\n" + "=" * 40)
        print("WRITER RESULTS:")
        print("=" * 40)

        successful_writers = [r for r in writer_results if r.get("success")]
        failed_writers = [r for r in writer_results if not r.get("success")]

        if successful_writers:
            total_writes = sum(r["num_writes"] for r in successful_writers)
            total_duration = max(r["duration"] for r in successful_writers)
            avg_writes_per_second = sum(r["writes_per_second"] for r in successful_writers) / len(
                successful_writers
            )

            print(f"✅ Successful writers: {len(successful_writers)}/{NUM_WRITERS}")
            print(f"   Total writes: {total_writes}")
            print(f"   Max duration: {total_duration:.2f} seconds")
            print(f"   Avg writes/second per writer: {avg_writes_per_second:.1f}")
            print(f"   Total throughput: {total_writes / total_duration:.1f} writes/second")

        if failed_writers:
            print(f"❌ Failed writers: {len(failed_writers)}")
            for r in failed_writers:
                print(f"   Process {r.get('process_id', '?')}: {r.get('error', 'Unknown error')}")

        # Analyze reader results
        print("\n" + "=" * 40)
        print("READER RESULTS:")
        print("=" * 40)

        successful_readers = [r for r in reader_results if r.get("success")]
        failed_readers = [r for r in reader_results if not r.get("success")]

        if successful_readers:
            total_reads = sum(r["total_reads"] for r in successful_readers)
            avg_reads_per_second = sum(r["reads_per_second"] for r in successful_readers) / len(
                successful_readers
            )

            print(f"✅ Successful readers: {len(successful_readers)}/{NUM_READERS}")
            print(f"   Total reads: {total_reads}")
            print(f"   Avg reads/second per reader: {avg_reads_per_second:.1f}")
            print(f"   Total read throughput: {total_reads / READER_DURATION:.1f} reads/second")

        if failed_readers:
            print(f"❌ Failed readers: {len(failed_readers)}")
            for r in failed_readers:
                print(f"   Reader {r.get('reader_id', '?')}: {r.get('error', 'Unknown error')}")

        # Verify final database state
        print("\n" + "=" * 40)
        print("FINAL DATABASE VERIFICATION:")
        print("=" * 40)

        db = SensorDatabase(db_path, preserve_existing_db=True)
        stats = db.get_database_stats()

        expected_writes = NUM_WRITERS * WRITES_PER_WRITER
        actual_writes = stats["total_readings"]

        print(f"Expected writes: {expected_writes}")
        print(f"Actual writes: {actual_writes}")

        if actual_writes == expected_writes:
            print("✅ All writes successfully persisted!")
        else:
            diff = expected_writes - actual_writes
            print(f"⚠️  Missing {diff} writes ({diff / expected_writes * 100:.1f}%)")

        if "database_size_bytes" in stats:
            size_mb = stats["database_size_bytes"] / (1024 * 1024)
            print(f"Database size: {size_mb:.2f} MB")
            print(f"Bytes per record: {stats['database_size_bytes'] / max(1, actual_writes):.0f}")

        db.close()

        # Overall summary
        print("\n" + "=" * 40)
        print("TEST SUMMARY:")
        print("=" * 40)

        all_writers_succeeded = len(successful_writers) == NUM_WRITERS
        all_readers_succeeded = len(successful_readers) == NUM_READERS
        data_integrity = actual_writes == expected_writes

        if all_writers_succeeded and all_readers_succeeded and data_integrity:
            print("✅ TEST PASSED - Database handles production load!")
        else:
            print("❌ TEST FAILED - Issues detected:")
            if not all_writers_succeeded:
                print(f"   - {len(failed_writers)} writers failed")
            if not all_readers_succeeded:
                print(f"   - {len(failed_readers)} readers failed")
            if not data_integrity:
                print(
                    f"   - Data integrity issue: {expected_writes - actual_writes} missing writes"
                )


if __name__ == "__main__":
    main()
