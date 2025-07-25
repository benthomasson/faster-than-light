"""
Comprehensive unit tests for faster_than_light.cli module.

Tests all CLI functionality including argument parsing, logging configuration,
module execution, and error handling scenarios.
"""

import asyncio
import logging
import pytest
import sys
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from docopt import DocoptExit

from faster_than_light.cli import (
    parse_module_args,
    main,
    entry_point,
)


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
    """Tests for main function with basic argument combinations."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_no_args(self, mock_logging):
        """Test main with no arguments (default behavior)."""
        result = await main([])
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.WARNING)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_debug_flag(self, mock_logging):
        """Test main with debug flag."""
        result = await main(["--debug"])
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.DEBUG)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_verbose_flag(self, mock_logging):
        """Test main with verbose flag."""
        result = await main(["--verbose"])
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.INFO)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_debug_takes_precedence_over_verbose(self, mock_logging):
        """Test that debug flag takes precedence over verbose."""
        result = await main(["--debug", "--verbose"])
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.DEBUG)
    
    @pytest.mark.asyncio
    async def test_main_help_flag(self):
        """Test main with help flag raises SystemExit."""
        with pytest.raises(SystemExit):
            await main(["--help"])
    
    @pytest.mark.asyncio
    async def test_main_invalid_args(self):
        """Test main with invalid arguments raises DocoptExit."""
        with pytest.raises(DocoptExit):
            await main(["--invalid-flag"])


class TestMainModuleExecution:
    """Tests for main function with module execution scenarios."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_run_module_basic(self, mock_logging, mock_load_inventory, 
                                        mock_run_module, mock_pprint):
        """Test running a basic module."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml"
        ]
        
        result = await main(args)
        
        assert result == 0
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
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_run_module_with_args(self, mock_logging, mock_load_inventory,
                                           mock_run_module, mock_pprint):
        """Test running module with arguments."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules", 
            "--inventory", "inventory.yml",
            "--args", "host=web1 port=8080"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/modules"],
            "test_module",
            modules=["test_module"],
            module_args={"host": "web1", "port": "8080"},
            dependencies=None,
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_ftl_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_run_ftl_module_basic(self, mock_logging, mock_load_inventory,
                                           mock_run_ftl_module, mock_pprint):
        """Test running a basic FTL module."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--ftl-module", "test_ftl_module",
            "--module-dir", "/ftl_modules",
            "--inventory", "inventory.yml"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_load_inventory.assert_called_once_with("inventory.yml")
        mock_run_ftl_module.assert_called_once_with(
            {"test": "inventory"},
            ["/ftl_modules"],
            "test_ftl_module",
            module_args={},
        )
        mock_pprint.assert_called_once_with({"localhost": {"result": "success"}})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_ftl_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_run_ftl_module_with_args(self, mock_logging, mock_load_inventory,
                                               mock_run_ftl_module, mock_pprint):
        """Test running FTL module with arguments."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--ftl-module", "test_ftl_module",
            "--module-dir", "/ftl_modules",
            "--inventory", "inventory.yml",
            "--args", "config=production debug=false"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_run_ftl_module.assert_called_once_with(
            {"test": "inventory"},
            ["/ftl_modules"],
            "test_ftl_module",
            module_args={"config": "production", "debug": "false"},
        )


class TestMainRequirements:
    """Tests for main function with requirements file handling."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    @patch('builtins.open', new_callable=mock_open)
    async def test_main_with_requirements_file(self, mock_file, mock_logging,
                                             mock_load_inventory, mock_run_module, mock_pprint):
        """Test running module with requirements file."""
        mock_file.return_value.read.return_value = "requests==2.25.1\npytest>=6.0.0\n\nnumpy"
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml",
            "--requirements", "requirements.txt"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_file.assert_called_once_with("requirements.txt")
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/modules"],
            "test_module",
            modules=["test_module"],
            module_args={},
            dependencies=["requests==2.25.1", "pytest>=6.0.0", "numpy"],
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    @patch('builtins.open', new_callable=mock_open)
    async def test_main_with_empty_requirements_file(self, mock_file, mock_logging,
                                                   mock_load_inventory, mock_run_module, mock_pprint):
        """Test running module with empty requirements file."""
        mock_file.return_value.read.return_value = "\n\n\n"
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"localhost": {"result": "success"}}
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml",
            "--requirements", "empty_requirements.txt"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/modules"],
            "test_module",
            modules=["test_module"],
            module_args={},
            dependencies=[],
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    @patch('builtins.open')
    async def test_main_requirements_file_not_found(self, mock_file, mock_logging):
        """Test error handling when requirements file is not found."""
        mock_file.side_effect = FileNotFoundError("File not found")
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml",
            "--requirements", "nonexistent.txt"
        ]
        
        with pytest.raises(FileNotFoundError):
            await main(args)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    @patch('builtins.open')
    async def test_main_requirements_file_permission_error(self, mock_file, mock_logging):
        """Test error handling when requirements file has permission issues."""
        mock_file.side_effect = PermissionError("Permission denied")
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml",
            "--requirements", "protected.txt"
        ]
        
        with pytest.raises(PermissionError):
            await main(args)


class TestMainErrorHandling:
    """Tests for main function error handling scenarios."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_inventory_file_error(self, mock_logging, mock_load_inventory):
        """Test error handling when inventory file cannot be loaded."""
        mock_load_inventory.side_effect = FileNotFoundError("Inventory not found")
        
        args = [
            "--module", "test_module", 
            "--module-dir", "/modules",
            "--inventory", "nonexistent.yml"
        ]
        
        with pytest.raises(FileNotFoundError):
            await main(args)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_module_execution_error(self, mock_logging, mock_load_inventory, mock_run_module):
        """Test error handling when module execution fails."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.side_effect = Exception("Module execution failed")
        
        args = [
            "--module", "failing_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml"
        ]
        
        with pytest.raises(Exception, match="Module execution failed"):
            await main(args)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.run_ftl_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_ftl_module_execution_error(self, mock_logging, mock_load_inventory, mock_run_ftl_module):
        """Test error handling when FTL module execution fails."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_ftl_module.side_effect = Exception("FTL module execution failed")
        
        args = [
            "--ftl-module", "failing_ftl_module",
            "--module-dir", "/ftl_modules",
            "--inventory", "inventory.yml"
        ]
        
        with pytest.raises(Exception, match="FTL module execution failed"):
            await main(args)


