"""
Comprehensive unit tests for faster_than_light.cli module.

Tests all CLI functionality including argument parsing, logging configuration,
module execution, and error handling scenarios using Click's testing framework.
"""

import logging
from unittest.mock import AsyncMock, mock_open, patch

import pytest
from click.testing import CliRunner

from faster_than_light.cli import entry_point, main, parse_module_args


class TestParseModuleArgs:
    """Tests for parse_module_args function."""

    def test_parse_module_args_empty_string(self):
        """Test parsing empty string returns empty dict."""
        result = parse_module_args("")
        assert result == {}

    def test_parse_module_args_none(self):
        """Test parsing None returns empty dict."""
        result = parse_module_args(None)
        assert result == {}

    def test_parse_module_args_single_pair(self):
        """Test parsing single key=value pair."""
        result = parse_module_args("key=value")
        assert result == {"key": "value"}

    def test_parse_module_args_multiple_pairs(self):
        """Test parsing multiple key=value pairs."""
        result = parse_module_args("host=web1 port=8080 debug=true")
        expected = {"host": "web1", "port": "8080", "debug": "true"}
        assert result == expected

    def test_parse_module_args_with_equals_in_values(self):
        """Test parsing args where value contains equals sign fails as expected."""
        # The current implementation doesn't handle this case gracefully
        with pytest.raises(ValueError, match="too many values to unpack"):
            parse_module_args("description=hello=world")

    def test_parse_module_args_multiple_equals_error(self):
        """Test parsing args with multiple equals in single arg raises error."""
        # The current implementation can't handle multiple equals signs
        with pytest.raises(ValueError, match="too many values to unpack"):
            parse_module_args("url=http://example.com:8080/path=value")

    def test_parse_module_args_empty_value(self):
        """Test parsing args with empty values."""
        result = parse_module_args("key1= key2=value2")
        assert result == {"key1": "", "key2": "value2"}

    def test_parse_module_args_special_characters(self):
        """Test parsing args with special characters."""
        result = parse_module_args("path=/tmp/test user=admin@domain.com")
        assert result == {"path": "/tmp/test", "user": "admin@domain.com"}


