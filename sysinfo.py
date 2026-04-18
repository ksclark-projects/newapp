#!/usr/bin/env python3
"""sysinfo.py — System information utility."""

import argparse
import json
import os
import platform
import sys

import colorama
import psutil

colorama.init(autoreset=True)


def color_enabled() -> bool:
    """Return True if ANSI colour output is allowed.

    Respects the NO_COLOR convention (https://no-color.org/): when the
    NO_COLOR environment variable is set to any value, colour is disabled.
    """
    return os.environ.get("NO_COLOR") is None


# Threshold constants for CPU, memory, and disk usage (percentages)
CPU_WARN = 60
CPU_CRIT = 85
MEM_WARN = 70
MEM_CRIT = 90
DISK_WARN = 70
DISK_CRIT = 90


def _apply_filter(procs: list, pattern: str | None) -> list:
    """Return *procs* filtered to entries whose name contains *pattern*.

    The match is case-insensitive. Uses ``p.get('name', '')`` so that process
    dicts with a missing or ``None`` name key are safely skipped rather than
    raising a ``KeyError``.

    Args:
        procs: List of process dicts as returned by ``get_top_processes``.
        pattern: Substring to match against process names, or ``None`` to
            return *procs* unchanged.

    Returns:
        Filtered (or original) list of process dicts.
    """
    if pattern is None:
        return procs
    pat = pattern.lower()
    return [p for p in procs if pat in p.get('name', '').lower()]


def format_header(text: str) -> str:
    """Return *text* wrapped in bold+cyan ANSI codes for section headers.

    Returns plain *text* when colour is disabled (NO_COLOR set).
    """
    if not color_enabled():
        return text
    return (
        colorama.Style.BRIGHT
        + colorama.Fore.CYAN
        + text
        + colorama.Style.RESET_ALL
    )


def format_label(label: str) -> str:
    """Return *label* wrapped in yellow ANSI codes for key labels.

    Returns plain *label* when colour is disabled (NO_COLOR set).
    """
    if not color_enabled():
        return label
    return (
        colorama.Fore.YELLOW
        + label
        + colorama.Style.RESET_ALL
    )


def colorize_pct(value: float, warn: float, crit: float) -> str:
    """Return *value* as a colored percentage string based on thresholds.

    Colors:
      - green  -- value < warn
      - yellow -- warn <= value < crit
      - red    -- value >= crit
    """
    pct_str = f"{value:.1f}%"
    if not color_enabled():
        return pct_str
    if value >= crit:
        color = colorama.Fore.RED
    elif value >= warn:
        color = colorama.Fore.YELLOW
    else:
        color = colorama.Fore.GREEN
    return color + pct_str + colorama.Style.RESET_ALL


def _fmt_size(mb: float) -> str:
    """Return *mb* as a human-readable string (GB when >= 1024, else MB)."""
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def get_cpu_pct() -> float:
    """Return current CPU usage as a percentage (0.0-100.0)."""
    return psutil.cpu_percent(interval=0.1)


def get_cpu_cores() -> list:
    """Return per-core CPU usage as a list of floats (0.0-100.0 each)."""
    return psutil.cpu_percent(interval=0.1, percpu=True)


def get_mem_pct() -> float:
    """Return current memory usage as a percentage (0.0-100.0)."""
    return psutil.virtual_memory().percent


def get_mem_details() -> dict:
    """Return memory usage details as a dict with MB values.

    Keys: used_mb, free_mb, cached_mb, total_mb (all rounded to 1 d.p.)

    - free_mb  : bytes available to user processes (psutil 'available')
    - cached_mb: OS page-cache bytes; 0 on platforms that don't expose it
    - used_mb  : bytes actively used (psutil 'used')
    - total_mb : physical RAM installed
    """
    vm = psutil.virtual_memory()
    _mb = 1024 * 1024
    return {
        "used_mb": round(vm.used / _mb, 1),
        "free_mb": round(vm.available / _mb, 1),
        "cached_mb": round(getattr(vm, "cached", 0) / _mb, 1),
        "total_mb": round(vm.total / _mb, 1),
    }


def get_disk_pct(path: str = "/") -> float:
    """Return disk usage for *path* as a percentage (0.0-100.0)."""
    return psutil.disk_usage(path).percent