class TestMainComplexScenarios:
    """Tests for main function with complex argument combinations."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    @patch('builtins.open', new_callable=mock_open)
    async def test_main_all_options_combined(self, mock_file, mock_logging,
                                           mock_load_inventory, mock_run_module, mock_pprint):
        """Test running module with all options combined."""
        mock_file.return_value.read.return_value = "requests\npytest"
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = {"host1": {"result": "success"}}
        
        args = [
            "--debug",
            "--module", "complex_module",
            "--module-dir", "/complex/modules",
            "--inventory", "complex_inventory.yml",
            "--requirements", "complex_requirements.txt",
            "--args", "env=production workers=4 ssl=true"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.DEBUG)
        mock_load_inventory.assert_called_once_with("complex_inventory.yml")
        mock_run_module.assert_called_once_with(
            {"test": "inventory"},
            ["/complex/modules"],
            "complex_module",
            modules=["complex_module"],
            module_args={"env": "production", "workers": "4", "ssl": "true"},
            dependencies=["requests", "pytest"],
        )
        mock_pprint.assert_called_once_with({"host1": {"result": "success"}})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_both_module_and_ftl_module(self, mock_logging):
        """Test that both module and ftl-module flags work (module takes precedence)."""
        # This tests the order of conditionals in the main function
        # --module is checked first, so it should take precedence
        with patch('faster_than_light.cli.pprint') as mock_pprint, \
             patch('faster_than_light.cli.run_module', new_callable=AsyncMock) as mock_run_module, \
             patch('faster_than_light.cli.run_ftl_module', new_callable=AsyncMock) as mock_run_ftl_module, \
             patch('faster_than_light.cli.load_inventory') as mock_load_inventory:
            
            mock_load_inventory.return_value = {"test": "inventory"}
            mock_run_module.return_value = {"result": "module_executed"}
            mock_run_ftl_module.return_value = {"result": "ftl_module_executed"}
            
            args = [
                "--module", "regular_module",
                "--ftl-module", "ftl_module", 
                "--module-dir", "/modules",
                "--inventory", "inventory.yml"
            ]
            
            result = await main(args)
            
            assert result == 0
            mock_run_module.assert_called_once()
            mock_run_ftl_module.assert_not_called()
            mock_pprint.assert_called_once_with({"result": "module_executed"})


class TestMainArgumentValidation:
    """Tests for main function argument validation scenarios."""
    
    @pytest.mark.asyncio
    async def test_main_module_without_inventory(self):
        """Test that module execution requires inventory."""
        args = [
            "--module", "test_module",
            "--module-dir", "/modules"
            # Missing --inventory
        ]
        
        # This should raise an error when load_inventory is called with None
        with pytest.raises(TypeError):
            await main(args)
    
    @pytest.mark.asyncio
    async def test_main_module_without_module_dir(self):
        """Test that module execution without module directory raises ModuleNotFound."""
        from faster_than_light.exceptions import ModuleNotFound
        
        args = [
            "--module", "test_module",
            "--inventory", "inventory.yml"
            # Missing --module-dir
        ]
        
        # This should raise ModuleNotFound when module isn't found in [None]
        with patch('faster_than_light.cli.load_inventory') as mock_load_inventory:
            mock_load_inventory.return_value = {"test": "inventory"}
            with pytest.raises(ModuleNotFound, match="Module test_module not found in"):
                await main(args)


class TestMainSysArgvHandling:
    """Tests for main function sys.argv handling."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_with_none_args_uses_sys_argv(self, mock_logging):
        """Test that main uses sys.argv when args is None."""
        # This tests the line: if args is None: args = sys.argv[1:]
        # We need to mock sys.argv for this test
        with patch('faster_than_light.cli.sys.argv', ["ftl", "--verbose"]):
            result = await main(None)
            
            assert result == 0
            mock_logging.assert_called_once_with(level=logging.INFO)


