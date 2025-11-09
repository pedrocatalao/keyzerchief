#!/usr/bin/env python3

"""Gzip and encode to base64 an ASCII file."""

import sys
import gzip
import base64
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        print("Usage: python ascii_to_gzip_b64.py <input_file>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: File not found -> {input_path}")
        sys.exit(1)

    with input_path.open("r", encoding="utf-8") as f:
        content = f.read()

    compressed = gzip.compress(content.encode("utf-8"))
    encoded = base64.b64encode(compressed).decode("utf-8")

    print(encoded)

if __name__ == "__main__":
    main()
