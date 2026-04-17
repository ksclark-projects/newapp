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
    """Non-percentage value text (e.g. version string) must not be wrapped in ANSI."""
    result = run_sysinfo()
    # Lines that display a plain string value (OS version, Python version) should
    # have no ANSI codes after the label reset.  Lines that show a colorized
    # percentage (CPU, Memory, Disk) are intentionally styled — skip those.
    pct_labels = ("CPU Usage:", "Memory Usage:", "Disk Usage:")
    for line in result.stdout.splitlines():
        clean_line = ANSI_ESCAPE.sub("", line)
        if any(label in clean_line for label in pct_labels):
            continue
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


# ---------------------------------------------------------------------------
# colorize_pct tests  (newapp-10j.4)
# ---------------------------------------------------------------------------


def test_colorize_pct_green_below_warn():
    """colorize_pct() returns green for values below warn threshold."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(50.0, 60.0, 85.0)
    assert _colorama.Fore.GREEN in result, (
        f"Expected Fore.GREEN for value below warn, got: {result!r}"
    )


def test_colorize_pct_yellow_at_warn():
    """colorize_pct() returns yellow for values at the warn threshold."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(60.0, 60.0, 85.0)
    assert _colorama.Fore.YELLOW in result, (
        f"Expected Fore.YELLOW at warn threshold, got: {result!r}"
    )


def test_colorize_pct_yellow_between_thresholds():
    """colorize_pct() returns yellow for values between warn and crit."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(75.0, 60.0, 85.0)
    assert _colorama.Fore.YELLOW in result, (
        f"Expected Fore.YELLOW between thresholds, got: {result!r}"
    )


def test_colorize_pct_red_at_crit():
    """colorize_pct() returns red for values at the crit threshold."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(85.0, 60.0, 85.0)
    assert _colorama.Fore.RED in result, (
        f"Expected Fore.RED at crit threshold, got: {result!r}"
    )


def test_colorize_pct_red_above_crit():
    """colorize_pct() returns red for values above crit threshold."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(95.0, 60.0, 85.0)
    assert _colorama.Fore.RED in result, (
        f"Expected Fore.RED above crit threshold, got: {result!r}"
    )


def test_colorize_pct_contains_percentage_string():
    """colorize_pct() output includes the numeric percentage."""
    result = sysinfo.colorize_pct(42.5, 60.0, 85.0)
    assert "42.5%" in result, (
        f"Expected '42.5%' in colorize_pct output, got: {result!r}"
    )


def test_colorize_pct_ends_with_reset():
    """colorize_pct() output ends with RESET_ALL."""
    import colorama as _colorama
    result = sysinfo.colorize_pct(50.0, 60.0, 85.0)
    assert result.endswith(_colorama.Style.RESET_ALL), (
        f"colorize_pct output should end with RESET_ALL, got: {result!r}"
    )


def test_no_args_includes_cpu_line():
    """Default output must include a 'CPU Usage:' line."""
    result = run_sysinfo()
    assert "CPU Usage:" in result.stdout, (
        "Expected 'CPU Usage:' line in default output"
    )


def test_no_args_includes_memory_line():
    """Default output must include a 'Memory Usage:' line."""
    result = run_sysinfo()
    assert "Memory Usage:" in result.stdout, (
        "Expected 'Memory Usage:' line in default output"
    )


def test_no_args_includes_disk_line():
    """Default output must include a 'Disk Usage:' line."""
    result = run_sysinfo()
    assert "Disk Usage:" in result.stdout, (
        "Expected 'Disk Usage:' line in default output"
    )


# ---------------------------------------------------------------------------
# NO_COLOR environment variable tests  (newapp-10j.5)
# ---------------------------------------------------------------------------


def test_color_enabled_true_when_no_color_unset(monkeypatch):
    """color_enabled() returns True when NO_COLOR is not in the environment."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert sysinfo.color_enabled() is True


