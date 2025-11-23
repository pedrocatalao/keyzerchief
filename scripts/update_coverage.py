#!/usr/bin/env python3
"""
Run tests, generate coverage report, and update the README badge locally.
"""

import subprocess
import json
import re
import sys
from pathlib import Path

def main():
    # Check if coverage is installed
    try:
        import coverage
    except ImportError:
        # Try to find venv
        script_dir = Path(__file__).parent.resolve()
        venv_python = script_dir.parent / ".venv" / "bin" / "python"
        if venv_python.exists():
            print(f"Coverage not found in {sys.executable}. Switching to virtual environment: {venv_python}")
            # Re-execute script with venv python
            try:
                subprocess.run([str(venv_python), *sys.argv], check=True)
                return
            except subprocess.CalledProcessError as e:
                sys.exit(e.returncode)
        else:
            print("Error: 'coverage' module not found and no .venv detected.")
            print("Please install it using 'pip install coverage' or run this script inside the virtual environment.")
            sys.exit(1)

    # 1. Run tests with coverage
    print("Running tests with coverage...")
    try:
        subprocess.run([sys.executable, "-m", "coverage", "run", "-m", "unittest", "discover", "tests"], check=True)
    except subprocess.CalledProcessError:
        print("Tests failed! Aborting coverage update.")
        sys.exit(1)
    
    # 2. Generate JSON report
    print("Generating coverage report...")
    subprocess.run([sys.executable, "-m", "coverage", "report"], check=True)
    subprocess.run([sys.executable, "-m", "coverage", "json"], check=True)
    
    # 3. Read coverage.json
    try:
        with open("coverage.json", "r") as f:
            data = json.load(f)
            total = data["totals"]["percent_covered_display"]
            total_float = float(total)
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"Error reading coverage data: {e}")
        sys.exit(1)
        
    # 4. Determine color
    if total_float > 80:
        color = "green"
    elif total_float > 50:
        color = "yellow"
    else:
        color = "red"
        
    print(f"Total coverage: {total}% ({color})")
    
    # 5. Update README.md
    readme_path = Path("README.md")
    if not readme_path.exists():
        # Try looking one level up if we are in scripts/
        readme_path = Path("../README.md")
        if not readme_path.exists():
            print("README.md not found!")
            sys.exit(1)
        
    content = readme_path.read_text()
    
    # Regex to match the badge
    # ![Coverage](https://img.shields.io/badge/coverage-52%25-yellow)
    
    badge_pattern = r"!\[Coverage\]\(https://img\.shields\.io/badge/coverage-\d+%25-[a-z]+\)"
    new_badge = f"![Coverage](https://img.shields.io/badge/coverage-{total}%25-{color})"
    
    if re.search(badge_pattern, content):
        new_content = re.sub(badge_pattern, new_badge, content)
        if new_content != content:
            readme_path.write_text(new_content)
            print(f"README.md updated with new coverage badge: {total}%")
        else:
            print("Coverage badge already up to date.")
    else:
        # If not found, try to find the old svg one
        old_svg_pattern = r"!\[Coverage\]\(coverage\.svg\)"
        if re.search(old_svg_pattern, content):
             new_content = re.sub(old_svg_pattern, new_badge, content)
             readme_path.write_text(new_content)
             print("README.md updated (replaced old SVG badge).")
        else:
            print("Could not find existing coverage badge in README.md to update.")
            
if __name__ == "__main__":
    main()
