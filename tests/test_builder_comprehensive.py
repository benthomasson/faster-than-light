"""
Comprehensive unit tests for faster_than_light.builder module.

Tests all builder CLI functionality including Click option parsing,
requirements file processing, gate building integration, and error handling.
"""

import sys
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from click.testing import CliRunner

from faster_than_light.builder import entry_point, main


class TestBuilderMain:
    """Tests for main function using Click testing framework."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_minimal_parameters(self, mock_build_ftl_gate):
        """Test main with minimal parameters."""
        mock_build_ftl_gate.return_value = ("/path/to/gate.pyz", "hash123")

        result = self.runner.invoke(main, [])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            [],
            [],
            None,
            "/usr/bin/python3",  # modules, module_dirs, dependencies, interpreter
        )
        assert "/path/to/gate.pyz" in result.output

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_single_options(self, mock_build_ftl_gate):
        """Test main with single values for each option."""
        mock_build_ftl_gate.return_value = ("/custom/gate.pyz", "custom_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "test_module",
                "--module-dir",
                "/modules",
                "--interpreter",
                "/usr/bin/python3.9",
            ],
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["test_module"], ["/modules"], None, "/usr/bin/python3.9"
        )
        assert "/custom/gate.pyz" in result.output

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_multiple_modules(self, mock_build_ftl_gate):
        """Test main with multiple modules and directories."""
        mock_build_ftl_gate.return_value = ("/multi/gate.pyz", "multi_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "mod1",
                "--module",
                "mod2",
                "--ftl-module",
                "ftl_mod1",
                "--ftl-module",
                "ftl_mod2",
                "--module-dir",
                "/dir1",
                "--module-dir",
                "/dir2",
            ],
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["mod1", "mod2"], ["/dir1", "/dir2"], None, "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_short_options(self, mock_build_ftl_gate):
        """Test main with short option flags."""
        mock_build_ftl_gate.return_value = ("/short/gate.pyz", "short_hash")

        result = self.runner.invoke(
            main,
            [
                "-m",
                "module1",
                "-f",
                "ftl_module1",
                "-M",
                "/short/modules",
                "-I",
                "/usr/bin/python3.8",
            ],
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["module1"], ["/short/modules"], None, "/usr/bin/python3.8"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_verbose_flag(self, mock_build_ftl_gate):
        """Test main with verbose flag."""
        mock_build_ftl_gate.return_value = ("/verbose/gate.pyz", "verbose_hash")

        result = self.runner.invoke(main, ["--verbose"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_debug_flag(self, mock_build_ftl_gate):
        """Test main with debug flag."""
        mock_build_ftl_gate.return_value = ("/debug/gate.pyz", "debug_hash")

        result = self.runner.invoke(main, ["--debug"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_both_flags(self, mock_build_ftl_gate):
        """Test main with both verbose and debug flags."""
        mock_build_ftl_gate.return_value = ("/flags/gate.pyz", "flags_hash")

        result = self.runner.invoke(main, ["--verbose", "--debug"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once()


class TestBuilderRequirements:
    """Tests for requirements file processing in builder."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_with_single_requirements_file(self, mock_file, mock_build_ftl_gate):
        """Test main with single requirements file."""
        mock_file.return_value.read.return_value = (
            "requests>=2.25.0\npytest>=6.0\n\nnumpy"
        )
        mock_build_ftl_gate.return_value = ("/req/gate.pyz", "req_hash")

        result = self.runner.invoke(main, ["--requirements", "requirements.txt"])

        assert result.exit_code == 0
        mock_file.assert_called_once_with("requirements.txt")
        mock_build_ftl_gate.assert_called_once_with(
            [], [], ["requests>=2.25.0", "pytest>=6.0", "numpy"], "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_with_multiple_requirements_files(
        self, mock_file, mock_build_ftl_gate
    ):
        """Test main with multiple requirements files."""
        # Mock multiple file reads
        mock_file.side_effect = [
            mock_open(read_data="requests\nflask").return_value,
            mock_open(read_data="pytest\nnumpy").return_value,
        ]
        mock_build_ftl_gate.return_value = ("/multi_req/gate.pyz", "multi_req_hash")

        result = self.runner.invoke(
            main, ["--requirements", "req1.txt", "--requirements", "req2.txt"]
        )

        assert result.exit_code == 0
        # Should have been called twice, but only the last one sets dependencies
        expected_calls = [call("req1.txt"), call("req2.txt")]
        mock_file.assert_has_calls(expected_calls)

        # The current implementation overwrites dependencies for each file
        mock_build_ftl_gate.assert_called_once_with(
            [], [], ["pytest", "numpy"], "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_with_empty_requirements_file(self, mock_file, mock_build_ftl_gate):
        """Test main with empty requirements file."""
        mock_file.return_value.read.return_value = "\n\n\n"
        mock_build_ftl_gate.return_value = ("/empty_req/gate.pyz", "empty_req_hash")

        result = self.runner.invoke(main, ["--requirements", "empty.txt"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with([], [], [], "/usr/bin/python3")

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_with_comments_in_requirements(self, mock_file, mock_build_ftl_gate):
        """Test main with comments and complex requirements."""
        requirements_content = """# Main dependencies
requests>=2.25.0
flask==1.1.0
# Development dependencies  
pytest>=6.0
# Optional dependency
numpy; sys_platform != "win32"

# Empty line above should be ignored"""

        mock_file.return_value.read.return_value = requirements_content
        mock_build_ftl_gate.return_value = ("/complex_req/gate.pyz", "complex_req_hash")

        result = self.runner.invoke(main, ["--requirements", "complex.txt"])

        assert result.exit_code == 0
        # All non-empty lines should be included (including comments in current implementation)
        # Note: preserving exact whitespace from the requirements content
        expected_deps = [
            "# Main dependencies",
            "requests>=2.25.0",
            "flask==1.1.0",
            "# Development dependencies  ",  # Note the trailing spaces
            "pytest>=6.0",
            "# Optional dependency",
            'numpy; sys_platform != "win32"',
            "# Empty line above should be ignored",
        ]
        mock_build_ftl_gate.assert_called_once_with(
            [], [], expected_deps, "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open")
    def test_main_requirements_file_not_found(self, mock_file, mock_build_ftl_gate):
        """Test error handling when requirements file is not found."""
        mock_file.side_effect = FileNotFoundError("File not found")

        result = self.runner.invoke(main, ["--requirements", "nonexistent.txt"])

        # Click should handle the exception and exit with non-zero code
        assert result.exit_code != 0
        assert "FileNotFoundError" in str(result.exception) or isinstance(
            result.exception, FileNotFoundError
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open")
    def test_main_requirements_file_permission_error(
        self, mock_file, mock_build_ftl_gate
    ):
        """Test error handling when requirements file has permission issues."""
        mock_file.side_effect = PermissionError("Permission denied")

        result = self.runner.invoke(main, ["--requirements", "protected.txt"])

        assert result.exit_code != 0
        assert "PermissionError" in str(result.exception) or isinstance(
            result.exception, PermissionError
        )


class TestBuilderInterpreterHandling:
    """Tests for interpreter parameter handling in builder."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_default_interpreter(self, mock_build_ftl_gate):
        """Test that default interpreter is used when not specified."""
        mock_build_ftl_gate.return_value = ("/default/gate.pyz", "default_hash")

        result = self.runner.invoke(main, ["--module", "test"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["test"], [], None, "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_custom_interpreter(self, mock_build_ftl_gate):
        """Test with custom interpreter path."""
        mock_build_ftl_gate.return_value = (
            "/custom_interp/gate.pyz",
            "custom_interp_hash",
        )

        result = self.runner.invoke(
            main, ["--interpreter", "/opt/python/bin/python3.9"]
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            [], [], None, "/opt/python/bin/python3.9"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_interpreter_short_option(self, mock_build_ftl_gate):
        """Test interpreter with short option flag."""
        mock_build_ftl_gate.return_value = (
            "/short_interp/gate.pyz",
            "short_interp_hash",
        )

        result = self.runner.invoke(main, ["-I", "/usr/local/bin/python3"])

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            [], [], None, "/usr/local/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_empty_interpreter_uses_default(self, mock_build_ftl_gate):
        """Test that empty interpreter string still uses default."""
        mock_build_ftl_gate.return_value = (
            "/empty_interp/gate.pyz",
            "empty_interp_hash",
        )

        result = self.runner.invoke(main, ["--interpreter", ""])

        assert result.exit_code == 0
        # Empty string is falsy, so default should be used
        mock_build_ftl_gate.assert_called_once_with([], [], None, "/usr/bin/python3")


class TestBuilderIntegration:
    """Integration tests for builder functionality."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_complete_workflow(self, mock_file, mock_build_ftl_gate):
        """Test complete workflow with all options."""
        mock_file.return_value.read.return_value = "requests>=2.25.0\nflask>=1.0.0"
        mock_build_ftl_gate.return_value = ("/complete/gate.pyz", "complete_hash")

        result = self.runner.invoke(
            main,
            [
                "--verbose",
                "--debug",
                "--module",
                "service",
                "--module",
                "utils",
                "--ftl-module",
                "custom_ftl",
                "--module-dir",
                "/opt/modules",
                "--module-dir",
                "/custom/modules",
                "--requirements",
                "requirements.txt",
                "--interpreter",
                "/usr/bin/python3.10",
            ],
        )

        assert result.exit_code == 0
        mock_file.assert_called_once_with("requirements.txt")
        mock_build_ftl_gate.assert_called_once_with(
            ["service", "utils"],
            ["/opt/modules", "/custom/modules"],
            ["requests>=2.25.0", "flask>=1.0.0"],
            "/usr/bin/python3.10",
        )
        assert "/complete/gate.pyz" in result.output

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_realistic_ansible_scenario(self, mock_build_ftl_gate):
        """Test realistic scenario mimicking Ansible module usage."""
        mock_build_ftl_gate.return_value = ("/ansible/gate.pyz", "ansible_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "copy",
                "--module",
                "template",
                "--module",
                "service",
                "--module-dir",
                "/usr/share/ansible/plugins/modules",
                "--module-dir",
                "/opt/custom/modules",
                "--interpreter",
                "/usr/bin/python3.8",
            ],
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["copy", "template", "service"],
            ["/usr/share/ansible/plugins/modules", "/opt/custom/modules"],
            None,
            "/usr/bin/python3.8",
        )


class TestBuilderErrorHandling:
    """Tests for error handling in builder."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_build_ftl_gate_failure(self, mock_build_ftl_gate):
        """Test error handling when build_ftl_gate fails."""
        mock_build_ftl_gate.side_effect = Exception("Gate building failed")

        result = self.runner.invoke(main, ["--module", "failing_module"])

        assert result.exit_code != 0
        assert "Gate building failed" in str(result.exception)

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_import_error_handling(self, mock_build_ftl_gate):
        """Test handling of import-related errors."""
        mock_build_ftl_gate.side_effect = ImportError("Module not found")

        result = self.runner.invoke(main, ["--module", "missing_module"])

        assert result.exit_code != 0
        assert "ImportError" in str(result.exception) or isinstance(
            result.exception, ImportError
        )

    def test_main_invalid_option(self):
        """Test behavior with invalid command line options."""
        result = self.runner.invoke(main, ["--invalid-option"])

        assert result.exit_code != 0
        assert "No such option" in result.output or "invalid-option" in result.output

    def test_main_help_option(self):
        """Test help option displays usage information."""
        result = self.runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output or "Options:" in result.output


class TestBuilderEntryPoint:
    """Tests for entry_point function."""

    @patch("faster_than_light.builder.main")
    @patch("faster_than_light.builder.sys.argv", ["ftl-gate-builder", "--verbose"])
    def test_entry_point_calls_main_with_sys_argv(self, mock_main):
        """Test that entry_point calls main with sys.argv."""
        mock_main.return_value = None  # Click commands don't return values by default

        entry_point()

        mock_main.assert_called_once_with(["--verbose"])

    @patch("faster_than_light.builder.main")
    @patch("faster_than_light.builder.sys.argv", ["ftl-gate-builder"])
    def test_entry_point_with_no_args(self, mock_main):
        """Test entry_point with no arguments."""
        mock_main.return_value = None

        entry_point()

        mock_main.assert_called_once_with([])

    @patch("faster_than_light.builder.main")
    @patch(
        "faster_than_light.builder.sys.argv",
        ["ftl-gate-builder", "--module", "test", "--interpreter", "/usr/bin/python3"],
    )
    def test_entry_point_with_complex_args(self, mock_main):
        """Test entry_point with complex argument list."""
        mock_main.return_value = None

        entry_point()

        expected_args = ["--module", "test", "--interpreter", "/usr/bin/python3"]
        mock_main.assert_called_once_with(expected_args)


class TestBuilderEdgeCases:
    """Tests for edge cases and corner scenarios in builder."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_duplicate_modules(self, mock_build_ftl_gate):
        """Test behavior with duplicate module names."""
        mock_build_ftl_gate.return_value = ("/dup/gate.pyz", "dup_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "test_module",
                "--module",
                "test_module",  # Duplicate
                "--ftl-module",
                "ftl_test",
                "--ftl-module",
                "ftl_test",  # Duplicate
            ],
        )

        assert result.exit_code == 0
        # Click should preserve duplicates as tuples
        mock_build_ftl_gate.assert_called_once_with(
            ["test_module", "test_module"], [], None, "/usr/bin/python3"
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_empty_module_names(self, mock_build_ftl_gate):
        """Test behavior with empty module names."""
        mock_build_ftl_gate.return_value = ("/empty/gate.pyz", "empty_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "",
                "--ftl-module",
                "",  # Note: ftl-module is not used in current implementation
                "--module-dir",
                "",
            ],
        )

        assert result.exit_code == 0
        # Note: ftl-module parameter is currently ignored in the implementation
        mock_build_ftl_gate.assert_called_once_with(
            [""],  # Only module parameter is used, not ftl-module
            [""],
            None,
            "/usr/bin/python3",
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_with_special_characters(self, mock_build_ftl_gate):
        """Test with special characters in module names and paths."""
        mock_build_ftl_gate.return_value = ("/special/gate.pyz", "special_hash")

        result = self.runner.invoke(
            main,
            [
                "--module",
                "module-with-dashes",
                "--module",
                "module_with_underscores",
                "--module-dir",
                "/path with spaces/modules",
                "--module-dir",
                "/path/with/unicode/🚀",
                "--interpreter",
                "/opt/python-3.9/bin/python3",
            ],
        )

        assert result.exit_code == 0
        mock_build_ftl_gate.assert_called_once_with(
            ["module-with-dashes", "module_with_underscores"],
            ["/path with spaces/modules", "/path/with/unicode/🚀"],
            None,
            "/opt/python-3.9/bin/python3",
        )

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_return_value_handling(self, mock_build_ftl_gate):
        """Test that gate path is properly printed regardless of return format."""
        # Test different return value formats
        test_cases = [
            ("/simple/gate.pyz", "hash"),  # Tuple format
            "/just/path/gate.pyz",  # String format (if implementation changes)
        ]

        for return_value in test_cases:
            mock_build_ftl_gate.return_value = return_value

            result = self.runner.invoke(main, ["--module", "test"])

            assert result.exit_code == 0
            # Should print the return value (or first element if tuple)
            expected_output = (
                return_value if isinstance(return_value, str) else str(return_value)
            )
            assert expected_output in result.output


class TestBuilderClick:
    """Tests specific to Click framework integration."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    def test_main_click_context_handling(self):
        """Test that Click context is properly handled."""
        # Test that the function works as a Click command
        from click.testing import CliRunner

        runner = CliRunner()

        with patch("faster_than_light.builder.build_ftl_gate") as mock_build:
            mock_build.return_value = ("/context/gate.pyz", "context_hash")
            result = runner.invoke(main, ["--help"])

            assert result.exit_code == 0
            assert "Show this message and exit" in result.output

    @patch("faster_than_light.builder.build_ftl_gate")
    def test_main_multiple_flag_values_as_tuples(self, mock_build_ftl_gate):
        """Test that Click properly handles multiple values as tuples."""
        mock_build_ftl_gate.return_value = ("/tuple/gate.pyz", "tuple_hash")

        result = self.runner.invoke(
            main,
            [
                "-m",
                "mod1",
                "-m",
                "mod2",
                "-m",
                "mod3",
                "-f",
                "ftl1",
                "-f",
                "ftl2",
                "-M",
                "dir1",
                "-M",
                "dir2",
                "-M",
                "dir3",
            ],
        )

        assert result.exit_code == 0

        # Verify that arguments are passed as tuples to build_ftl_gate
        call_args = mock_build_ftl_gate.call_args[0]
        modules, module_dirs, dependencies, interpreter = call_args

        assert modules == ["mod1", "mod2", "mod3"]
        assert module_dirs == ["dir1", "dir2", "dir3"]
        assert dependencies is None
        assert interpreter == "/usr/bin/python3"
