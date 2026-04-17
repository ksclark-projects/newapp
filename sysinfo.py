#!/usr/bin/env python3
"""sysinfo.py — System information utility."""

import argparse
import platform
import sys

import colorama

colorama.init(autoreset=True)


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
