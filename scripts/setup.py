#!/usr/bin/env python3
"""
Setup script for Nexus development environment.

This script following Vibecode principles to automate development setup.
"""

import subprocess
import sys


def run_command(command: str, description: str) -> bool:
    """
    Run a shell command and report success/failure.

    Args:
        command: The command to run
        description: Human-readable description of the command

    Returns:
        bool: True if command succeeded, False otherwise
    """
    print(f"🔄 {description}...")
    try:
        subprocess.run(
            command.split(), check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"  Command: {command}")
        print(f"  Error: {e.stderr}")
        return False


def main() -> None:
    """Main setup function following Vibecode practices."""
    print("🚀 Setting up Nexus development environment...")

    steps = [
        ("pip install -e .[dev]", "Installing development dependencies"),
        ("pre-commit install", "Setting up pre-commit hooks"),
        ("black --check src/ tests/", "Checking code formatting"),
        ("isort --check-only src/ tests/", "Checking import sorting"),
        ("flake8 src/ tests/", "Running linting checks"),
        ("mypy src/", "Running type checking"),
        ("pytest", "Running test suite"),
    ]

    success_count = 0
    for command, description in steps:
        if run_command(command, description):
            success_count += 1

    print(
        f"\n📊 Setup Results: {success_count}/{len(steps)} steps completed successfully"
    )

    if success_count == len(steps):
        print("🎉 Development environment setup complete!")
        print("\n📖 Next steps:")
        print("  - Start coding with: python -m nexus.main")
        print("  - Run tests with: pytest")
        print("  - Format code with: black src/ tests/")
    else:
        print("⚠️  Some setup steps failed. Please review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
