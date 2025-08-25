#!/usr/bin/env python3
"""Run pytest tests serially to avoid timeout issues."""

import subprocess
import sys
from pathlib import Path


def run_tests_serially():
    """Run each test file individually."""
    test_dir = Path("tests")
    test_files = sorted(test_dir.glob("test_*.py"))

    failed_tests = []
    passed_count = 0
    failed_count = 0

    for test_file in test_files:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_file}")
        print("=" * 60)

        result = subprocess.run(
            ["uv", "run", "pytest", str(test_file), "-v", "--tb=short", "--timeout=10"],
            capture_output=False,
            text=True,
        )

        if result.returncode == 0:
            passed_count += 1
            print(f"✓ {test_file.name} PASSED")
        else:
            failed_count += 1
            failed_tests.append(test_file.name)
            print(f"✗ {test_file.name} FAILED")

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")

    if failed_tests:
        print("\nFailed tests:")
        for test in failed_tests:
            print(f"  - {test}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_tests_serially())
