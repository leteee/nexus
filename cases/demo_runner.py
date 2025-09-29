"""
Demo script to test the Nexus framework functionality.

This script demonstrates the complete workflow including:
- Plugin registration
- Data processing pipeline
- CLI interface
"""

import sys
from pathlib import Path

# Add the src directory to the path for demo purposes
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "cases"))

# Import demo plugins to register them
from demo.plugins import *
from nexus.engine import PipelineEngine


def main():
    """Run the demo pipeline."""
    demo_path = Path(__file__).parent / "demo"

    print("Starting Nexus Demo Pipeline")
    print(f"Case directory: {demo_path}")

    try:
        # Create and run the pipeline engine
        engine = PipelineEngine(demo_path)
        engine.run_pipeline()

        print("\nPipeline completed successfully!")
        print("\nGenerated files:")

        # List generated files
        for file_path in demo_path.glob("*.csv"):
            print(f"  {file_path.name}")
        for file_path in demo_path.glob("*.json"):
            print(f"  {file_path.name}")

    except Exception as e:
        print(f"\nPipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())