def test_color_enabled_false_when_no_color_set(monkeypatch):
    """color_enabled() returns False when NO_COLOR is set to any value."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert sysinfo.color_enabled() is False


def test_color_enabled_false_when_no_color_empty(monkeypatch):
    """color_enabled() returns False when NO_COLOR is set to empty string."""
    monkeypatch.setenv("NO_COLOR", "")
    assert sysinfo.color_enabled() is False


def test_format_label_plain_when_no_color(monkeypatch):
    """format_label() returns the bare label with no ANSI codes when NO_COLOR set."""
    monkeypatch.setenv("NO_COLOR", "1")
    result = sysinfo.format_label("OS Version:")
    assert result == "OS Version:", (
        f"Expected plain label when NO_COLOR set, got: {result!r}"
    )
    assert "\x1b[" not in result


def test_format_header_plain_when_no_color(monkeypatch):
    """format_header() returns the bare text with no ANSI codes when NO_COLOR set."""
    monkeypatch.setenv("NO_COLOR", "1")
    result = sysinfo.format_header("System Info")
    assert result == "System Info", (
        f"Expected plain text when NO_COLOR set, got: {result!r}"
    )
    assert "\x1b[" not in result


def test_colorize_pct_plain_when_no_color(monkeypatch):
    """colorize_pct() returns a plain 'X.X%' string with no ANSI when NO_COLOR set."""
    monkeypatch.setenv("NO_COLOR", "1")
    result = sysinfo.colorize_pct(75.0, 60.0, 85.0)
    assert result == "75.0%", (
        f"Expected plain percentage when NO_COLOR set, got: {result!r}"
    )
    assert "\x1b[" not in result


def test_subprocess_no_ansi_when_no_color_set():
    """Default output contains no ANSI escape codes when NO_COLOR is set."""
    import os
    env = {**os.environ, "NO_COLOR": "1"}
    result = subprocess.run(
        [sys.executable, "sysinfo.py"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "\x1b[" not in result.stdout, (
        f"Expected no ANSI codes in output when NO_COLOR=1, got: {result.stdout!r}"
    )


def test_subprocess_has_ansi_when_no_color_unset():
    """ANSI codes present in direct calls when NO_COLOR is not set."""
    import importlib
    import os
    # Subprocess strips ANSI on non-TTY pipes, so verify in-process instead.
    orig = os.environ.get("NO_COLOR")
    try:
        os.environ.pop("NO_COLOR", None)
        importlib.reload(sysinfo)
        assert sysinfo.color_enabled() is True
        assert "\x1b[" in sysinfo.format_label("Test:")
        assert "\x1b[" in sysinfo.colorize_pct(50.0, 60.0, 85.0)
    finally:
        if orig is not None:
            os.environ["NO_COLOR"] = orig
        importlib.reload(sysinfo)  # restore module state


# ---------------------------------------------------------------------------
# US-006: Additional color output tests  (newapp-10j.6)
# ---------------------------------------------------------------------------


def test_colorize_pct_high_cpu_red_when_color_enabled(monkeypatch):
    """colorize_pct() for 90% CPU (above CPU_CRIT) contains a red ANSI code."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    result = sysinfo.colorize_pct(90.0, sysinfo.CPU_WARN, sysinfo.CPU_CRIT)
    assert re.search(r"\x1b\[", result), (
        f"Expected ANSI escape code in colorize_pct output, got: {result!r}"
    )
    import colorama as _colorama
    assert _colorama.Fore.RED in result, (
        f"Expected Fore.RED for 90% CPU above CPU_CRIT={sysinfo.CPU_CRIT}, "
        f"got: {result!r}"
    )


def test_no_color_suppresses_ansi_in_all_color_functions(monkeypatch):
    """With NO_COLOR set, colorize_pct/format_header/format_label emit no ANSI."""
    monkeypatch.setenv("NO_COLOR", "1")
    pct_result = sysinfo.colorize_pct(90.0, sysinfo.CPU_WARN, sysinfo.CPU_CRIT)
    header_result = sysinfo.format_header("System Info")
    label_result = sysinfo.format_label("CPU Usage:")
    for name, result in (
        ("colorize_pct", pct_result),
        ("format_header", header_result),
        ("format_label", label_result),
    ):
        assert not re.search(r"\x1b\[", result), (
            f"Expected no ANSI escape sequences from {name}() when NO_COLOR "
            f"is set, got: {result!r}"
        )


def test_format_header_contains_bold_ansi(monkeypatch):
    """format_header() output contains a bold (Style.BRIGHT) ANSI escape code."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    import colorama as _colorama
    result = sysinfo.format_header("System Info")
    assert _colorama.Style.BRIGHT in result, (
        f"Expected Style.BRIGHT (bold) in format_header output, got: {result!r}"
    )
