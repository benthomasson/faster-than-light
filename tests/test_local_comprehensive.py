"""
Comprehensive unit tests for faster_than_light.local module.

Tests all local execution functionality including subprocess execution,
module type detection, file operations, JSON handling, and error scenarios.
"""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, call, mock_open, patch

import pytest

from faster_than_light.local import (check_output, is_binary_module,
                                     is_new_style_module, is_want_json_module,
                                     run_ftl_module_locally,
                                     run_module_locally)

# runpy doesn't have a specific RunPathError, it raises standard exceptions



class TestCheckOutput:
    """Tests for check_output function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.asyncio.create_subprocess_shell')
    async def test_check_output_basic_command(self, mock_create_subprocess):
        """Test basic command execution with stdout."""
        # Setup mock process
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Hello World", None))
        mock_create_subprocess.return_value = mock_process
        
        result = await check_output("echo 'Hello World'")
        
        assert result == b"Hello World"
        mock_create_subprocess.assert_called_once_with(
            "echo 'Hello World'",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        mock_process.communicate.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.asyncio.create_subprocess_shell')
    async def test_check_output_with_stdin(self, mock_create_subprocess):
        """Test command execution with stdin input."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Processed input", None))
        mock_create_subprocess.return_value = mock_process
        
        stdin_data = b"test input data"
        result = await check_output("cat", stdin=stdin_data)
        
        assert result == b"Processed input"
        mock_process.communicate.assert_called_once_with(stdin_data)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.asyncio.create_subprocess_shell')
    async def test_check_output_empty_result(self, mock_create_subprocess):
        """Test command execution with empty output."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", None))
        mock_create_subprocess.return_value = mock_process
        
        result = await check_output("true")
        
        assert result == b""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.asyncio.create_subprocess_shell')
    async def test_check_output_complex_command(self, mock_create_subprocess):
        """Test complex command with pipes and arguments."""
        mock_process = MagicMock()
        expected_output = b"line1\nline2\nline3"
        mock_process.communicate = AsyncMock(return_value=(expected_output, None))
        mock_create_subprocess.return_value = mock_process
        
        result = await check_output("ls -la | grep test | head -3")
        
        assert result == expected_output
        mock_create_subprocess.assert_called_once_with(
            "ls -la | grep test | head -3",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )


class TestIsBinaryModule:
    """Tests for is_binary_module function."""
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_binary_module_text_file(self, mock_file):
        """Test with regular text Python module."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "import sys\n",
            "print('Hello World')\n"
        ]
        
        result = is_binary_module("/path/to/text_module.py")
        
        assert result is False
        mock_file.assert_called_once_with("/path/to/text_module.py")
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_binary_module_binary_file(self, mock_file):
        """Test with binary file that raises UnicodeDecodeError."""
        mock_file.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid start byte")
        
        result = is_binary_module("/path/to/binary_module")
        
        assert result is True
        mock_file.assert_called_once_with("/path/to/binary_module")
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_binary_module_empty_file(self, mock_file):
        """Test with empty text file."""
        mock_file.return_value.readlines.return_value = []
        
        result = is_binary_module("/path/to/empty_module.py")
        
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_binary_module_single_line(self, mock_file):
        """Test with single line text file."""
        mock_file.return_value.readlines.return_value = ["print('single line')"]
        
        result = is_binary_module("/path/to/single_line.py")
        
        assert result is False
    
    @patch('builtins.open')
    def test_is_binary_module_file_not_found(self, mock_file):
        """Test with file that doesn't exist."""
        mock_file.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            is_binary_module("/path/to/nonexistent.py")


