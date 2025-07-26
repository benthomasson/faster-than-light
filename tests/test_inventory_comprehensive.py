"""
Comprehensive unit tests for faster_than_light.inventory module.

Tests all inventory management functionality including YAML loading,
localhost configuration generation, file operations, and error handling.
"""

import os
import sys
import tempfile
from unittest.mock import mock_open, patch

import pytest
import yaml

from faster_than_light.inventory import (
    entry_point,
    load_inventory,
    load_localhost,
    write_localhost,
)


class TestLoadInventory:
    """Tests for load_inventory function."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_basic_success(self, mock_yaml_load, mock_file):
        """Test basic successful inventory loading."""
        # Setup test data
        test_inventory = {
            "all": {
                "hosts": {
                    "web1": {"ansible_host": "192.168.1.10"},
                    "web2": {"ansible_host": "192.168.1.11"},
                }
            }
        }

        mock_file.return_value.read.return_value = "inventory content"
        mock_yaml_load.return_value = test_inventory

        result = load_inventory("test_inventory.yml")

        # Verify result
        assert result == test_inventory

        # Verify file operations
        mock_file.assert_called_once_with("test_inventory.yml")
        mock_file.return_value.read.assert_called_once()
        mock_yaml_load.assert_called_once_with("inventory content")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_empty_file(self, mock_yaml_load, mock_file):
        """Test loading inventory from empty file."""
        mock_file.return_value.read.return_value = ""
        mock_yaml_load.return_value = None  # YAML returns None for empty content

        result = load_inventory("empty.yml")

        # Should return empty dict when YAML returns None
        assert result == {}
        mock_yaml_load.assert_called_once_with("")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_complex_structure(self, mock_yaml_load, mock_file):
        """Test loading complex inventory structure."""
        complex_inventory = {
            "all": {
                "children": {
                    "webservers": {
                        "hosts": {
                            "web1": {
                                "ansible_host": "192.168.1.10",
                                "ansible_user": "deploy",
                                "http_port": 80,
                            },
                            "web2": {
                                "ansible_host": "192.168.1.11",
                                "ansible_user": "deploy",
                                "http_port": 8080,
                            },
                        },
                        "vars": {"http_port": 80, "max_connections": 100},
                    },
                    "dbservers": {
                        "hosts": {
                            "db1": {"ansible_host": "192.168.1.20", "mysql_port": 3306}
                        }
                    },
                }
            }
        }

        mock_file.return_value.read.return_value = "complex yaml content"
        mock_yaml_load.return_value = complex_inventory

        result = load_inventory("complex.yml")

        assert result == complex_inventory
        assert "webservers" in result["all"]["children"]
        assert "dbservers" in result["all"]["children"]
        assert result["all"]["children"]["webservers"]["vars"]["max_connections"] == 100

    @patch("builtins.open")
    def test_load_inventory_file_not_found(self, mock_file):
        """Test FileNotFoundError handling."""
        mock_file.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            load_inventory("nonexistent.yml")

    @patch("builtins.open")
    def test_load_inventory_permission_error(self, mock_file):
        """Test PermissionError handling."""
        mock_file.side_effect = PermissionError("Permission denied")

        with pytest.raises(PermissionError):
            load_inventory("protected.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_yaml_parse_error(self, mock_yaml_load, mock_file):
        """Test YAML parsing error handling."""
        mock_file.return_value.read.return_value = "invalid: yaml: content: ["
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML syntax")

        with pytest.raises(yaml.YAMLError):
            load_inventory("invalid.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_unicode_content(self, mock_yaml_load, mock_file):
        """Test loading inventory with unicode content."""
        unicode_inventory = {
            "all": {
                "hosts": {
                    "服务器1": {
                        "ansible_host": "192.168.1.10",
                        "description": "测试服务器",
                    },
                    "server-émoji": {"ansible_host": "192.168.1.11", "emoji": "🚀"},
                }
            }
        }

        mock_file.return_value.read.return_value = "unicode content"
        mock_yaml_load.return_value = unicode_inventory

        result = load_inventory("unicode.yml")

        assert result == unicode_inventory
        assert "服务器1" in result["all"]["hosts"]
        assert result["all"]["hosts"]["server-émoji"]["emoji"] == "🚀"

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_returns_dict_for_falsy_yaml(
        self, mock_yaml_load, mock_file
    ):
        """Test that falsy YAML values return empty dict."""
        test_cases = [None, False, 0, "", []]

        for falsy_value in test_cases:
            mock_file.return_value.read.return_value = f"content for {falsy_value}"
            mock_yaml_load.return_value = falsy_value

            result = load_inventory("test.yml")
            assert result == {}, f"Failed for falsy value: {falsy_value}"


class TestLoadLocalhost:
    """Tests for load_localhost function."""

    def test_load_localhost_default_interpreter(self):
        """Test localhost loading with default interpreter."""
        result = load_localhost()

        expected = {
            "all": {
                "hosts": {
                    "localhost": {
                        "ansible_connection": "local",
                        "ansible_python_interpreter": sys.executable,
                    }
                }
            }
        }

        assert result == expected
        assert (
            result["all"]["hosts"]["localhost"]["ansible_python_interpreter"]
            == sys.executable
        )

    def test_load_localhost_custom_interpreter(self):
        """Test localhost loading with custom interpreter."""
        custom_interpreter = "/usr/bin/python3.9"

        result = load_localhost(interpreter=custom_interpreter)

        expected = {
            "all": {
                "hosts": {
                    "localhost": {
                        "ansible_connection": "local",
                        "ansible_python_interpreter": custom_interpreter,
                    }
                }
            }
        }

        assert result == expected
        assert (
            result["all"]["hosts"]["localhost"]["ansible_python_interpreter"]
            == custom_interpreter
        )

    def test_load_localhost_none_interpreter_uses_default(self):
        """Test that explicitly passing None uses default interpreter."""
        result = load_localhost(interpreter=None)

        assert (
            result["all"]["hosts"]["localhost"]["ansible_python_interpreter"]
            == sys.executable
        )

    def test_load_localhost_empty_string_interpreter(self):
        """Test localhost with empty string interpreter."""
        result = load_localhost(interpreter="")

        assert result["all"]["hosts"]["localhost"]["ansible_python_interpreter"] == ""

    def test_load_localhost_structure_integrity(self):
        """Test that localhost inventory has correct structure."""
        result = load_localhost()

        # Verify structure
        assert "all" in result
        assert "hosts" in result["all"]
        assert "localhost" in result["all"]["hosts"]

        localhost_config = result["all"]["hosts"]["localhost"]
        assert "ansible_connection" in localhost_config
        assert "ansible_python_interpreter" in localhost_config
        assert localhost_config["ansible_connection"] == "local"

    def test_load_localhost_immutability(self):
        """Test that multiple calls return independent objects."""
        result1 = load_localhost()
        result2 = load_localhost()

        # Should be equal but not the same object
        assert result1 == result2
        assert result1 is not result2

        # Modifying one shouldn't affect the other
        result1["all"]["hosts"]["localhost"]["test"] = "value"
        assert "test" not in result2["all"]["hosts"]["localhost"]


class TestWriteLocalhost:
    """Tests for write_localhost function."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_default_filename(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test writing localhost inventory with default filename."""
        test_inventory = {"test": "data"}
        mock_load_localhost.return_value = test_inventory

        write_localhost()

        # Verify file operations
        mock_file.assert_called_once_with("inventory.yml", "w")
        mock_load_localhost.assert_called_once()
        mock_yaml_dump.assert_called_once_with(
            test_inventory, stream=mock_file.return_value
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_custom_filename(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test writing localhost inventory with custom filename."""
        test_inventory = {"custom": "inventory"}
        mock_load_localhost.return_value = test_inventory
        custom_filename = "custom_inventory.yml"

        write_localhost(custom_filename)

        # Verify file operations
        mock_file.assert_called_once_with(custom_filename, "w")
        mock_load_localhost.assert_called_once()
        mock_yaml_dump.assert_called_once_with(
            test_inventory, stream=mock_file.return_value
        )

    @patch("builtins.open")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_file_creation_error(self, mock_load_localhost, mock_file):
        """Test file creation error handling."""
        mock_load_localhost.return_value = {"test": "data"}
        mock_file.side_effect = PermissionError("Cannot create file")

        with pytest.raises(PermissionError):
            write_localhost("protected_dir/inventory.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_yaml_dump_error(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test YAML dump error handling."""
        mock_load_localhost.return_value = {"test": "data"}
        mock_yaml_dump.side_effect = yaml.YAMLError("Cannot serialize data")

        with pytest.raises(yaml.YAMLError):
            write_localhost()

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_complex_inventory(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test writing complex localhost inventory."""
        complex_inventory = {
            "all": {
                "hosts": {
                    "localhost": {
                        "ansible_connection": "local",
                        "ansible_python_interpreter": "/usr/bin/python3",
                        "custom_vars": {"environment": "test", "debug": True},
                    }
                }
            }
        }
        mock_load_localhost.return_value = complex_inventory

        write_localhost("complex.yml")

        mock_yaml_dump.assert_called_once_with(
            complex_inventory, stream=mock_file.return_value
        )


class TestEntryPoint:
    """Tests for entry_point function."""

    @patch("faster_than_light.inventory.write_localhost")
    def test_entry_point_calls_write_localhost(self, mock_write_localhost):
        """Test that entry_point calls write_localhost with no arguments."""
        entry_point()

        mock_write_localhost.assert_called_once_with()

    @patch("faster_than_light.inventory.write_localhost")
    def test_entry_point_error_propagation(self, mock_write_localhost):
        """Test that entry_point propagates errors from write_localhost."""
        mock_write_localhost.side_effect = IOError("Disk full")

        with pytest.raises(IOError, match="Disk full"):
            entry_point()


class TestInventoryIntegration:
    """Integration tests for inventory functions working together."""

    def test_load_localhost_write_localhost_roundtrip(self):
        """Test that load_localhost and write_localhost work together."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            # Generate localhost inventory and write it
            write_localhost(tmp_filename)

            # Load it back and verify
            loaded_inventory = load_inventory(tmp_filename)
            expected_inventory = load_localhost()

            assert loaded_inventory == expected_inventory
            assert "localhost" in loaded_inventory["all"]["hosts"]
            assert (
                loaded_inventory["all"]["hosts"]["localhost"]["ansible_connection"]
                == "local"
            )

        finally:
            # Clean up
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

    def test_custom_interpreter_roundtrip(self):
        """Test roundtrip with custom interpreter."""
        custom_interpreter = "/opt/python/bin/python3"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            # Create localhost with custom interpreter
            original_inventory = load_localhost(interpreter=custom_interpreter)

            # Write to file (need to patch load_localhost in write_localhost)
            with patch(
                "faster_than_light.inventory.load_localhost",
                return_value=original_inventory,
            ):
                write_localhost(tmp_filename)

            # Load back and verify
            loaded_inventory = load_inventory(tmp_filename)

            assert loaded_inventory == original_inventory
            assert (
                loaded_inventory["all"]["hosts"]["localhost"][
                    "ansible_python_interpreter"
                ]
                == custom_interpreter
            )

        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)


class TestInventoryEdgeCases:
    """Tests for edge cases and error scenarios."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_large_file(self, mock_yaml_load, mock_file):
        """Test loading very large inventory file."""
        # Simulate large inventory
        large_inventory = {
            "all": {
                "hosts": {
                    f"host_{i}": {"ansible_host": f"192.168.1.{i}"} for i in range(1000)
                }
            }
        }

        mock_file.return_value.read.return_value = "large content"
        mock_yaml_load.return_value = large_inventory

        result = load_inventory("large.yml")

        assert len(result["all"]["hosts"]) == 1000
        assert "host_999" in result["all"]["hosts"]

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_deeply_nested(self, mock_yaml_load, mock_file):
        """Test loading deeply nested inventory structure."""
        nested_inventory = {
            "all": {
                "children": {
                    "level1": {
                        "children": {
                            "level2": {
                                "children": {
                                    "level3": {"hosts": {"deep_host": {"var": "value"}}}
                                }
                            }
                        }
                    }
                }
            }
        }

        mock_file.return_value.read.return_value = "nested content"
        mock_yaml_load.return_value = nested_inventory

        result = load_inventory("nested.yml")

        assert (
            result["all"]["children"]["level1"]["children"]["level2"]["children"][
                "level3"
            ]["hosts"]["deep_host"]["var"]
            == "value"
        )

    def test_load_localhost_with_special_characters(self):
        """Test load_localhost with interpreter path containing special characters."""
        special_interpreter = "/path with spaces/python3.exe"

        result = load_localhost(interpreter=special_interpreter)

        assert (
            result["all"]["hosts"]["localhost"]["ansible_python_interpreter"]
            == special_interpreter
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_with_special_filename(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test writing localhost with filename containing special characters."""
        mock_load_localhost.return_value = {"test": "data"}
        special_filename = "inventory with spaces & symbols!.yml"

        write_localhost(special_filename)

        mock_file.assert_called_once_with(special_filename, "w")


class TestInventoryFileFormats:
    """Tests for different inventory file formats and variations."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_yaml_variations(self, mock_yaml_load, mock_file):
        """Test loading different YAML format variations."""
        # Test various YAML structures that should all be valid
        yaml_variations = [
            # Simple flat structure
            {"hosts": {"server1": {"ansible_host": "1.2.3.4"}}},
            # List format
            ["host1", "host2", "host3"],
            # Mixed types
            {
                "string_var": "value",
                "int_var": 42,
                "bool_var": True,
                "null_var": None,
                "list_var": [1, 2, 3],
                "dict_var": {"nested": "value"},
            },
        ]

        for i, variation in enumerate(yaml_variations):
            mock_file.return_value.read.return_value = f"content_{i}"
            mock_yaml_load.return_value = variation

            result = load_inventory(f"variation_{i}.yml")
            assert result == variation


class TestInventoryErrorRecovery:
    """Tests for error recovery and graceful degradation."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_inventory_partial_yaml_error(self, mock_yaml_load, mock_file):
        """Test handling of partially corrupted YAML."""
        mock_file.return_value.read.return_value = "partial content"
        mock_yaml_load.side_effect = yaml.constructor.ConstructorError(
            "found undefined constructor", None, "test error", None
        )

        with pytest.raises(yaml.constructor.ConstructorError):
            load_inventory("partial.yml")

    @patch("builtins.open", new_callable=mock_open)
    def test_load_inventory_io_error_during_read(self, mock_file):
        """Test IO error during file read operation."""
        mock_file.return_value.read.side_effect = IOError("Disk read error")

        with pytest.raises(IOError, match="Disk read error"):
            load_inventory("problematic.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    @patch("faster_than_light.inventory.load_localhost")
    def test_write_localhost_io_error_during_write(
        self, mock_load_localhost, mock_yaml_dump, mock_file
    ):
        """Test IO error during file write operation."""
        mock_load_localhost.return_value = {"test": "data"}
        mock_yaml_dump.side_effect = IOError("Disk write error")

        with pytest.raises(IOError, match="Disk write error"):
            write_localhost("output.yml")