class TestMainBasicArguments:
    """Tests for main function with basic argument combinations using Click."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_no_args(self, mock_logging):
        """Test main with no arguments shows help and exits with error."""
        result = self.runner.invoke(main, [])

        assert result.exit_code == 2  # Click exit code for missing required option
        assert "Missing option '--inventory'" in result.output
        # logging.basicConfig should not be called since validation fails early
        mock_logging.assert_not_called()

    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_debug_flag(self, mock_logging):
        """Test main with debug flag but missing required inventory."""
        result = self.runner.invoke(main, ["--debug"])

        assert result.exit_code == 2  # Missing required option
        assert "Missing option '--inventory'" in result.output
        mock_logging.assert_not_called()

    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_verbose_flag(self, mock_logging):
        """Test main with verbose flag but missing required inventory."""
        result = self.runner.invoke(main, ["--verbose"])

        assert result.exit_code == 2  # Missing required option
        assert "Missing option '--inventory'" in result.output
        mock_logging.assert_not_called()

    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_debug_takes_precedence_over_verbose(self, mock_logging):
        """Test that debug flag takes precedence over verbose."""
        # Need to provide required inventory and module
        result = self.runner.invoke(
            main,
            ["--debug", "--verbose", "--inventory", "test.yml", "--module", "test"],
        )

        # Will fail due to missing files, but logging should be configured
        mock_logging.assert_called_once_with(level=logging.DEBUG)

    def test_main_help_flag(self):
        """Test main with help flag shows help and exits successfully."""
        result = self.runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Main CLI entry point" in result.output
        assert "--inventory" in result.output

    def test_main_invalid_args(self):
        """Test main with invalid arguments shows error."""
        result = self.runner.invoke(main, ["--invalid-flag"])

        assert result.exit_code == 2
        assert "No such option" in result.output


class TestMainModuleExecution:
    """Tests for main function with module execution scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_run_module_basic(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test running a basic module."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}

        args = [
            "--module",
            "test_module",
            "--module-dir",
            "/modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_load_inventory.assert_called_once_with("inventory.yml")
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/modules"],
            "test_module",
            modules=["test_module"],
            module_args={},
            dependencies=None,
        )
        mock_pprint.assert_called_once_with({"localhost": {"result": "success"}})

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_run_module_with_args(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test running module with arguments."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}

        args = [
            "--module",
            "test_module",
            "--module-dir",
            "/modules",
            "--inventory",
            "inventory.yml",
            "--args",
            "host=web1 port=8080",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/modules"],
            "test_module",
            modules=["test_module"],
            module_args={"host": "web1", "port": "8080"},
            dependencies=None,
        )

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_ftl_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_run_ftl_module_basic(
        self, mock_logging, mock_load_inventory, mock_run_ftl_module, mock_pprint
    ):
        """Test running a basic FTL module."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.return_value = {"localhost": {"result": "success"}}

        args = [
            "--ftl-module",
            "test_ftl_module",
            "--module-dir",
            "/ftl_modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_load_inventory.assert_called_once_with("inventory.yml")
        mock_run_ftl_module.assert_called_once_with(
            {"test": "inventory"},
            ["/ftl_modules"],
            "test_ftl_module",
            module_args={},
        )
        mock_pprint.assert_called_once_with({"localhost": {"result": "success"}})

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_ftl_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_run_ftl_module_with_args(
        self, mock_logging, mock_load_inventory, mock_run_ftl_module, mock_pprint
    ):
        """Test running FTL module with arguments."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.return_value = {"localhost": {"result": "success"}}

        args = [
            "--ftl-module",
            "test_ftl_module",
            "--module-dir",
            "/ftl_modules",
            "--inventory",
            "inventory.yml",
            "--args",
            "config=debug timeout=30",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_run_ftl_module.assert_called_once_with(
            {"test": "inventory"},
            ["/ftl_modules"],
            "test_ftl_module",
            module_args={"config": "debug", "timeout": "30"},
        )


class TestMainRequirements:
    """Tests for main function with requirements file handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_with_requirements_file(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test main with requirements file."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}

        # Mock file reading for requirements
        requirements_content = (
            "requests>=2.25.0\npyyaml>=5.4.0\n\n# Comment line\nclick>=8.0.0"
        )
        expected_deps = [
            "requests>=2.25.0",
            "pyyaml>=5.4.0",
            "# Comment line",
            "click>=8.0.0",
        ]

        with patch("builtins.open", mock_open(read_data=requirements_content)):
            args = [
                "--module",
                "test_module",
                "--module-dir",
                "/modules",
                "--inventory",
                "inventory.yml",
                "--requirements",
                "requirements.txt",
            ]

            result = self.runner.invoke(main, args)

            assert result.exit_code == 0
            mock_run_module.assert_called_once_with(
                {"test": "inventory"},
                ["/modules"],
                "test_module",
                modules=["test_module"],
                module_args={},
                dependencies=expected_deps,
            )

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_with_empty_requirements_file(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test main with empty requirements file."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}

        with patch("builtins.open", mock_open(read_data="")):
            args = [
                "--module",
                "test_module",
                "--module-dir",
                "/modules",
                "--inventory",
                "inventory.yml",
                "--requirements",
                "empty_requirements.txt",
            ]

            result = self.runner.invoke(main, args)

            assert result.exit_code == 0
            mock_run_module.assert_called_once_with(
                {"test": "inventory"},
                ["/modules"],
                "test_module",
                modules=["test_module"],
                module_args={},
                dependencies=[],  # Empty list for empty file
            )


class TestMainErrorHandling:
    """Tests for main function error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.load_inventory")
    def test_main_inventory_file_error(self, mock_load_inventory):
        """Test main when inventory file cannot be loaded."""
        mock_load_inventory.side_effect = FileNotFoundError("Inventory file not found")

        args = [
            "--module",
            "test_module",
            "--module-dir",
            "/modules",
            "--inventory",
            "nonexistent.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code != 0
        assert isinstance(result.exception, FileNotFoundError)
        assert "Inventory file not found" in str(result.exception)

    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    def test_main_module_execution_error(self, mock_load_inventory, mock_run_module):
        """Test main when module execution fails."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.side_effect = Exception("Module execution failed")

        args = [
            "--module",
            "test_module",
            "--module-dir",
            "/modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code != 0
        assert result.exception is not None

    @patch("faster_than_light.cli.run_ftl_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    def test_main_ftl_module_execution_error(
        self, mock_load_inventory, mock_run_ftl_module
    ):
        """Test main when FTL module execution fails."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.side_effect = Exception("FTL module execution failed")

        args = [
            "--ftl-module",
            "test_ftl_module",
            "--module-dir",
            "/ftl_modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code != 0
        assert result.exception is not None


class TestMainComplexScenarios:
    """Tests for main function with complex argument combinations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_all_options_combined(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test main with all options combined."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}

        with patch("builtins.open", mock_open(read_data="requests>=2.25.0")):
            args = [
                "--debug",
                "--module",
                "complex_module",
                "--module-dir",
                "/opt/modules",
                "--inventory",
                "production.yml",
                "--requirements",
                "requirements.txt",
                "--args",
                "env=production debug=true",
            ]

            result = self.runner.invoke(main, args)

            assert result.exit_code == 0
            mock_logging.assert_called_once_with(level=logging.DEBUG)
            mock_run_module.assert_called_once_with(
                {"test": "inventory"},
                ["/opt/modules"],
                "complex_module",
                modules=["complex_module"],
                module_args={"env": "production", "debug": "true"},
                dependencies=["requests>=2.25.0"],
            )

    def test_main_both_module_and_ftl_module(self):
        """Test main when both module and ftl-module are specified (should fail)."""
        args = [
            "--module",
            "test_module",
            "--ftl-module",
            "test_ftl_module",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 1  # Click exception exit code
        assert "Cannot specify both --ftl-module and --module" in result.output


class TestMainArgumentValidation:
    """Tests for main function argument validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_main_module_without_inventory(self):
        """Test main with module but no inventory (should fail)."""
        result = self.runner.invoke(main, ["--module", "test_module"])

        assert result.exit_code == 2
        assert "Missing option '--inventory'" in result.output

    def test_main_inventory_without_module(self):
        """Test main with inventory but no module or ftl-module (should fail)."""
        result = self.runner.invoke(main, ["--inventory", "inventory.yml"])

        assert result.exit_code == 1  # Our custom validation
        assert "Must specify either --ftl-module or --module" in result.output

    @patch("faster_than_light.cli.load_inventory")
    def test_main_module_without_module_dir(self, mock_load_inventory):
        """Test main with module but no module-dir (should work with empty list)."""
        mock_load_inventory.return_value = {"test": "inventory"}

        with patch(
            "faster_than_light.cli.run_module", new_callable=AsyncMock
        ) as mock_run_module:
            mock_run_module.return_value = {"localhost": {"result": "success"}}

            args = ["--module", "test_module", "--inventory", "inventory.yml"]

            result = self.runner.invoke(main, args)

            assert result.exit_code == 0
            mock_run_module.assert_called_once_with(
                {"test": "inventory"},
                [],  # Empty module_dir list
                "test_module",
                modules=["test_module"],
                module_args={},
                dependencies=None,
            )


class TestEntryPoint:
    """Tests for entry_point function."""

    def test_entry_point_calls_main(self):
        """Test that entry_point calls main with Click handling."""
        # Since entry_point() just calls main() directly, and main is a Click command,
        # we can test that it works by checking the help output
        with patch("faster_than_light.cli.sys.argv", ["ftl", "--help"]):
            # entry_point() should call main() which will show help and exit
            with pytest.raises(SystemExit) as exc_info:
                entry_point()

            # Help command should exit with code 0
            assert exc_info.value.code == 0

    def test_entry_point_with_args(self):
        """Test entry_point with different argument combinations."""
        # Test with missing inventory - should exit with error code 2
        with patch("faster_than_light.cli.sys.argv", ["ftl", "--module", "test"]):
            with pytest.raises(SystemExit) as exc_info:
                entry_point()

            # Missing required option should exit with code 2
            assert exc_info.value.code == 2


class TestCliIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_real_world_cli_scenario(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test a realistic CLI usage scenario."""
        # Setup realistic inventory and module execution result
        mock_load_inventory.return_value = {
            "all": {
                "hosts": {
                    "web1": {"ansible_host": "192.168.1.10"},
                    "web2": {"ansible_host": "192.168.1.11"},
                }
            }
        }

        mock_run_module.return_value = {
            "web1": {
                "changed": True,
                "stdout": "Service restarted successfully",
                "rc": 0,
            },
            "web2": {
                "changed": True,
                "stdout": "Service restarted successfully",
                "rc": 0,
            },
        }

        args = [
            "--verbose",
            "--module",
            "service",
            "--module-dir",
            "/opt/ansible/library",
            "--inventory",
            "production.yml",
            "--args",
            "name=nginx state=restarted",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_logging.assert_called_once_with(level=logging.INFO)
        mock_load_inventory.assert_called_once_with("production.yml")
        mock_run_module.assert_called_once_with(
            mock_load_inventory.return_value,
            ["/opt/ansible/library"],
            "service",
            modules=["service"],
            module_args={"name": "nginx", "state": "restarted"},
            dependencies=None,
        )
        mock_pprint.assert_called_once_with(mock_run_module.return_value)


class TestCliEdgeCases:
    """Edge case tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_main_with_empty_args_list(self):
        """Test main with explicitly empty args list."""
        result = self.runner.invoke(main, [])

        assert result.exit_code == 2  # Missing required inventory
        assert "Missing option '--inventory'" in result.output

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_module_returns_none(
        self, mock_logging, mock_load_inventory, mock_run_module, mock_pprint
    ):
        """Test main when module execution returns None."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = None

        args = [
            "--module",
            "test_module",
            "--module-dir",
            "/modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_pprint.assert_called_once_with(None)

    @patch("faster_than_light.cli.pprint")
    @patch("faster_than_light.cli.run_ftl_module", new_callable=AsyncMock)
    @patch("faster_than_light.cli.load_inventory")
    @patch("faster_than_light.cli.logging.basicConfig")
    def test_main_ftl_module_returns_complex_data(
        self, mock_logging, mock_load_inventory, mock_run_ftl_module, mock_pprint
    ):
        """Test main when FTL module returns complex nested data."""
        mock_load_inventory.return_value = {"test": "inventory"}
        complex_result = {
            "host1": {
                "result": {
                    "nested": {"data": [1, 2, 3]},
                    "metadata": {"timestamp": "2023-01-01", "version": "1.0"},
                }
            }
        }
        mock_run_ftl_module.return_value = complex_result

        args = [
            "--ftl-module",
            "complex_module",
            "--module-dir",
            "/ftl_modules",
            "--inventory",
            "inventory.yml",
        ]

        result = self.runner.invoke(main, args)

        assert result.exit_code == 0
        mock_pprint.assert_called_once_with(complex_result)

    def test_main_with_special_characters_in_args(self):
        """Test main with special characters in module arguments."""
        with patch("faster_than_light.cli.load_inventory") as mock_load_inventory:
            with patch(
                "faster_than_light.cli.run_module", new_callable=AsyncMock
            ) as mock_run_module:
                mock_load_inventory.return_value = {"test": "inventory"}
                mock_run_module.return_value = {"localhost": {"result": "success"}}

                args = [
                    "--module",
                    "test_module",
                    "--inventory",
                    "inventory.yml",
                    "--args",
                    "path=/tmp/test@domain.com user=admin@example.org",
                ]

                result = self.runner.invoke(main, args)

                assert result.exit_code == 0
                expected_args = {
                    "path": "/tmp/test@domain.com",
                    "user": "admin@example.org",
                }
                mock_run_module.assert_called_once()
                actual_call = mock_run_module.call_args
                assert actual_call[1]["module_args"] == expected_args
