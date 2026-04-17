"""Tests for sysinfo.py."""

import subprocess
import sys


def run_sysinfo(*args):
    """Helper: run sysinfo.py as a subprocess, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "sysinfo.py", *args],
        capture_output=True,
        text=True,
        cwd=None,  # inherits the working directory set by pytest
    )


def test_python_version_exits_zero():
    """--python-version should exit with code 0."""
    result = run_sysinfo("--python-version")
    assert result.returncode == 0


def test_python_version_output_format():
    """--python-version should print MAJOR.MINOR.PATCH on stdout."""
    result = run_sysinfo("--python-version")
    output = result.stdout.strip()
    parts = output.split(".")
    assert len(parts) == 3, f"Expected 3 version parts, got: {output!r}"
    assert all(part.isdigit() for part in parts), (
        f"All parts should be numeric, got: {output!r}"
    )


def test_python_version_matches_sys():
    """--python-version output must match the running interpreter."""
    result = run_sysinfo("--python-version")
    output = result.stdout.strip()
    v = sys.version_info
    expected = f"{v.major}.{v.minor}.{v.micro}"
    assert output == expected, f"Expected {expected!r}, got {output!r}"


def test_no_args_exits_zero():
    """Running with no arguments should exit 0 (prints help)."""
    result = run_sysinfo()
    assert result.returncode == 0
