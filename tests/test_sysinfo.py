"""Tests for sysinfo.py."""

import subprocess
import sys
from unittest.mock import patch

import pytest  # noqa: F401 — used for potential future parametrize

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_sysinfo(*args):
    """Helper: run sysinfo.py as a subprocess, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "sysinfo.py", *args],
        capture_output=True,
        text=True,
        cwd=None,  # inherits the working directory set by pytest
    )


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


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
    """Running with no arguments should exit 0."""
    result = run_sysinfo()
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# OS version tests
# ---------------------------------------------------------------------------


def test_no_args_includes_os_version_line():
    """Running with no arguments should include an 'OS Version:' line."""
    result = run_sysinfo()
    assert result.returncode == 0
    assert "OS Version:" in result.stdout


def test_no_args_os_version_before_python():
    """OS Version line must appear before Python line in default output."""
    result = run_sysinfo()
    lines = result.stdout.splitlines()
    os_idx = next(
        (i for i, l in enumerate(lines) if l.startswith("OS Version:")), None
    )
    py_idx = next(
        (i for i, l in enumerate(lines) if l.startswith("Python:")), None
    )
    assert os_idx is not None, "OS Version line not found in output"
    assert py_idx is not None, "Python line not found in output"
    assert os_idx < py_idx, (
        "OS Version line should appear before Python line"
    )


def test_get_os_version_happy_path():
    """get_os_version returns a properly formatted string on macOS."""
    # Import here so we can mock platform internals directly
    import sysinfo

    with patch("platform.system", return_value="Darwin"), \
         patch("platform.release", return_value="23.4.0"), \
         patch("platform.mac_ver", return_value=("14.4", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    assert result == "macOS 14.4 (Darwin 23.4.0)", (
        f"Unexpected OS version string: {result!r}"
    )


def test_get_os_version_format_pattern():
    """get_os_version output matches expected pattern on macOS."""
    import re
    import sysinfo

    with patch("platform.system", return_value="Darwin"), \
         patch("platform.release", return_value="23.4.0"), \
         patch("platform.mac_ver", return_value=("14.4", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    pattern = r"^.+ .+ \(.+ .+\)$"
    assert re.match(pattern, result), (
        f"OS version string {result!r} does not match expected format "
        "'<name> <version> (<kernel> <build>)'"
    )


def test_get_os_version_fallback_on_exception():
    """get_os_version returns 'Unknown' when platform.mac_ver raises."""
    import sysinfo

    with patch("platform.mac_ver", side_effect=Exception("simulated error")):
        result = sysinfo.get_os_version()

    assert result == "Unknown", (
        f"Expected 'Unknown' fallback, got: {result!r}"
    )


def test_get_os_version_fallback_on_empty_mac_ver():
    """get_os_version falls back gracefully when mac_ver returns empty string."""
    import sysinfo

    # mac_ver returns empty version string — non-macOS path
    with patch("platform.system", return_value="Linux"), \
         patch("platform.release", return_value="5.15.0"), \
         patch("platform.mac_ver", return_value=("", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    # Should fall back to generic "system release" format
    assert "Linux" in result or result == "Unknown", (
        f"Unexpected fallback value: {result!r}"
    )


def test_get_os_version_fallback_on_empty_system():
    """get_os_version returns 'Unknown' when platform.system() returns empty."""
    import sysinfo

    with patch("platform.system", return_value=""), \
         patch("platform.release", return_value=""), \
         patch("platform.mac_ver", return_value=("", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    assert result == "Unknown", (
        f"Expected 'Unknown' when system is empty, got: {result!r}"
    )