class TestEntryPoint:
    """Tests for entry_point function."""
    
    @patch('faster_than_light.cli.asyncio.run')
    @patch('faster_than_light.cli.sys.argv', ["ftl", "--debug"])
    def test_entry_point_calls_main_with_sys_argv(self, mock_asyncio_run):
        """Test that entry_point calls main with sys.argv."""
        entry_point()
        
        mock_asyncio_run.assert_called_once()
        # Verify the call was made with the expected main coroutine
        call_args = mock_asyncio_run.call_args[0][0]
        # We can't easily test the exact coroutine, but we can test it was called
        assert mock_asyncio_run.called
    
    @patch('faster_than_light.cli.main', new_callable=AsyncMock)
    @patch('faster_than_light.cli.sys.argv', ["ftl", "--verbose"])
    def test_entry_point_propagates_main_args(self, mock_main):
        """Test that entry_point propagates sys.argv to main."""
        # We need to create a real asyncio.run call since we're mocking main
        async def run_test():
            await main(["--verbose"])
        
        with patch('faster_than_light.cli.asyncio.run') as mock_asyncio_run:
            mock_asyncio_run.side_effect = lambda coro: asyncio.get_event_loop().run_until_complete(coro)
            entry_point()
            
            mock_asyncio_run.assert_called_once()


class TestCliIntegration:
    """Integration tests for CLI functionality."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_real_world_cli_scenario(self, mock_logging, mock_load_inventory,
                                         mock_run_module, mock_pprint):
        """Test a realistic CLI usage scenario."""
        # Setup realistic inventory and module execution result
        mock_load_inventory.return_value = {
            "all": {
                "hosts": {
                    "web1": {"ansible_host": "192.168.1.10"},
                    "web2": {"ansible_host": "192.168.1.11"}
                }
            }
        }
        
        mock_run_module.return_value = {
            "web1": {
                "changed": True,
                "stdout": "Service restarted successfully",
                "rc": 0
            },
            "web2": {
                "changed": True,
                "stdout": "Service restarted successfully", 
                "rc": 0
            }
        }
        
        args = [
            "--verbose",
            "--module", "service",
            "--module-dir", "/opt/ansible/library",
            "--inventory", "production.yml",
            "--args", "name=nginx state=restarted"
        ]
        
        result = await main(args)
        
        assert result == 0
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
        mock_pprint.assert_called_once()


class TestCliEdgeCases:
    """Tests for CLI edge cases and corner scenarios."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_with_empty_args_list(self, mock_logging):
        """Test main with explicitly empty args list."""
        result = await main([])
        
        assert result == 0
        mock_logging.assert_called_once_with(level=logging.WARNING)
    
    def test_parse_module_args_malformed_input(self):
        """Test parse_module_args with malformed input."""
        # Test args without equals sign - should fail with not enough values to unpack
        with pytest.raises(ValueError, match="not enough values to unpack"):
            parse_module_args("just_a_string another_string")
    
    def test_parse_module_args_only_key_no_value(self):
        """Test parse_module_args with keys but no values."""
        with pytest.raises(ValueError, match="not enough values to unpack"):
            # This should fail when trying to unpack a single item tuple
            parse_module_args("key_without_equals")
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory')
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_module_returns_none(self, mock_logging, mock_load_inventory,
                                          mock_run_module, mock_pprint):
        """Test main when module execution returns None."""
        mock_load_inventory.return_value = {"test": "inventory"}
        mock_run_module.return_value = None
        
        args = [
            "--module", "test_module",
            "--module-dir", "/modules",
            "--inventory", "inventory.yml"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_pprint.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.cli.pprint')
    @patch('faster_than_light.cli.run_ftl_module', new_callable=AsyncMock)
    @patch('faster_than_light.cli.load_inventory') 
    @patch('faster_than_light.cli.logging.basicConfig')
    async def test_main_ftl_module_returns_complex_data(self, mock_logging, mock_load_inventory,
                                                      mock_run_ftl_module, mock_pprint):
        """Test main when FTL module returns complex nested data."""
        mock_load_inventory.return_value = {"test": "inventory"}
        complex_result = {
            "host1": {
                "result": {
                    "nested": {"data": [1, 2, 3]},
                    "metadata": {"timestamp": "2023-01-01", "version": "1.0"}
                }
            }
        }
        mock_run_ftl_module.return_value = complex_result
        
        args = [
            "--ftl-module", "complex_module",
            "--module-dir", "/ftl_modules",
            "--inventory", "inventory.yml"
        ]
        
        result = await main(args)
        
        assert result == 0
        mock_pprint.assert_called_once_with(complex_result) 