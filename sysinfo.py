#!/usr/bin/env python3
"""sysinfo.py — System information utility."""

import argparse
import sys


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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
