#!/usr/bin/env python
"""Manual CLI smoke test script.

This script tests the CLI validation logic without requiring a worker.
Run with: uv run python scripts/test_cli_manual.py
"""

import subprocess
import sys


def run_cmd(cmd: list, expect_error: bool = False) -> bool:
    """Run a command and check result."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if expect_error:
        success = result.returncode != 0
        status = "✓ Expected error" if success else "✗ Should have failed"
    else:
        success = result.returncode == 0
        status = "✓ Success" if success else "✗ Failed"

    print(f"\n{status}")
    return success


def main():
    print("SLEAP-RTC CLI Manual Smoke Tests")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Train --help shows new options
    print("\n\n[TEST 1] Train --help shows new options")
    result = subprocess.run(
        ["sleap-rtc", "train", "--help"],
        capture_output=True, text=True
    )
    if "--config" in result.stdout and "Examples:" in result.stdout:
        print("✓ Train help shows --config and examples")
        tests_passed += 1
    else:
        print("✗ Train help missing --config or examples")
        tests_failed += 1

    # Test 2: Track --help shows new options
    print("\n\n[TEST 2] Track --help shows new options")
    result = subprocess.run(
        ["sleap-rtc", "track", "--help"],
        capture_output=True, text=True
    )
    if "--batch-size" in result.stdout and "--peak-threshold" in result.stdout:
        print("✓ Track help shows new options")
        tests_passed += 1
    else:
        print("✗ Track help missing new options")
        tests_failed += 1

    # Test 3: Train requires --config or --pkg-path
    print("\n\n[TEST 3] Train requires job specification")
    result = subprocess.run(
        ["sleap-rtc", "train", "--room", "test"],
        capture_output=True, text=True
    )
    if result.returncode != 0 and "Must provide a job specification" in result.stderr:
        print("✓ Train correctly requires --config or --pkg-path")
        tests_passed += 1
    else:
        print("✗ Train should require job specification")
        tests_failed += 1

    # Test 4: Mutual exclusivity of --config and --pkg-path
    print("\n\n[TEST 4] --config and --pkg-path are mutually exclusive")
    result = subprocess.run(
        ["sleap-rtc", "train", "--room", "test",
         "--config", "/path/config.yaml", "--pkg-path", "/path/pkg.zip"],
        capture_output=True, text=True
    )
    if result.returncode != 0 and "mutually exclusive" in result.stderr:
        print("✓ Correctly rejects both --config and --pkg-path")
        tests_passed += 1
    else:
        print("✗ Should reject mutually exclusive options")
        tests_failed += 1

    # Test 5: Deprecation warning for --pkg-path
    print("\n\n[TEST 5] Deprecation warning for --pkg-path")
    result = subprocess.run(
        ["sleap-rtc", "train", "--room", "test", "--pkg-path", "/path/pkg.zip"],
        capture_output=True, text=True
    )
    if "DEPRECATION WARNING" in result.stderr:
        print("✓ Shows deprecation warning for --pkg-path")
        tests_passed += 1
    else:
        print("✗ Missing deprecation warning")
        tests_failed += 1

    # Test 6: Track requires --data-path and --model-paths
    print("\n\n[TEST 6] Track requires data and model paths")
    result = subprocess.run(
        ["sleap-rtc", "track", "--room", "test"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("✓ Track correctly requires --data-path and --model-paths")
        tests_passed += 1
    else:
        print("✗ Track should require data and model paths")
        tests_failed += 1

    # Summary
    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")

    if tests_failed == 0:
        print("\n✓ All CLI validation tests passed!")
        print("\nTo test full end-to-end functionality:")
        print("1. Start a worker: sleap-rtc worker --room test-room")
        print("2. Run train: sleap-rtc train --room test-room --config /path/config.yaml")
        print("3. Run track: sleap-rtc track --room test-room --data-path /path/data.slp --model-paths /path/model")
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
