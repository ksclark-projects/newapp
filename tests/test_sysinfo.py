"""Tests for sysinfo.py."""

import json
import re
import subprocess
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import psutil
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
    # Table header and process data rows from --top output do not use the
    # label format; skip them when checking for colon-terminated labels.
    for line in clean.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip process table header and data rows — they don't use label: format
        if stripped.startswith("PID") or stripped.startswith("Top "):
            continue
        if line.startswith("  ") and stripped[:1].isdigit():
            continue
        assert ":" in stripped, (
            f"Expected a labelled line (containing ':'), got: {stripped!r}"
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
# Per-core CPU tests  (newapp-pc8)
# ---------------------------------------------------------------------------


def test_get_cpu_cores_returns_list():
    """get_cpu_cores() returns a non-empty list."""
    result = sysinfo.get_cpu_cores()
    assert isinstance(result, list), (
        f"Expected list from get_cpu_cores(), got: {type(result)}"
    )
    assert len(result) > 0, "Expected at least one core"


def test_get_cpu_cores_values_in_range():
    """get_cpu_cores() values are floats in 0.0–100.0."""
    cores = sysinfo.get_cpu_cores()
    for i, pct in enumerate(cores):
        assert isinstance(pct, float), (
            f"Core {i} value should be float, got {type(pct)}: {pct!r}"
        )
        assert 0.0 <= pct <= 100.0, (
            f"Core {i} percentage {pct} out of range [0.0, 100.0]"
        )


def test_get_cpu_cores_count_matches_psutil():
    """get_cpu_cores() returns one entry per logical CPU."""
    expected = psutil.cpu_count(logical=True)
    assert len(sysinfo.get_cpu_cores()) == expected, (
        f"Expected {expected} core entries, "
        f"got {len(sysinfo.get_cpu_cores())}"
    )


def test_no_args_includes_core_lines():
    """Default output must include at least one 'Core N:' line."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    core_lines = [ln for ln in clean.splitlines() if "Core " in ln and ":" in ln]
    assert len(core_lines) > 0, (
        "Expected at least one 'Core N:' line in default output"
    )


def test_no_args_core_count_matches_cpu_count():
    """Number of 'Core N:' lines equals the logical CPU count."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    core_lines = [ln for ln in clean.splitlines() if "Core " in ln and ":" in ln]
    expected = psutil.cpu_count(logical=True)
    assert len(core_lines) == expected, (
        f"Expected {expected} core lines, got {len(core_lines)}"
    )


def test_no_args_core_lines_contain_percentage():
    """Each 'Core N:' line in output contains a percentage value."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    core_lines = [ln for ln in clean.splitlines() if "Core " in ln and ":" in ln]
    for line in core_lines:
        assert re.search(r"\d+\.\d+%", line), (
            f"Core line missing percentage value: {line!r}"
        )


def test_no_args_core_lines_after_cpu_usage():
    """Per-core lines appear immediately after the 'CPU Usage:' line."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    lines = clean.splitlines()
    cpu_idx = next(
        (i for i, l in enumerate(lines) if l.startswith("CPU Usage:")), None
    )
    assert cpu_idx is not None, "CPU Usage line not found"
    # The line right after CPU Usage should be a core line
    assert cpu_idx + 1 < len(lines), "No line after CPU Usage"
    assert "Core 0:" in lines[cpu_idx + 1], (
        f"Expected 'Core 0:' after CPU Usage line, got: {lines[cpu_idx+1]!r}"
    )


def test_get_cpu_cores_mocked():
    """get_cpu_cores() returns the mocked per-core list."""
    mock_cores = [10.0, 20.0, 30.0, 40.0]
    with patch("psutil.cpu_percent", return_value=mock_cores):
        result = sysinfo.get_cpu_cores()
    assert result == mock_cores, (
        f"Expected mocked core list {mock_cores!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Top processes tests  (newapp-leh)
# ---------------------------------------------------------------------------


def _make_mock_proc(pid, name, cpu_pct, mem_pct):
    """Return a MagicMock that mimics a psutil.Process with .info dict."""
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.info = {
        'pid': pid,
        'name': name,
        'cpu_percent': cpu_pct,
        'memory_percent': mem_pct,
    }
    return proc


def test_get_top_processes_returns_list():
    """get_top_processes() returns a list."""
    result = sysinfo.get_top_processes(n=5)
    assert isinstance(result, list), (
        f"Expected list from get_top_processes(), got: {type(result)}"
    )


def test_get_top_processes_respects_n():
    """get_top_processes(n) returns at most n entries."""
    procs = [_make_mock_proc(i, f"proc{i}", float(i), 1.0) for i in range(20)]
    with patch("psutil.process_iter", return_value=procs):
        result = sysinfo.get_top_processes(n=5)
    assert len(result) <= 5, (
        f"Expected at most 5 processes, got {len(result)}"
    )


def test_get_top_processes_sorted_by_cpu_descending():
    """get_top_processes() returns entries sorted by cpu_pct descending."""
    procs = [
        _make_mock_proc(1, "low",  10.0, 1.0),
        _make_mock_proc(2, "high", 80.0, 2.0),
        _make_mock_proc(3, "mid",  40.0, 1.5),
    ]
    with patch("psutil.process_iter", return_value=procs):
        result = sysinfo.get_top_processes(n=3)
    cpu_values = [p['cpu_pct'] for p in result]
    assert cpu_values == sorted(cpu_values, reverse=True), (
        f"Expected descending CPU order, got: {cpu_values}"
    )


def test_get_top_processes_entry_keys():
    """Each entry from get_top_processes() has pid, name, cpu_pct, mem_pct."""
    procs = [_make_mock_proc(42, "test_proc", 5.0, 1.2)]
    with patch("psutil.process_iter", return_value=procs):
        result = sysinfo.get_top_processes(n=1)
    assert len(result) == 1
    entry = result[0]
    for key in ('pid', 'name', 'cpu_pct', 'mem_pct'):
        assert key in entry, f"Expected key '{key}' in process entry, got: {entry}"


def test_get_top_processes_skips_noaccess():
    """get_top_processes() silently skips inaccessible processes."""
    good = _make_mock_proc(1, "good", 5.0, 1.0)
    bad_proc = MagicMock(spec=psutil.Process)
    type(bad_proc).info = PropertyMock(
        side_effect=psutil.AccessDenied(pid=2, name="restricted")
    )
    with patch("psutil.process_iter", return_value=[good, bad_proc]):
        result = sysinfo.get_top_processes(n=10)
    pids = [p['pid'] for p in result]
    assert 1 in pids, "Expected accessible process to be included"


def test_no_args_includes_top_processes_section():
    """Default output (--top 10) includes the 'Top N Processes' header."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    assert "Top 10 Processes" in clean, (
        "Expected 'Top 10 Processes' section in default output"
    )


def test_top_flag_limits_processes():
    """--top 3 output includes at most 3 process data rows."""
    result = run_sysinfo("--top", "3")
    assert result.returncode == 0
    clean = ANSI_ESCAPE.sub("", result.stdout)
    # Count indented rows that start with a digit (PID column)
    proc_rows = [
        ln for ln in clean.splitlines()
        if ln.startswith("  ") and ln.strip()[:1].isdigit()
    ]
    assert len(proc_rows) <= 3, (
        f"Expected at most 3 process rows with --top 3, got {len(proc_rows)}"
    )


def test_top_zero_suppresses_section():
    """--top 0 suppresses the top-processes section entirely."""
    result = run_sysinfo("--top", "0")
    assert result.returncode == 0
    assert "Top " not in result.stdout, (
        "Expected no 'Top N Processes' section when --top 0"
    )
    assert "PID" not in result.stdout, (
        "Expected no process table when --top 0"
    )


def test_top_processes_output_contains_pid_and_name():
    """Top-processes output lines contain PID and name columns."""
    result = run_sysinfo("--top", "5")
    clean = ANSI_ESCAPE.sub("", result.stdout)
    # The header row should contain PID and Name labels
    assert "PID" in clean, "Expected 'PID' column header in output"
    assert "Name" in clean, "Expected 'Name' column header in output"


# ---------------------------------------------------------------------------
# Disk per-mount tests  (newapp-5pj)
# ---------------------------------------------------------------------------


def test_get_disk_mounts_returns_list():
    """get_disk_mounts() returns a non-empty list."""
    result = sysinfo.get_disk_mounts()
    assert isinstance(result, list), (
        f"Expected list from get_disk_mounts(), got: {type(result)}"
    )
    assert len(result) > 0, "Expected at least one mount point"


def test_get_disk_mounts_entry_keys():
    """Each get_disk_mounts() entry has the required keys."""
    required = {"mount", "used_gb", "free_gb", "total_gb", "percent"}
    for entry in sysinfo.get_disk_mounts():
        missing = required - entry.keys()
        assert not missing, (
            f"Mount entry missing keys {missing}: {entry!r}"
        )


def test_get_disk_mounts_numeric_values():
    """get_disk_mounts() entries have numeric GB and percent values in range."""
    for entry in sysinfo.get_disk_mounts():
        for key in ("used_gb", "free_gb", "total_gb"):
            assert isinstance(entry[key], (int, float)) and entry[key] >= 0, (
                f"{key} should be a non-negative number, got: {entry[key]!r}"
            )
        assert 0.0 <= entry["percent"] <= 100.0, (
            f"percent should be 0-100, got: {entry['percent']!r}"
        )


def test_get_disk_mounts_total_ge_used():
    """total_gb >= used_gb for every mount point."""
    for entry in sysinfo.get_disk_mounts():
        assert entry["total_gb"] >= entry["used_gb"], (
            f"total_gb {entry['total_gb']} < used_gb {entry['used_gb']} "
            f"for mount {entry['mount']!r}"
        )


def test_get_disk_mounts_mocked():
    """get_disk_mounts() uses disk_partitions and disk_usage correctly."""
    from collections import namedtuple
    FakePart = namedtuple("FakePart", ["mountpoint"])
    FakeUsage = namedtuple("FakeUsage", ["used", "free", "total", "percent"])

    fake_parts = [FakePart("/"), FakePart("/data")]
    fake_usages = {
        "/": FakeUsage(used=10 * 1024**3, free=90 * 1024**3,
                       total=100 * 1024**3, percent=10.0),
        "/data": FakeUsage(used=50 * 1024**3, free=50 * 1024**3,
                           total=100 * 1024**3, percent=50.0),
    }

    with patch("psutil.disk_partitions", return_value=fake_parts), \
         patch("psutil.disk_usage", side_effect=lambda mp: fake_usages[mp]):
        result = sysinfo.get_disk_mounts()

    assert len(result) == 2
    assert result[0]["mount"] == "/"
    assert result[0]["used_gb"] == 10.0
    assert result[0]["free_gb"] == 90.0
    assert result[0]["total_gb"] == 100.0
    assert result[0]["percent"] == 10.0
    assert result[1]["mount"] == "/data"
    assert result[1]["percent"] == 50.0


def test_get_disk_mounts_skips_inaccessible():
    """get_disk_mounts() silently skips mount points that raise OSError."""
    from collections import namedtuple
    FakePart = namedtuple("FakePart", ["mountpoint"])

    fake_parts = [FakePart("/"), FakePart("/secret")]

    def fake_usage(mp):
        if mp == "/secret":
            raise PermissionError("no access")
        from collections import namedtuple as nt
        U = nt("U", ["used", "free", "total", "percent"])
        return U(used=10 * 1024**3, free=90 * 1024**3,
                 total=100 * 1024**3, percent=10.0)

    with patch("psutil.disk_partitions", return_value=fake_parts), \
         patch("psutil.disk_usage", side_effect=fake_usage):
        result = sysinfo.get_disk_mounts()

    assert len(result) == 1
    assert result[0]["mount"] == "/"


def test_json_flag_outputs_valid_json():
    """--json flag produces valid JSON with a 'disk' key."""
    result = run_sysinfo("--json")
    assert result.returncode == 0, (
        f"Expected exit 0 with --json, got {result.returncode}"
    )
    data = json.loads(result.stdout)
    assert "disk" in data, f"Expected 'disk' key in JSON output: {data!r}"
    assert isinstance(data["disk"], list), (
        f"Expected 'disk' to be a list, got: {type(data['disk'])}"
    )


def test_json_flag_disk_entries_have_required_keys():
    """--json disk entries contain mount, used_gb, free_gb, total_gb, percent."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    required = {"mount", "used_gb", "free_gb", "total_gb", "percent"}
    for entry in data["disk"]:
        missing = required - entry.keys()
        assert not missing, (
            f"JSON disk entry missing keys {missing}: {entry!r}"
        )


def test_no_args_includes_disk_header():
    """Default output shows 'Disk Usage:' as a section header."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    assert "Disk Usage:" in clean, (
        "Expected 'Disk Usage:' header in default output"
    )


def test_no_args_disk_shows_per_mount():
    """Default output shows at least one per-mount line with GiB info."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    assert "GiB" in clean, (
        "Expected per-mount GiB info in default output"
    )


def test_no_args_disk_mount_lines_have_percentage():
    """Each per-mount disk line in default output includes a percentage."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    # Find indented lines under Disk Usage section
    mount_lines = [
        ln for ln in clean.splitlines()
        if ln.startswith("  ") and "GiB" in ln
    ]
    assert len(mount_lines) > 0, "Expected at least one mount line with GiB"
    for line in mount_lines:
        assert re.search(r"\d+\.\d+%", line), (
            f"Mount line missing percentage: {line!r}"
        )


# ---------------------------------------------------------------------------
# Memory details tests  (newapp-528)
# ---------------------------------------------------------------------------


def test_get_mem_details_returns_dict():
    """get_mem_details() returns a dict with the required keys."""
    result = sysinfo.get_mem_details()
    assert isinstance(result, dict), (
        f"Expected dict from get_mem_details(), got: {type(result)}"
    )
    for key in ("used_mb", "free_mb", "cached_mb", "total_mb"):
        assert key in result, f"Expected key '{key}' in mem details: {result}"


def test_get_mem_details_values_are_numeric():
    """get_mem_details() values are numeric (int or float)."""
    result = sysinfo.get_mem_details()
    for key, val in result.items():
        assert isinstance(val, (int, float)), (
            f"Expected numeric for '{key}', got {type(val)}: {val!r}"
        )


def test_get_mem_details_total_positive():
    """get_mem_details() total_mb is a positive number."""
    result = sysinfo.get_mem_details()
    assert result["total_mb"] > 0, (
        f"Expected total_mb > 0, got: {result['total_mb']}"
    )


def test_get_mem_details_used_le_total():
    """get_mem_details() used_mb does not exceed total_mb."""
    result = sysinfo.get_mem_details()
    assert result["used_mb"] <= result["total_mb"], (
        f"used_mb {result['used_mb']} exceeds total_mb {result['total_mb']}"
    )


def test_get_mem_details_mocked():
    """get_mem_details() maps psutil fields correctly when mocked."""
    mock_vm = MagicMock()
    mock_vm.used = 8 * 1024 * 1024 * 1024       # 8 GiB
    mock_vm.available = 4 * 1024 * 1024 * 1024  # 4 GiB
    mock_vm.total = 16 * 1024 * 1024 * 1024     # 16 GiB
    del mock_vm.cached  # cached not available on this platform
    with patch("psutil.virtual_memory", return_value=mock_vm):
        result = sysinfo.get_mem_details()
    assert result["used_mb"] == round(8 * 1024, 1)
    assert result["free_mb"] == round(4 * 1024, 1)
    assert result["total_mb"] == round(16 * 1024, 1)
    assert result["cached_mb"] == 0.0


def test_no_args_memory_line_includes_used_free_total():
    """Default output Memory Usage line includes used/free/total strings."""
    result = run_sysinfo()
    clean = ANSI_ESCAPE.sub("", result.stdout)
    mem_line = next(
        (ln for ln in clean.splitlines() if ln.startswith("Memory Usage:")),
        None,
    )
    assert mem_line is not None, "No 'Memory Usage:' line in output"
    assert "used" in mem_line, f"Expected 'used' in memory line: {mem_line!r}"
    assert "free" in mem_line, f"Expected 'free' in memory line: {mem_line!r}"
    assert "total" in mem_line, f"Expected 'total' in memory line: {mem_line!r}"


def test_json_flag_includes_memory_key():
    """--json output includes a 'memory' key with the required fields."""
    result = run_sysinfo("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "memory" in data, (
        f"Expected 'memory' key in --json output, got: {list(data)}"
    )
    for key in ("used_mb", "free_mb", "cached_mb", "total_mb"):
        assert key in data["memory"], (
            f"Expected '{key}' in memory JSON: {list(data['memory'])}"
        )


# ---------------------------------------------------------------------------
# Full --json output tests  (newapp-850 / US-006)
# ---------------------------------------------------------------------------


def test_json_flag_exits_zero():
    """--json flag exits with code 0."""
    result = run_sysinfo("--json")
    assert result.returncode == 0, (
        f"Expected exit 0 with --json, got {result.returncode}"
    )


def test_json_flag_contains_all_top_level_keys():
    """--json output contains all required top-level keys."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    for key in ("python_version", "cpu", "memory", "disk", "top_processes"):
        assert key in data, (
            f"Expected key '{key}' in --json output, got: {list(data)}"
        )


def test_json_flag_cpu_has_overall_and_cores():
    """--json cpu value has 'overall' (float) and 'cores' (list)."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    cpu = data["cpu"]
    assert "overall" in cpu, f"Expected 'overall' in cpu: {cpu!r}"
    assert "cores" in cpu, f"Expected 'cores' in cpu: {cpu!r}"
    assert isinstance(cpu["overall"], float), (
        f"Expected cpu.overall to be float, got {type(cpu['overall'])}"
    )
    assert isinstance(cpu["cores"], list), (
        f"Expected cpu.cores to be list, got {type(cpu['cores'])}"
    )
    assert len(cpu["cores"]) > 0, "Expected at least one core in cpu.cores"


def test_json_flag_python_version_format():
    """--json python_version matches MAJOR.MINOR.PATCH format."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    parts = data["python_version"].split(".")
    assert len(parts) == 3, (
        f"Expected 3-part version, got: {data['python_version']!r}"
    )
    assert all(p.isdigit() for p in parts), (
        f"All version parts should be numeric: {data['python_version']!r}"
    )


def test_json_flag_top_processes_is_list():
    """--json top_processes value is a list."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    assert isinstance(data["top_processes"], list), (
        f"Expected top_processes to be list, got {type(data['top_processes'])}"
    )


def test_json_flag_top_processes_entry_keys():
    """--json top_processes entries have pid, name, cpu_pct, mem_pct."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    for entry in data["top_processes"]:
        for key in ("pid", "name", "cpu_pct", "mem_pct"):
            assert key in entry, (
                f"Expected key '{key}' in top_processes entry: {entry!r}"
            )


def test_fmt_size_under_1024_returns_mb():
    """_fmt_size() returns MB string for values under 1024."""
    assert sysinfo._fmt_size(512.0) == "512 MB"
    assert sysinfo._fmt_size(0.0) == "0 MB"


def test_fmt_size_1024_or_over_returns_gb():
    """_fmt_size() returns GB string for values >= 1024."""
    assert sysinfo._fmt_size(1024.0) == "1.0 GB"
    assert sysinfo._fmt_size(8192.0) == "8.0 GB"


# ---------------------------------------------------------------------------
# Additional tests addressing Riley's review (PR #18)
# ---------------------------------------------------------------------------


def test_json_flag_top_zero_returns_empty_processes():
    """--json --top 0 outputs top_processes as an empty list."""
    result = run_sysinfo("--json", "--top", "0")
    assert result.returncode == 0, (
        f"Expected exit 0 with --json --top 0, got {result.returncode}"
    )
    data = json.loads(result.stdout)
    assert "top_processes" in data, "Expected top_processes key in JSON output"
    assert data["top_processes"] == [], (
        f"Expected empty list for top_processes with --top 0, "
        f"got: {data['top_processes']!r}"
    )


def test_top_negative_exits_nonzero():
    """--top with a negative value should exit non-zero with an error message."""
    result = run_sysinfo("--top", "-1")
    assert result.returncode != 0, (
        "Expected non-zero exit code for --top -1"
    )
    # argparse writes errors to stderr
    assert result.stderr, "Expected error message on stderr for --top -1"


def test_mem_pct_zero_total_does_not_crash():
    """main() must not raise ZeroDivisionError when total_mb is 0."""
    zero_mem = {
        "used_mb": 0.0,
        "free_mb": 0.0,
        "cached_mb": 0.0,
        "total_mb": 0.0,
    }
    with patch.object(sysinfo, "get_mem_details", return_value=zero_mem), \
         patch.object(sysinfo, "get_disk_mounts", return_value=[]), \
         patch.object(sysinfo, "get_top_processes", return_value=[]), \
         patch.object(sysinfo, "get_cpu_pct", return_value=0.0), \
         patch.object(sysinfo, "get_cpu_cores", return_value=[0.0]), \
         patch.object(sysinfo, "get_os_version", return_value="Test OS 1.0"), \
         patch.object(sysinfo, "get_python_version", return_value="3.0.0"):
        import argparse as _argparse

        class _Args:
            command = None
            json = False
            python_version = False
            top = 0

        def _fake_parse(self, args=None, namespace=None):
            return _Args()

        with patch.object(_argparse.ArgumentParser, "parse_args", _fake_parse):
            rc = sysinfo.main()
    assert rc == 0, f"Expected exit 0 when total_mb is 0, got {rc}"


def test_json_cpu_overall_is_mean_of_cores():
    """--json cpu.overall equals the mean of cpu.cores (single-call consistency)."""
    result = run_sysinfo("--json")
    data = json.loads(result.stdout)
    cores = data["cpu"]["cores"]
    if cores:
        expected_mean = sum(cores) / len(cores)
        # Allow a small floating-point tolerance
        assert abs(data["cpu"]["overall"] - expected_mean) < 1e-9, (
            f"cpu.overall ({data['cpu']['overall']}) does not match "
            f"mean of cpu.cores ({expected_mean})"
        )


# ---------------------------------------------------------------------------
# cpu sub-command --json tests  (newapp-odd.1 / US-001)
# ---------------------------------------------------------------------------


def test_cpu_json_exits_zero():
    """cpu --json exits with code 0."""
    result = run_sysinfo("cpu", "--json")
    assert result.returncode == 0, (
        f"Expected exit 0 with 'cpu --json', got {result.returncode}"
    )


def test_cpu_json_produces_valid_json():
    """cpu --json stdout is valid JSON."""
    result = run_sysinfo("cpu", "--json")
    assert result.returncode == 0
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"'cpu --json' output is not valid JSON: {exc}\n{result.stdout!r}")
    assert isinstance(data, dict), (
        f"Expected dict at top level, got {type(data)}"
    )