def get_disk_mounts() -> list:
    """Return disk usage info for every mounted filesystem.

    Iterates psutil.disk_partitions() and collects psutil.disk_usage() for
    each mount point that is accessible.  Mount points that raise
    PermissionError or OSError are silently skipped.

    Each entry in the returned list is a dict with keys:
      mount     (str)   -- mount point path, e.g. '/'
      used_gb   (float) -- used space in GiB
      free_gb   (float) -- free space in GiB
      total_gb  (float) -- total capacity in GiB
      percent   (float) -- used percentage (0.0-100.0)
    """
    _GiB = 1024 ** 3
    mounts = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        mounts.append({
            "mount": part.mountpoint,
            "used_gb": round(usage.used / _GiB, 2),
            "free_gb": round(usage.free / _GiB, 2),
            "total_gb": round(usage.total / _GiB, 2),
            "percent": usage.percent,
        })
    return mounts


def get_top_processes(n: int = 10) -> list:
    """Return the top *n* processes sorted by CPU usage (descending).

    Each entry is a dict with keys:
      pid      (int)   -- process ID
      name     (str)   -- process name
      cpu_pct  (float) -- CPU usage percentage
      mem_pct  (float) -- memory usage percentage

    Processes that are inaccessible (NoSuchProcess, AccessDenied) are
    silently skipped.
    """
    procs = []
    attrs = ['pid', 'name', 'cpu_percent', 'memory_percent']
    for proc in psutil.process_iter(attrs):
        try:
            info = proc.info
            procs.append({
                'pid': info['pid'],
                'name': info['name'] or '',
                'cpu_pct': info['cpu_percent'] or 0.0,
                'mem_pct': info['memory_percent'] or 0.0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p['cpu_pct'], reverse=True)
    return procs[:n]


def get_os_version() -> str:
    """Return a formatted OS version string.

    Returns a string like 'macOS 14.4 (Darwin 23.4.0)'.
    Falls back to 'Unknown' if retrieval fails or returns empty data.
    """
    try:
        system = platform.system()
        release = platform.release()
        mac_ver_info = platform.mac_ver()
        mac_version = mac_ver_info[0]

        if system == "Darwin" and mac_version:
            return f"macOS {mac_version} (Darwin {release})"
        elif system and release:
            return f"{system} {release}"
        else:
            return "Unknown"
    except Exception:
        return "Unknown"


def get_python_version() -> str:
    """Return the current Python version string."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def _cpu_plain_output() -> None:
    """Print CPU-only information in human-readable form to stdout."""
    cpu_pct = get_cpu_pct()
    cores = get_cpu_cores()
    print(
        f"{format_label('CPU Usage:')} "
        f"{colorize_pct(cpu_pct, CPU_WARN, CPU_CRIT)}"
    )
    for i, core_pct in enumerate(cores):
        print(
            f"  {format_label(f'Core {i}:')} "
            f"{colorize_pct(core_pct, CPU_WARN, CPU_CRIT)}"
        )


def _cpu_json_output() -> None:
    """Print CPU info as a versioned JSON object to stdout (no ANSI codes)."""
    # Single psutil call so overall and per-core figures are consistent.
    cores = psutil.cpu_percent(interval=0.1, percpu=True)
    # overall is the arithmetic mean of per-core percentages, not psutil's
    # time-weighted cpu_percent() — computed this way to avoid a second
    # 100 ms blocking interval call and keep overall/cores consistent.
    overall = sum(cores) / len(cores) if cores else 0.0
    print(json.dumps(
        {
            "version": "1.0",
            "cpu": {
                "overall": overall,
                "cores": cores,
            },
        },
        indent=2,
    ))


def _memory_plain_output() -> None:
    """Print memory-only information in human-readable form to stdout."""
    mem = get_mem_details()
    mem_pct = psutil.virtual_memory().percent
    mem_detail = (
        f"{_fmt_size(mem['used_mb'])} used / "
        f"{_fmt_size(mem['free_mb'])} available / "
        f"{_fmt_size(mem['total_mb'])} total"
    )
    print(
        f"{format_label('Memory Usage:')} "
        f"{colorize_pct(mem_pct, MEM_WARN, MEM_CRIT)}"
        f"  ({mem_detail})"
    )


def _memory_json_output() -> None:
    """Print memory info as a versioned JSON object to stdout (no ANSI codes)."""
    vm = psutil.virtual_memory()
    _gb = 1024.0 * 1024 * 1024
    print(json.dumps(
        {
            "version": "1.0",
            "memory": {
                # total_gb / used_gb / available_gb are in GiB (1024^3 bytes)
                "total_gb": round(vm.total / _gb, 3),
                "used_gb": round(vm.used / _gb, 3),
                # available_gb is vm.available (memory usable by processes),
                # not vm.free (unallocated pages).
                "available_gb": round(vm.available / _gb, 3),
                # percent is psutil's time-weighted utilisation value
                "percent": vm.percent,
            },
        },
        indent=2,
    ))


def _disk_json_output(path: str = "/") -> None:
    """Print disk info as a versioned JSON object to stdout (no ANSI codes).

    Note: This returns a single flat dict for the given *path* (default ``/``).
    The top-level ``sysinfo --json`` snapshot uses ``get_disk_mounts()`` and
    returns a list of all mount points under the ``"disk"`` key.  The
    difference is intentional: the sub-command is scoped to one path probe,
    while the dashboard shows all mounts.
    """
    _GiB = 1024 ** 3
    usage = psutil.disk_usage(path)
    print(json.dumps(
        {
            "version": "1.0",
            "disk": {
                "total_gb": round(usage.total / _GiB, 2),
                "used_gb": round(usage.used / _GiB, 2),
                "free_gb": round(usage.free / _GiB, 2),
                "percent": usage.percent,
            },
        },
        indent=2,
    ))


def main() -> int:
    """Entry point for sysinfo CLI."""
    parser = argparse.ArgumentParser(
        description="Display system information."
    )
    parser.add_argument(
        "--python-version",
        action="store_true",
        help="Print the current Python version and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Output a full system snapshot as JSON "
            "(python_version, cpu, memory, disk, top_processes) and exit."
        ),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Show top N processes by CPU%% (default: 10; 0 to disable).",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        metavar="PATTERN",
        help=(
            "Filter the process list to names containing PATTERN "
            "(case-insensitive substring match). "
            "Must be a non-empty string."
        ),
    )
    parser.add_argument(
        "--sort",
        type=str,
        default=None,
        choices=["mem"],
        metavar="KEY",
        help=(
            "Sort the process list by KEY. "
            "Valid values: mem (memory usage %%). "
            "Default: CPU%% descending. "
            "Unrecognized values are rejected with a helpful error."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    # cpu sub-command
    cpu_parser = subparsers.add_parser(
        "cpu",
        help="Show CPU information.",
    )
    cpu_parser.add_argument(
        "--json",
        action="store_true",
        dest="cpu_json",
        help="Output CPU info as JSON ({version, cpu: {overall, cores}}).",
    )

    # memory sub-command
    mem_parser = subparsers.add_parser(
        "memory",
        help="Show memory information.",
    )
    mem_parser.add_argument(
        "--json",
        action="store_true",
        dest="mem_json",
        help=(
            "Output memory info as JSON "
            "({version, memory: {total_gb, used_gb, available_gb, percent}})."
        ),
    )

    # disk sub-command
    disk_parser = subparsers.add_parser(
        "disk",
        help="Show disk information.",
    )
    disk_parser.add_argument(
        "--json",
        action="store_true",
        dest="disk_json",
        help=(
            "Output disk info as JSON "
            "({version, disk: {total_gb, used_gb, free_gb, percent}})."
        ),
    )

    args = parser.parse_args()

    # Validate --filter: reject empty (or whitespace-only) strings.
    _filter = args.filter
    if _filter is not None and _filter.strip() == "":
        _msg = "--filter value must not be empty; provide a non-empty pattern"
        if getattr(args, 'json', False):
            print(json.dumps({"error": _msg}), file=sys.stderr)
            return 1
        parser.error(_msg)

    # --filter only applies to the default (no-subcommand) process list view.
    # Warn the user if they combine it with a subcommand so it isn't silently
    # discarded.
    if _filter is not None and args.command is not None:
        print(
            f"Warning: --filter has no effect with the '{args.command}' "
            "subcommand and will be ignored. "
            "Use --filter without a subcommand to filter the process list.",
            file=sys.stderr,
        )

    # --sort only applies to the default (no-subcommand) process list view.
    # Warn the user if they combine it with a subcommand so it isn't silently
    # discarded.
    if getattr(args, 'sort', None) is not None and args.command is not None:
        print(
            f"Warning: --sort has no effect with the '{args.command}' "
            "subcommand and will be ignored.",
            file=sys.stderr,
        )

    # --- cpu sub-command ---
    if args.command == "cpu":
        if args.cpu_json:
            try:
                _cpu_json_output()
            except Exception as exc:
                print(json.dumps({"error": str(exc)}), file=sys.stderr)
                return 1
            return 0

    # --- memory sub-command ---
    if args.command == "memory":
        if args.mem_json:
            try:
                _memory_json_output()
            except Exception as exc:
                print(json.dumps({"error": str(exc)}), file=sys.stderr)
                return 1
            return 0
        # No flags: show memory-only plain-text output.
        _memory_plain_output()
        return 0

    # --- disk sub-command ---
    if args.command == "disk":
        if args.disk_json:
            try:
                _disk_json_output()
            except Exception as exc:
                print(json.dumps({"error": str(exc)}), file=sys.stderr)
                return 1
            return 0

    if args.command is None:
        # Validate --top for the top-level (non-sub-command) path.
        # When --json is also active, emit a JSON error instead of the default
        # plain-text argparse message so callers receive a consistent format.
        if args.top < 0:
            if args.json:
                print(
                    json.dumps({"error": "--top must be >= 0"}),
                    file=sys.stderr,
                )
                return 1
            parser.error("--top must be >= 0")

    if args.python_version:
        print(get_python_version())
        return 0

    if args.json:
        try:
            # Collect per-core percentages in a single psutil call, then derive
            # the overall figure as the mean — avoids two separate 100 ms sleeps
            # that would otherwise produce an inconsistent overall/cores pair.
            cores = psutil.cpu_percent(interval=0.1, percpu=True)
            overall = sum(cores) / len(cores) if cores else 0.0
            top_procs = _apply_filter(get_top_processes(args.top), _filter)
            if args.sort == "mem":
                top_procs = sorted(
                    top_procs, key=lambda p: p.get("mem_pct", 0.0), reverse=True
                )
            print(json.dumps(
                {
                    "version": "1.0",
                    "python_version": get_python_version(),
                    "cpu": {
                        "overall": overall,
                        "cores": cores,
                    },
                    "memory": get_mem_details(),
                    "disk": get_disk_mounts(),
                    "top_processes": top_procs,
                },
                indent=2,
            ))
        except Exception as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
        return 0

    mem = get_mem_details()
    mem_pct = (
        mem["used_mb"] / mem["total_mb"] * 100 if mem["total_mb"] else 0.0
    )
    mem_detail = (
        f"{_fmt_size(mem['used_mb'])} used / "
        f"{_fmt_size(mem['free_mb'])} free / "
        f"{_fmt_size(mem['total_mb'])} total"
    )

    print(f"{format_label('OS Version:')} {get_os_version()}")
    print(f"{format_label('Python:')} {get_python_version()}")
    print(
        f"{format_label('CPU Usage:')} "
        f"{colorize_pct(get_cpu_pct(), CPU_WARN, CPU_CRIT)}"
    )
    for i, core_pct in enumerate(get_cpu_cores()):
        print(
            f"  {format_label(f'Core {i}:')} "
            f"{colorize_pct(core_pct, CPU_WARN, CPU_CRIT)}"
        )
    print(
        f"{format_label('Memory Usage:')} "
        f"{colorize_pct(mem_pct, MEM_WARN, MEM_CRIT)}"
        f"  ({mem_detail})"
    )

    print(format_header("Disk Usage:"))
    for mount in get_disk_mounts():
        pct_str = colorize_pct(mount["percent"], DISK_WARN, DISK_CRIT)
        print(
            f"  {format_label(mount['mount'] + ':')} "
            f"{pct_str} "
            f"({mount['used_gb']:.1f} / {mount['total_gb']:.1f} GiB, "
            f"{mount['free_gb']:.1f} GiB free)"
        )

    if args.top > 0:
        print()
        top_procs = _apply_filter(get_top_processes(args.top), _filter)
        if args.sort == "mem":
            top_procs = sorted(
                top_procs, key=lambda p: p.get("mem_pct", 0.0), reverse=True
            )
        sort_label = "MEM%" if args.sort == "mem" else "CPU%"
        print(format_header(f"Top {args.top} Processes (by {sort_label}):"))
        if not top_procs:
            print("  No matching processes")
        else:
            print(f"  {'PID':>7}  {'Name':<20}  {'CPU%':>7}  {'MEM%':>7}")
            for proc in top_procs:
                cpu_str = colorize_pct(proc['cpu_pct'], CPU_WARN, CPU_CRIT)
                mem_str = colorize_pct(proc['mem_pct'], MEM_WARN, MEM_CRIT)
                name = proc['name'][:20]
                print(f"  {proc['pid']:>7}  {name:<20}  {cpu_str}  {mem_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