class TestIsNewStyleModule:
    """Tests for is_new_style_module function."""
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_new_style_module_ansible_module_present(self, mock_file):
        """Test with module containing AnsibleModule."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "from ansible.module_utils.basic import AnsibleModule\n",
            "def main():\n",
            "    module = AnsibleModule(\n",
            "        argument_spec=dict()\n",
            "    )\n"
        ]
        
        result = is_new_style_module("/path/to/new_style.py")
        
        assert result is True
        mock_file.assert_called_once_with("/path/to/new_style.py")
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_new_style_module_no_ansible_module(self, mock_file):
        """Test with module not containing AnsibleModule."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "import sys\n",
            "print('Old style module')\n"
        ]
        
        result = is_new_style_module("/path/to/old_style.py")
        
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_new_style_module_ansible_module_in_comment(self, mock_file):
        """Test with AnsibleModule in comment."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "# This module uses AnsibleModule() for argument parsing\n",
            "import sys\n"
        ]
        
        result = is_new_style_module("/path/to/commented.py")
        
        assert result is True  # Current implementation doesn't distinguish comments
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_new_style_module_partial_match(self, mock_file):
        """Test with partial AnsibleModule string."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "# AnsibleModuleHelper is not the same\n",
            "import ansible_module_utils\n"
        ]
        
        result = is_new_style_module("/path/to/partial.py")
        
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_new_style_module_empty_file(self, mock_file):
        """Test with empty file."""
        mock_file.return_value.readlines.return_value = []
        
        result = is_new_style_module("/path/to/empty.py")
        
        assert result is False


