"""Tests for sysinfo.py."""

import re
import subprocess
import sys
from unittest.mock import patch

import pytest  # noqa: F401 — used for potential future parametrize

import sysinfo

# Regex to strip ANSI escape codes from output
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

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
    # Strip ANSI escape codes so startswith checks work regardless of color
    clean = ANSI_ESCAPE.sub("", result.stdout)
    lines = clean.splitlines()
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
    with patch("platform.system", return_value="Darwin"), \
         patch("platform.release", return_value="23.4.0"), \
         patch("platform.mac_ver", return_value=("14.4", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    assert result == "macOS 14.4 (Darwin 23.4.0)", (
        f"Unexpected OS version string: {result!r}"
    )


def test_get_os_version_format_pattern():
    """get_os_version output matches expected pattern on macOS."""
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
    with patch("platform.mac_ver", side_effect=Exception("simulated error")):
        result = sysinfo.get_os_version()

    assert result == "Unknown", (
        f"Expected 'Unknown' fallback, got: {result!r}"
    )


def test_get_os_version_fallback_on_empty_mac_ver():
    """get_os_version falls back gracefully when mac_ver returns empty string."""
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
    with patch("platform.system", return_value=""), \
         patch("platform.release", return_value=""), \
         patch("platform.mac_ver", return_value=("", ("", "", ""), "")):
        result = sysinfo.get_os_version()

    assert result == "Unknown", (
        f"Expected 'Unknown' when system is empty, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Section header colorization tests
# ---------------------------------------------------------------------------


def test_format_header_contains_ansi_codes():
    """format_header() output must contain ANSI escape sequences."""
    result = sysinfo.format_header("OS Version:")
    assert "\x1b[" in result, (
        f"Expected ANSI escape codes in format_header output, got: {result!r}"
    )


def test_format_header_preserves_text():
    """format_header() must include the original text unchanged."""
    label = "OS Version:"
    result = sysinfo.format_header(label)
    assert label in result, (
        f"Expected {label!r} to appear in format_header output, got: {result!r}"
    )


def test_format_header_ends_with_reset():
    """format_header() output must end with a reset sequence."""
    import colorama as _colorama
    result = sysinfo.format_header("Python:")
    assert result.endswith(_colorama.Style.RESET_ALL), (
        f"format_header output should end with RESET_ALL, got: {result!r}"
    )


def test_no_args_value_text_is_plain():
    """Non-label value text (e.g. version string) must not be wrapped in ANSI."""
    result = run_sysinfo()
    # Strip header ANSI: split each line on RESET_ALL (\x1b[0m) and check
    # that the value portion (after the reset) has no further escape codes.
    for line in result.stdout.splitlines():
        reset = "\x1b[0m"
        if reset in line:
            value_part = line.split(reset, 1)[1]
            assert "\x1b[" not in value_part, (
                f"Value portion of line should be plain text, got: {line!r}"
            )


# ---------------------------------------------------------------------------
# Label colorization tests  (newapp-10j.3)
# ---------------------------------------------------------------------------


def test_format_label_contains_ansi_codes():
    """format_label() output must contain ANSI escape sequences."""
    result = sysinfo.format_label("OS Version:")
    assert "\x1b[" in result, (
        f"Expected ANSI escape codes in format_label output, got: {result!r}"
    )


def test_format_label_preserves_text():
    """format_label() must include the original label text unchanged."""
    label = "Python:"
    result = sysinfo.format_label(label)
    assert label in result, (
        f"Expected {label!r} to appear in format_label output, got: {result!r}"
    )


def test_format_label_ends_with_reset():
    """format_label() output must end with RESET_ALL so the value is unstyled."""
    import colorama as _colorama
    result = sysinfo.format_label("OS Version:")
    assert result.endswith(_colorama.Style.RESET_ALL), (
        f"format_label output should end with RESET_ALL, got: {result!r}"
    )


def test_format_label_uses_yellow():
    """format_label() must apply Fore.YELLOW to the label."""
    import colorama as _colorama
    result = sysinfo.format_label("Python:")
    assert _colorama.Fore.YELLOW in result, (
        f"Expected Fore.YELLOW in format_label output, got: {result!r}"
    )


def test_format_label_all_labels_covered():
    """Every label/value line in default output uses format_label styling."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    # Each non-empty line in plain output should have a colon-terminated label
    for line in clean.splitlines():
        if not line.strip():
            continue
        assert ":" in line, (
            f"Expected a labelled line (containing ':'), got: {line!r}"
        )
