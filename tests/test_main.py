"""
Test cases for the main module.

These tests demonstrate Vibecode testing principles:
- Clear, descriptive test names
- Comprehensive coverage
- Well-documented test cases
"""

from nexus.main import main


def test_main_function_exists():
    """Test that the main function exists and is callable."""
    assert callable(main)


def test_main_function_runs_without_error(capsys):
    """
    Test that the main function runs without raising an exception.

    Args:
        capsys: pytest fixture to capture stdout/stderr
    """
    main()
    captured = capsys.readouterr()
    assert "Welcome to Nexus" in captured.out


def test_main_function_output_format(capsys):
    """
    Test that the main function produces the expected output format.

    Args:
        capsys: pytest fixture to capture stdout/stderr
    """
    main()
    captured = capsys.readouterr()
    expected_message = "Welcome to Nexus - A Vibecode Python Project!"
    assert captured.out.strip() == expected_message


class TestMainModule:
    """Test class demonstrating organized test structure."""

    def test_main_function_type_hints(self):
        """Test that the main function has proper type hints."""
        import inspect

        sig = inspect.signature(main)
        assert sig.return_annotation is None or sig.return_annotation is type(None)

    def test_main_function_docstring(self):
        """Test that the main function has a proper docstring."""
        assert main.__doc__ is not None
        assert len(main.__doc__.strip()) > 0