class TestIsWantJsonModule:
    """Tests for is_want_json_module function."""
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_want_json_module_want_json_present(self, mock_file):
        """Test with module containing WANT_JSON."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "WANT_JSON = True\n",
            "import json\n",
            "import sys\n"
        ]
        
        result = is_want_json_module("/path/to/want_json.py")
        
        assert result is True
        mock_file.assert_called_once_with("/path/to/want_json.py")
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_want_json_module_no_want_json(self, mock_file):
        """Test with module not containing WANT_JSON."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "import sys\n",
            "print('No JSON wanted')\n"
        ]
        
        result = is_want_json_module("/path/to/no_json.py")
        
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_want_json_module_want_json_in_string(self, mock_file):
        """Test with WANT_JSON in string literal."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            'print("This module supports WANT_JSON format")\n',
            "import sys\n"
        ]
        
        result = is_want_json_module("/path/to/string_match.py")
        
        assert result is True  # Current implementation matches anywhere in line
    
    @patch('builtins.open', new_callable=mock_open)
    def test_is_want_json_module_want_json_commented(self, mock_file):
        """Test with WANT_JSON in comment."""
        mock_file.return_value.readlines.return_value = [
            "#!/usr/bin/env python3\n",
            "# WANT_JSON = True  # Commented out\n",
            "import sys\n"
        ]
        
        result = is_want_json_module("/path/to/commented_json.py")
        
        assert result is True  # Current implementation doesn't distinguish comments


class TestRunModuleLocally:
    """Tests for run_module_locally function."""
    
    def setup_method(self):
        """Set up common test data."""
        self.host_name = "test_host"
        self.host = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.module_args = {"state": "present", "name": "test"}
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_binary_module(self, mock_file, mock_check_output,
                                                  mock_is_binary, mock_copy, mock_mkdtemp):
        """Test running binary module."""
        mock_mkdtemp.return_value = "/tmp/test123"
        mock_is_binary.return_value = True
        mock_check_output.return_value = b'{"changed": true, "msg": "success"}'
        
        result = await run_module_locally(
            self.host_name, self.host, "/path/to/binary_module", self.module_args
        )
        
        assert result == ("test_host", {"changed": True, "msg": "success"})
        mock_copy.assert_called_once_with("/path/to/binary_module", "/tmp/test123/module.py")
        mock_file.assert_called_once_with("/tmp/test123/args", "w")
        mock_file.return_value.write.assert_called_once_with(json.dumps(self.module_args))
        mock_check_output.assert_called_once_with("/tmp/test123/module.py /tmp/test123/args")
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.is_new_style_module')
    @patch('faster_than_light.local.check_output')
    async def test_run_module_locally_new_style_module(self, mock_check_output, mock_is_new_style,
                                                     mock_is_binary, mock_copy, mock_mkdtemp):
        """Test running new-style Ansible module."""
        mock_mkdtemp.return_value = "/tmp/test456"
        mock_is_binary.return_value = False
        mock_is_new_style.return_value = True
        mock_check_output.return_value = b'{"changed": false, "msg": "already present"}'
        
        with patch('builtins.print'):  # Mock print statements
            result = await run_module_locally(
                self.host_name, self.host, "/path/to/new_style.py", self.module_args
            )
        
        assert result == ("test_host", {"changed": False, "msg": "already present"})
        expected_stdin = json.dumps(dict(ANSIBLE_MODULE_ARGS=self.module_args)).encode()
        mock_check_output.assert_called_once_with(
            "/usr/bin/python3 /tmp/test456/module.py",
            stdin=expected_stdin
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.is_new_style_module')
    @patch('faster_than_light.local.is_want_json_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_want_json_module(self, mock_file, mock_check_output,
                                                     mock_is_want_json, mock_is_new_style,
                                                     mock_is_binary, mock_copy, mock_mkdtemp):
        """Test running WANT_JSON module."""
        mock_mkdtemp.return_value = "/tmp/test789"
        mock_is_binary.return_value = False
        mock_is_new_style.return_value = False
        mock_is_want_json.return_value = True
        mock_check_output.return_value = b'{"changed": true, "result": "json processed"}'
        
        result = await run_module_locally(
            self.host_name, self.host, "/path/to/want_json.py", self.module_args
        )
        
        assert result == ("test_host", {"changed": True, "result": "json processed"})
        mock_file.assert_called_once_with("/tmp/test789/args", "w")
        mock_file.return_value.write.assert_called_once_with(json.dumps(self.module_args))
        mock_check_output.assert_called_once_with(
            "/usr/bin/python3 /tmp/test789/module.py /tmp/test789/args"
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.is_new_style_module')
    @patch('faster_than_light.local.is_want_json_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_old_style_module(self, mock_file, mock_check_output,
                                                     mock_is_want_json, mock_is_new_style,
                                                     mock_is_binary, mock_copy, mock_mkdtemp):
        """Test running old-style module."""
        mock_mkdtemp.return_value = "/tmp/test_old"
        mock_is_binary.return_value = False
        mock_is_new_style.return_value = False
        mock_is_want_json.return_value = False
        mock_check_output.return_value = b'{"msg": "old style success"}'
        
        result = await run_module_locally(
            self.host_name, self.host, "/path/to/old_style.py", self.module_args
        )
        
        assert result == ("test_host", {"msg": "old style success"})
        mock_file.assert_called_once_with("/tmp/test_old/args", "w")
        # Old style uses key=value format
        expected_args = "state=present name=test"
        mock_file.return_value.write.assert_called_once_with(expected_args)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.is_new_style_module')
    @patch('faster_than_light.local.is_want_json_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_old_style_none_args(self, mock_file, mock_check_output,
                                                        mock_is_want_json, mock_is_new_style,
                                                        mock_is_binary, mock_copy, mock_mkdtemp):
        """Test running old-style module with None args."""
        mock_mkdtemp.return_value = "/tmp/test_none"
        mock_is_binary.return_value = False
        mock_is_new_style.return_value = False
        mock_is_want_json.return_value = False
        mock_check_output.return_value = b'{"msg": "no args"}'
        
        result = await run_module_locally(
            self.host_name, self.host, "/path/to/old_style.py", None
        )
        
        assert result == ("test_host", {"msg": "no args"})
        mock_file.return_value.write.assert_called_once_with("")
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_default_interpreter(self, mock_file, mock_check_output,
                                                        mock_is_binary, mock_copy, mock_mkdtemp):
        """Test with host missing ansible_python_interpreter."""
        mock_mkdtemp.return_value = "/tmp/test_default"
        mock_is_binary.return_value = True
        mock_check_output.return_value = b'{"result": "default interpreter"}'
        
        host_no_interpreter = {}  # No ansible_python_interpreter
        
        result = await run_module_locally(
            self.host_name, host_no_interpreter, "/path/to/module", self.module_args
        )
        
        assert result == ("test_host", {"result": "default interpreter"})
        # Should use sys.executable as default
        expected_cmd = f"/tmp/test_default/module.py /tmp/test_default/args"
        mock_check_output.assert_called_once_with(expected_cmd)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_invalid_json_output(self, mock_file, mock_check_output,
                                                        mock_is_binary, mock_copy, mock_mkdtemp):
        """Test with invalid JSON output from module."""
        mock_mkdtemp.return_value = "/tmp/test_invalid"
        mock_is_binary.return_value = True
        mock_check_output.return_value = b'Invalid JSON output {broken'
        
        with patch('builtins.print'):  # Mock print for error output
            result = await run_module_locally(
                self.host_name, self.host, "/path/to/module", self.module_args
            )
        
        assert result == ("test_host", {"error": b'Invalid JSON output {broken'})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.check_output')
    @patch('faster_than_light.local.traceback.print_exc')
    @patch('builtins.open', new_callable=mock_open)
    async def test_run_module_locally_exception_handling(self, mock_file, mock_print_exc, 
                                                       mock_check_output, mock_is_binary, 
                                                       mock_copy, mock_mkdtemp):
        """Test exception handling and re-raising."""
        mock_mkdtemp.return_value = "/tmp/test_exception"
        mock_is_binary.return_value = True
        mock_check_output.side_effect = Exception("Command failed")
        
        with pytest.raises(Exception, match="Command failed"):
            await run_module_locally(
                self.host_name, self.host, "/path/to/module", self.module_args
            )
        
        mock_print_exc.assert_called_once()


class TestRunFtlModuleLocally:
    """Tests for run_ftl_module_locally function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_basic(self, mock_run_path):
        """Test basic FTL module execution."""
        # Mock module with async main function
        mock_main = AsyncMock(return_value={"result": "success", "changed": True})
        mock_run_path.return_value = {"main": mock_main}
        
        host_name = "ftl_host"
        host = {"type": "local"}
        module_path = "/path/to/ftl_module.py"
        module_args = {"param1": "value1", "param2": "value2"}
        
        result = await run_ftl_module_locally(host_name, host, module_path, module_args)
        
        assert result == ("ftl_host", {"result": "success", "changed": True})
        mock_run_path.assert_called_once_with(module_path)
        mock_main.assert_called_once_with(param1="value1", param2="value2")
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_none_args(self, mock_run_path):
        """Test FTL module execution with None args."""
        mock_main = AsyncMock(return_value={"status": "no args provided"})
        mock_run_path.return_value = {"main": mock_main}
        
        result = await run_ftl_module_locally("host", {}, "/path/to/module.py", None)
        
        assert result == ("host", {"status": "no args provided"})
        mock_main.assert_called_once_with()  # No keyword arguments
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_empty_args(self, mock_run_path):
        """Test FTL module execution with empty args dict."""
        mock_main = AsyncMock(return_value={"result": "empty args"})
        mock_run_path.return_value = {"main": mock_main}
        
        result = await run_ftl_module_locally("host", {}, "/path/to/module.py", {})
        
        assert result == ("host", {"result": "empty args"})
        mock_main.assert_called_once_with()
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_complex_args(self, mock_run_path):
        """Test FTL module execution with complex arguments."""
        mock_main = AsyncMock(return_value={"processed": "complex data"})
        mock_run_path.return_value = {"main": mock_main}
        
        complex_args = {
            "string_param": "test",
            "int_param": 42,
            "bool_param": True,
            "list_param": [1, 2, 3],
            "dict_param": {"nested": "value"}
        }
        
        result = await run_ftl_module_locally("host", {}, "/path/to/module.py", complex_args)
        
        assert result == ("host", {"processed": "complex data"})
        mock_main.assert_called_once_with(
            string_param="test",
            int_param=42,
            bool_param=True,
            list_param=[1, 2, 3],
            dict_param={"nested": "value"}
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_module_loading_error(self, mock_run_path):
        """Test error handling when module can't be loaded."""
        mock_run_path.side_effect = FileNotFoundError("Module not found")
        
        with pytest.raises(FileNotFoundError):
            await run_ftl_module_locally("host", {}, "/nonexistent/module.py", {})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_no_main_function(self, mock_run_path):
        """Test error handling when module has no main function."""
        mock_run_path.return_value = {"other_function": lambda: None}
        
        with pytest.raises(KeyError):
            await run_ftl_module_locally("host", {}, "/path/to/no_main.py", {})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_main_execution_error(self, mock_run_path):
        """Test error handling when main function raises exception."""
        mock_main = AsyncMock(side_effect=ValueError("Invalid parameter"))
        mock_run_path.return_value = {"main": mock_main}
        
        with pytest.raises(ValueError, match="Invalid parameter"):
            await run_ftl_module_locally("host", {}, "/path/to/failing.py", {"bad_param": "value"})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_syntax_error(self, mock_run_path):
        """Test error handling for syntax errors in module."""
        mock_run_path.side_effect = SyntaxError("Invalid syntax in module")
        
        with pytest.raises(SyntaxError):
            await run_ftl_module_locally("host", {}, "/path/to/broken.py", {})


class TestLocalIntegration:
    """Integration tests for local module functionality."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    @patch('faster_than_light.local.shutil.copy')
    @patch('faster_than_light.local.is_binary_module')
    @patch('faster_than_light.local.is_new_style_module')
    @patch('faster_than_light.local.is_want_json_module')
    @patch('faster_than_light.local.check_output')
    @patch('builtins.open', new_callable=mock_open)
    async def test_module_type_detection_workflow(self, mock_file, mock_check_output,
                                                mock_is_want_json, mock_is_new_style,
                                                mock_is_binary, mock_copy, mock_mkdtemp):
        """Test the module type detection workflow."""
        mock_mkdtemp.return_value = "/tmp/workflow_test"
        
        # Test cases for different module types
        test_cases = [
            # (is_binary, is_new_style, is_want_json, expected_behavior)
            (True, False, False, "binary"),
            (False, True, False, "new_style"),
            (False, False, True, "want_json"),
            (False, False, False, "old_style"),
        ]
        
        for is_binary, is_new, is_want, expected in test_cases:
            mock_is_binary.return_value = is_binary
            mock_is_new_style.return_value = is_new
            mock_is_want_json.return_value = is_want
            mock_check_output.return_value = b'{"type": "' + expected.encode() + b'"}'
            
            with patch('builtins.print'):  # Mock print for new_style
                result = await run_module_locally(
                    "test_host", 
                    {"ansible_python_interpreter": "/usr/bin/python3"},
                    f"/path/to/{expected}_module.py",
                    {"test": "param"}
                )
            
            assert result[0] == "test_host"
            assert result[1]["type"] == expected


class TestLocalEdgeCases:
    """Tests for edge cases and error scenarios."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.asyncio.create_subprocess_shell')
    async def test_check_output_process_error(self, mock_create_subprocess):
        """Test check_output with process that raises exception."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=OSError("Process error"))
        mock_create_subprocess.return_value = mock_process
        
        with pytest.raises(OSError):
            await check_output("failing_command")
    
    @patch('builtins.open')
    def test_module_detection_with_file_errors(self, mock_file):
        """Test module detection functions with file access errors."""
        mock_file.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(PermissionError):
            is_binary_module("/restricted/module.py")
        
        with pytest.raises(PermissionError):
            is_new_style_module("/restricted/module.py")
        
        with pytest.raises(PermissionError):
            is_want_json_module("/restricted/module.py")
    
    @patch('builtins.open', new_callable=mock_open)
    def test_module_detection_with_large_files(self, mock_file):
        """Test module detection with very large files."""
        # Simulate large file with many lines
        large_content = ["line " + str(i) + "\n" for i in range(10000)]
        large_content[5000] = "AnsibleModule(\n"  # Embedded in middle
        
        mock_file.return_value.readlines.return_value = large_content
        
        result = is_new_style_module("/path/to/large_module.py")
        assert result is True
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.tempfile.mkdtemp')
    async def test_run_module_locally_temp_dir_creation_failure(self, mock_mkdtemp):
        """Test error handling when temp directory creation fails."""
        mock_mkdtemp.side_effect = OSError("Cannot create temp directory")
        
        with pytest.raises(OSError):
            await run_module_locally("host", {}, "/path/to/module.py", {})
    
    @pytest.mark.asyncio
    @patch('faster_than_light.local.runpy.run_path')
    async def test_run_ftl_module_locally_unicode_args(self, mock_run_path):
        """Test FTL module with Unicode arguments."""
        mock_main = AsyncMock(return_value={"unicode": "processed"})
        mock_run_path.return_value = {"main": mock_main}
        
        unicode_args = {
            "message": "Hello 世界",
            "emoji": "🚀🌟",
            "path": "/路径/文件.txt"
        }
        
        result = await run_ftl_module_locally("host", {}, "/path/to/module.py", unicode_args)
        
        assert result == ("host", {"unicode": "processed"})
        mock_main.assert_called_once_with(
            message="Hello 世界",
            emoji="🚀🌟",
            path="/路径/文件.txt"
        ) 