def test_cpu_json_has_version_key():
    """cpu --json output contains a 'version' key."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    assert "version" in data, (
        f"Expected 'version' key in cpu --json output, got: {list(data)}"
    )
    assert data["version"] == "1.0", (
        f"Expected version '1.0', got: {data['version']!r}"
    )


def test_cpu_json_has_cpu_key():
    """cpu --json output contains a 'cpu' key."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    assert "cpu" in data, (
        f"Expected 'cpu' key in cpu --json output, got: {list(data)}"
    )
    assert isinstance(data["cpu"], dict), (
        f"Expected 'cpu' value to be dict, got {type(data['cpu'])}"
    )


def test_cpu_json_cpu_has_overall_and_cores():
    """cpu --json cpu object has 'overall' (float) and 'cores' (list)."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    cpu = data["cpu"]
    assert "overall" in cpu, f"Expected 'overall' in cpu object: {cpu!r}"
    assert "cores" in cpu, f"Expected 'cores' in cpu object: {cpu!r}"
    assert isinstance(cpu["overall"], float), (
        f"Expected cpu.overall to be float, got {type(cpu['overall'])}"
    )
    assert isinstance(cpu["cores"], list), (
        f"Expected cpu.cores to be list, got {type(cpu['cores'])}"
    )
    assert len(cpu["cores"]) > 0, "Expected at least one entry in cpu.cores"


def test_cpu_json_cores_values_in_range():
    """cpu --json cpu.cores values are floats in 0.0–100.0."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    for i, pct in enumerate(data["cpu"]["cores"]):
        assert isinstance(pct, float), (
            f"Core {i} should be float, got {type(pct)}: {pct!r}"
        )
        assert 0.0 <= pct <= 100.0, (
            f"Core {i} percentage {pct} out of range [0.0, 100.0]"
        )


