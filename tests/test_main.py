"""
Test cases for the main module.

These tests demonstrate Vibecode testing principles:
- Clear, descriptive test names
- Comprehensive coverage
- Well-documented test cases
"""

from nexus.main import create_engine, run_pipeline, run_plugin


def test_create_engine_function_exists():
    """Test that the create_engine function exists and is callable."""
    assert callable(create_engine)


def test_run_pipeline_function_exists():
    """Test that the run_pipeline function exists and is callable."""
    assert callable(run_pipeline)


def test_run_plugin_function_exists():
    """Test that the run_plugin function exists and is callable."""
    assert callable(run_plugin)


class TestMainModule:
    """Test class demonstrating organized test structure."""

    def test_create_engine_returns_engine(self):
        """Test that create_engine returns a PipelineEngine instance."""
        engine = create_engine("test-case")
        from nexus.core.engine import PipelineEngine

        assert isinstance(engine, PipelineEngine)

    def test_functions_have_docstrings(self):
        """Test that all main functions have proper docstrings."""
        assert create_engine.__doc__ is not None
        assert len(create_engine.__doc__.strip()) > 0
        assert run_pipeline.__doc__ is not None
        assert len(run_pipeline.__doc__.strip()) > 0
        assert run_plugin.__doc__ is not None
        assert len(run_plugin.__doc__.strip()) > 0
