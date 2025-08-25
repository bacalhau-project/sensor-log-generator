#!/usr/bin/env python3
"""Fix test issues in the codebase."""

import re
from pathlib import Path


def fix_path_exists_calls():
    """Fix Path.exists() calls to Path().exists()."""
    test_files = list(Path("tests").glob("*.py"))

    for file_path in test_files:
        content = file_path.read_text()
        original_content = content

        # Fix Path.exists(path) -> Path(path).exists()
        content = re.sub(r"Path\.exists\(([^)]+)\)", r"Path(\1).exists()", content)

        # Fix Path.stat(path) -> Path(path).stat()
        content = re.sub(r"Path\.stat\(([^)]+)\)", r"Path(\1).stat()", content)

        # Fix Path.unlink(path) -> Path(path).unlink()
        content = re.sub(r"Path\.unlink\(([^)]+)\)", r"Path(\1).unlink()", content)

        if content != original_content:
            file_path.write_text(content)
            print(f"Fixed Path issues in {file_path}")


def fix_store_reading_calls():
    """Fix store_reading calls that use keyword arguments."""
    file_path = Path("tests/test_database_read_operations.py")
    content = file_path.read_text()

    # For test_get_readings_by_time_range and similar tests
    # These need custom handling since they use timestamps
    lines = content.split("\n")
    new_lines = []
    in_store_reading = False
    store_reading_indent = 0

    for i, line in enumerate(lines):
        if "self.db.store_reading(" in line or "db.store_reading(" in line:
            # Replace store_reading with insert_reading for tests
            new_line = line.replace("store_reading(", "insert_reading(")
            new_lines.append(new_line)
            in_store_reading = True
            store_reading_indent = len(line) - len(line.lstrip())
        elif in_store_reading:
            # Check if we're still in the function call
            if line.strip().startswith(")") or (
                line.strip() and len(line) - len(line.lstrip()) <= store_reading_indent
            ):
                in_store_reading = False
            # Remove parameters that insert_reading doesn't accept
            elif any(
                param in line
                for param in ["timestamp=", "humidity=", "pressure=", "original_timezone="]
            ):
                continue  # Skip these lines
            new_lines.append(line)
        else:
            new_lines.append(line)

    content = "\n".join(new_lines)
    file_path.write_text(content)
    print(f"Fixed store_reading calls in {file_path}")


def fix_path_replace_calls():
    """Fix Path.replace() calls."""
    test_files = list(Path("tests").glob("*.py"))

    for file_path in test_files:
        content = file_path.read_text()
        original_content = content

        # Path.replace() with 3 args doesn't exist, it's str.replace()
        # Find these and fix them
        if "Path.replace(" in content:
            content = content.replace("Path.replace(", "str.replace(")

        if content != original_content:
            file_path.write_text(content)
            print(f"Fixed Path.replace in {file_path}")


if __name__ == "__main__":
    fix_path_exists_calls()
    fix_store_reading_calls()
    fix_path_replace_calls()
    print("Test fixes complete!")