def test_cpu_json_overall_in_range():
    """cpu --json cpu.overall is a float in 0.0–100.0."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    overall = data["cpu"]["overall"]
    assert 0.0 <= overall <= 100.0, (
        f"cpu.overall {overall} out of expected range [0.0, 100.0]"
    )


def test_cpu_json_no_ansi_codes():
    """cpu --json output contains no ANSI escape sequences."""
    result = run_sysinfo("cpu", "--json")
    assert "\x1b[" not in result.stdout, (
        f"ANSI escape codes found in 'cpu --json' output: {result.stdout!r}"
    )


def test_cpu_json_only_contains_version_and_cpu_keys():
    """cpu --json output does not leak memory, disk, or other top-level keys."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    unexpected = set(data.keys()) - {"version", "cpu"}
    assert not unexpected, (
        f"Unexpected top-level keys in 'cpu --json' output: {unexpected}"
    )


def test_cpu_json_overall_is_mean_of_cores():
    """cpu --json cpu.overall equals the mean of cpu.cores (consistency check)."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    cores = data["cpu"]["cores"]
    if cores:
        expected_mean = sum(cores) / len(cores)
        assert abs(data["cpu"]["overall"] - expected_mean) < 1e-9, (
            f"cpu.overall ({data['cpu']['overall']}) does not equal "
            f"mean of cpu.cores ({expected_mean})"
        )


def test_cpu_json_core_count_matches_psutil():
    """cpu --json cpu.cores length matches psutil.cpu_count(logical=True)."""
    result = run_sysinfo("cpu", "--json")
    data = json.loads(result.stdout)
    expected = psutil.cpu_count(logical=True)
    assert len(data["cpu"]["cores"]) == expected, (
        f"Expected {expected} core entries, got {len(data['cpu']['cores'])}"
    )
