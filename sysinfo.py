#!/usr/bin/env python3
"""sysinfo.py — System information utility."""

import argparse
import platform
import sys

import colorama
import psutil

colorama.init(autoreset=True)

# Threshold constants for CPU, memory, and disk usage (percentages)
CPU_WARN = 60
CPU_CRIT = 85
MEM_WARN = 70
MEM_CRIT = 90
DISK_WARN = 70
DISK_CRIT = 90


def format_header(text: str) -> str:
    """Return *text* wrapped in bold+cyan ANSI codes for section headers."""
    return (
        colorama.Style.BRIGHT
        + colorama.Fore.CYAN
        + text
        + colorama.Style.RESET_ALL
    )


def format_label(label: str) -> str:
    """Return *label* wrapped in yellow ANSI codes for key labels."""
    return (
        colorama.Fore.YELLOW
        + label
        + colorama.Style.RESET_ALL
    )


def colorize_pct(value: float, warn: float, crit: float) -> str:
    """Return *value* as a colored percentage string based on thresholds.

    Colors:
      - green  — value < warn
      - yellow — warn <= value <= crit
      - red    — value > crit
    """
    pct_str = f"{value:.1f}%"
    if value >= crit:
        color = colorama.Fore.RED
    elif value >= warn:
        color = colorama.Fore.YELLOW
    else:
        color = colorama.Fore.GREEN
    return color + pct_str + colorama.Style.RESET_ALL


def get_cpu_pct() -> float:
    """Return current CPU usage as a percentage (0.0–100.0)."""
    return psutil.cpu_percent(interval=0.1)


def get_mem_pct() -> float:
    """Return current memory usage as a percentage (0.0–100.0)."""
    return psutil.virtual_memory().percent


def get_disk_pct(path: str = "/") -> float:
    """Return disk usage for *path* as a percentage (0.0–100.0)."""
    return psutil.disk_usage(path).percent


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
    args = parser.parse_args()

    if args.python_version:
        print(get_python_version())
        return 0

    print(f"{format_label('OS Version:')} {get_os_version()}")
    print(f"{format_label('Python:')} {get_python_version()}")
    print(
        f"{format_label('CPU Usage:')} "
        f"{colorize_pct(get_cpu_pct(), CPU_WARN, CPU_CRIT)}"
    )
    print(
        f"{format_label('Memory Usage:')} "
        f"{colorize_pct(get_mem_pct(), MEM_WARN, MEM_CRIT)}"
    )
    print(
        f"{format_label('Disk Usage:')} "
        f"{colorize_pct(get_disk_pct(), DISK_WARN, DISK_CRIT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
