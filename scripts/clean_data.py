#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Clean up test databases from the data directory.
Only sensor_data.db should exist in data/.
"""

from pathlib import Path


def clean_data_directory():
    """Remove all databases except sensor_data.db from data directory."""
    data_dir = Path("data")
    if not data_dir.exists():
        print("No data directory found")
        return

    # Find all database files
    db_files = list(data_dir.glob("*.db"))
    db_files.extend(data_dir.glob("*.db-*"))
    db_files.extend(data_dir.glob("*.sqlite"))
    db_files.extend(data_dir.glob("*.lock"))

    removed_count = 0
    kept_files = []

    for file in db_files:
        # Keep only sensor_data.db and its associated files
        if file.name.startswith("sensor_data.db"):
            kept_files.append(file.name)
        else:
            print(f"Removing: {file}")
            file.unlink()
            removed_count += 1

    print(f"\nCleaned up {removed_count} test database files")
    if kept_files:
        print(f"Kept: {', '.join(sorted(set(kept_files)))}")
    else:
        print("No sensor_data.db found (this is normal if sensor isn't running)")


if __name__ == "__main__":
    clean_data_directory()
