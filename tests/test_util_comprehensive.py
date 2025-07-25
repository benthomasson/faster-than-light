"""
Comprehensive unit tests for faster_than_light.util module.

Tests all utility functions with various edge cases, error conditions,
and proper mocking of file system operations.
"""

import json
import os
import pytest
import tempfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

from faster_than_light.util import (
    ensure_directory,
    chunk,
    find_module,
    read_module,
    clean_up_ftl_cache,
    clean_up_tmp,
    process_module_result,
    unique_hosts,
)
from faster_than_light.exceptions import ModuleNotFound


class TestEnsureDirectory:
    """Tests for ensure_directory function."""
    
    def test_ensure_directory_exists(self, tmp_path):
        """Test that existing directory is returned unchanged."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        
        result = ensure_directory(str(existing_dir))
        
        assert result == str(existing_dir.resolve())
        assert existing_dir.exists()
    
    def test_ensure_directory_creates_new(self, tmp_path):
        """Test that new directory is created."""
        new_dir = tmp_path / "new_directory"
        
        result = ensure_directory(str(new_dir))
        
        assert result == str(new_dir.resolve())
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_ensure_directory_creates_nested(self, tmp_path):
        """Test that nested directories are created."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        
        result = ensure_directory(str(nested_dir))
        
        assert result == str(nested_dir.resolve())
        assert nested_dir.exists()
        assert nested_dir.is_dir()
    
    def test_ensure_directory_expands_user(self):
        """Test that ~ is expanded to user home directory."""
        with patch('os.path.expanduser') as mock_expanduser, \
             patch('os.path.abspath') as mock_abspath, \
             patch('os.path.exists') as mock_exists, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_expanduser.return_value = "/home/user/test"
            mock_abspath.return_value = "/home/user/test"
            mock_exists.return_value = True
            
            result = ensure_directory("~/test")
            
            mock_expanduser.assert_called_once_with("~/test")
            mock_abspath.assert_called_once_with("/home/user/test")
            assert result == "/home/user/test"
    
    def test_ensure_directory_handles_permissions_error(self, tmp_path):
        """Test handling of permission errors when creating directory."""
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                ensure_directory(str(tmp_path / "forbidden"))


class TestChunk:
    """Tests for chunk function."""
    
    def test_chunk_empty_list(self):
        """Test chunking empty list."""
        result = list(chunk([], 3))
        assert result == []
    
    def test_chunk_single_element(self):
        """Test chunking list with single element."""
        result = list(chunk([1], 3))
        assert result == [[1]]
    
    def test_chunk_exact_division(self):
        """Test chunking list that divides evenly."""
        result = list(chunk([1, 2, 3, 4, 5, 6], 3))
        assert result == [[1, 2, 3], [4, 5, 6]]
    
    def test_chunk_partial_last_chunk(self):
        """Test chunking list with partial last chunk."""
        result = list(chunk([1, 2, 3, 4, 5], 3))
        assert result == [[1, 2, 3], [4, 5]]
    
    def test_chunk_size_larger_than_list(self):
        """Test chunking with chunk size larger than list."""
        result = list(chunk([1, 2, 3], 10))
        assert result == [[1, 2, 3]]
    
    def test_chunk_size_one(self):
        """Test chunking with size 1."""
        result = list(chunk([1, 2, 3], 1))
        assert result == [[1], [2], [3]]
    
    def test_chunk_different_types(self):
        """Test chunking list with different data types."""
        mixed_list = ["a", 1, None, {"key": "value"}]
        result = list(chunk(mixed_list, 2))
        assert result == [["a", 1], [None, {"key": "value"}]]


class TestFindModule:
    """Tests for find_module function."""
    
    def test_find_python_module(self, tmp_path):
        """Test finding Python module file."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        python_module = module_dir / "test_module.py"
        python_module.write_text("# test module")
        
        result = find_module([str(module_dir)], "test_module")
        
        assert result == str(python_module)
    
    def test_find_binary_module(self, tmp_path):
        """Test finding binary module file."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        binary_module = module_dir / "test_binary"
        binary_module.write_bytes(b"binary content")
        
        result = find_module([str(module_dir)], "test_binary")
        
        assert result == str(binary_module)
    
    def test_find_module_multiple_dirs(self, tmp_path):
        """Test finding module in multiple directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        # Module only exists in second directory
        module = dir2 / "test_module.py"
        module.write_text("# test module")
        
        result = find_module([str(dir1), str(dir2)], "test_module")
        
        assert result == str(module)
    
    def test_find_module_python_takes_precedence(self, tmp_path):
        """Test that Python module takes precedence over binary."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        
        python_module = module_dir / "test_module.py"
        python_module.write_text("# python module")
        
        binary_module = module_dir / "test_module"
        binary_module.write_bytes(b"binary content")
        
        result = find_module([str(module_dir)], "test_module")
        
        assert result == str(python_module)
    
    def test_find_module_not_found(self, tmp_path):
        """Test module not found returns None."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        
        result = find_module([str(module_dir)], "nonexistent_module")
        
        assert result is None
    
    def test_find_module_empty_dirs(self):
        """Test with empty module directories list."""
        result = find_module([], "test_module")
        assert result is None
    
    def test_find_module_none_dirs(self):
        """Test with None values in module directories."""
        result = find_module([None, "", None], "test_module")
        assert result is None
    
    def test_find_module_nonexistent_dir(self):
        """Test with nonexistent directory."""
        result = find_module(["/nonexistent/path"], "test_module")
        assert result is None


class TestReadModule:
    """Tests for read_module function."""
    
    def test_read_python_module(self, tmp_path):
        """Test reading Python module content."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        module_file = module_dir / "test_module.py"
        content = "#!/usr/bin/python3\nprint('hello')"
        module_file.write_text(content)
        
        result = read_module([str(module_dir)], "test_module")
        
        assert result == content.encode()
    
    def test_read_binary_module(self, tmp_path):
        """Test reading binary module content."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        module_file = module_dir / "test_binary"
        content = b"\x00\x01\x02\x03binary content"
        module_file.write_bytes(content)
        
        result = read_module([str(module_dir)], "test_binary")
        
        assert result == content
    
    def test_read_module_not_found(self, tmp_path):
        """Test reading nonexistent module raises ModuleNotFound."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        
        with pytest.raises(ModuleNotFound) as exc_info:
            read_module([str(module_dir)], "nonexistent")
        
        assert "Cannot find nonexistent" in str(exc_info.value)
        assert str(module_dir) in str(exc_info.value)
    
    def test_read_module_permission_error(self, tmp_path):
        """Test handling permission error when reading module."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        module_file = module_dir / "test_module.py"
        module_file.write_text("content")
        
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                read_module([str(module_dir)], "test_module")


class TestCleanUpFtlCache:
    """Tests for clean_up_ftl_cache function."""
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('os.path.isdir')
    @patch('os.path.expanduser')
    @patch('os.path.abspath')
    def test_clean_up_existing_cache(self, mock_abspath, mock_expanduser, 
                                   mock_isdir, mock_exists, mock_rmtree):
        """Test cleaning up existing cache directory."""
        cache_path = "/home/user/.ftl"
        mock_expanduser.return_value = cache_path
        mock_abspath.return_value = cache_path
        mock_exists.return_value = True
        mock_isdir.return_value = True
        
        clean_up_ftl_cache()
        
        mock_expanduser.assert_called_once_with("~/.ftl")
        mock_abspath.assert_called_once_with(cache_path)
        mock_exists.assert_called_once_with(cache_path)
        mock_isdir.assert_called_once_with(cache_path)
        mock_rmtree.assert_called_once_with(cache_path)
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('os.path.expanduser')
    @patch('os.path.abspath')
    def test_clean_up_nonexistent_cache(self, mock_abspath, mock_expanduser, 
                                      mock_exists, mock_rmtree):
        """Test cleaning up when cache doesn't exist."""
        cache_path = "/home/user/.ftl"
        mock_expanduser.return_value = cache_path
        mock_abspath.return_value = cache_path
        mock_exists.return_value = False
        
        clean_up_ftl_cache()
        
        mock_rmtree.assert_not_called()
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('os.path.isdir')
    @patch('os.path.expanduser')
    @patch('os.path.abspath')
    def test_clean_up_cache_is_file(self, mock_abspath, mock_expanduser, 
                                  mock_isdir, mock_exists, mock_rmtree):
        """Test when .ftl exists but is not a directory."""
        cache_path = "/home/user/.ftl"
        mock_expanduser.return_value = cache_path
        mock_abspath.return_value = cache_path
        mock_exists.return_value = True
        mock_isdir.return_value = False
        
        clean_up_ftl_cache()
        
        mock_rmtree.assert_not_called()


class TestCleanUpTmp:
    """Tests for clean_up_tmp function."""
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('os.path.isdir')
    @patch('glob.glob')
    def test_clean_up_multiple_tmp_dirs(self, mock_glob, mock_isdir, 
                                      mock_exists, mock_rmtree):
        """Test cleaning up multiple temporary directories."""
        tmp_dirs = ["/tmp/ftl-123", "/tmp/ftl-456", "/tmp/ftl-789"]
        mock_glob.return_value = tmp_dirs
        mock_exists.return_value = True
        mock_isdir.return_value = True
        
        clean_up_tmp()
        
        mock_glob.assert_called_once_with("/tmp/ftl-*")
        assert mock_rmtree.call_count == 3
        for tmp_dir in tmp_dirs:
            mock_rmtree.assert_any_call(tmp_dir)
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('glob.glob')
    def test_clean_up_nonexistent_tmp_dirs(self, mock_glob, mock_exists, mock_rmtree):
        """Test when no tmp directories exist."""
        mock_glob.return_value = []
        
        clean_up_tmp()
        
        mock_rmtree.assert_not_called()
    
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    @patch('os.path.isdir')
    @patch('glob.glob')
    def test_clean_up_tmp_safety_check(self, mock_glob, mock_isdir, 
                                     mock_exists, mock_rmtree):
        """Test safety checks prevent removing directories that don't meet all criteria."""
        # Directory that would match glob but fails isdir check
        mock_glob.return_value = ["/tmp/ftl-file"]
        mock_exists.return_value = True
        mock_isdir.return_value = False  # Not a directory
        
        clean_up_tmp()
        
        mock_rmtree.assert_not_called()


class TestProcessModuleResult:
    """Tests for process_module_result function."""
    
    def test_process_module_result_success(self):
        """Test processing successful module result."""
        result_data = {"key": "value", "status": "success"}
        message = ["ModuleResult", {"stdout": json.dumps(result_data)}]
        
        result = process_module_result(message)
        
        assert result == result_data
    
    def test_process_module_result_error(self):
        """Test processing module result with error."""
        message = ["ModuleResult", {"stderr": "Error occurred"}]
        
        result = process_module_result(message)
        
        assert result == {"error": {"message": "Error occurred"}}
    
    def test_process_ftl_module_result(self):
        """Test processing FTL module result."""
        result_data = {"key": "value"}
        message = ["FTLModuleResult", {"result": result_data}]
        
        result = process_module_result(message)
        
        assert result == result_data
    
    def test_process_gate_system_error(self):
        """Test processing gate system error."""
        message = ["GateSystemError", "Connection failed"]
        
        result = process_module_result(message)
        
        expected = {
            "error": {
                "error_type": "GateSystemError",
                "message": "Connection failed"
            }
        }
        assert result == expected
    
    def test_process_module_not_found(self):
        """Test processing module not found error."""
        message = ["ModuleNotFound", {"message": "Module xyz not found"}]
        
        with pytest.raises(ModuleNotFound) as exc_info:
            process_module_result(message)
        
        assert "Module xyz not found" in str(exc_info.value)
    
    def test_process_unsupported_message_type(self):
        """Test processing unsupported message type."""
        message = ["UnknownType", {"data": "some data"}]
        
        with pytest.raises(Exception) as exc_info:
            process_module_result(message)
        
        assert "Unsupported message type UnknownType" in str(exc_info.value)
    
    def test_process_null_message(self):
        """Test processing null message."""
        with pytest.raises(Exception) as exc_info:
            process_module_result(None)
        
        assert "Null message" in str(exc_info.value)
    
    def test_process_empty_message(self):
        """Test processing empty message."""
        with pytest.raises(Exception) as exc_info:
            process_module_result([])
        
        assert "Empty message" in str(exc_info.value)
    
    def test_process_module_result_invalid_json(self):
        """Test processing module result with invalid JSON."""
        message = ["ModuleResult", {"stdout": "invalid json {"}]
        
        with pytest.raises(json.JSONDecodeError):
            process_module_result(message)


class TestUniqueHosts:
    """Tests for unique_hosts function."""
    
    def test_unique_hosts_single_group(self):
        """Test extracting hosts from single group."""
        inventory = {
            "webservers": {
                "hosts": {
                    "web1": {"ansible_host": "192.168.1.10"},
                    "web2": {"ansible_host": "192.168.1.11"}
                }
            }
        }
        
        result = unique_hosts(inventory)
        
        expected = {
            "web1": {"ansible_host": "192.168.1.10"},
            "web2": {"ansible_host": "192.168.1.11"}
        }
        assert result == expected
    
    def test_unique_hosts_multiple_groups(self):
        """Test extracting hosts from multiple groups."""
        inventory = {
            "webservers": {
                "hosts": {
                    "web1": {"ansible_host": "192.168.1.10"}
                }
            },
            "databases": {
                "hosts": {
                    "db1": {"ansible_host": "192.168.1.20"}
                }
            }
        }
        
        result = unique_hosts(inventory)
        
        expected = {
            "web1": {"ansible_host": "192.168.1.10"},
            "db1": {"ansible_host": "192.168.1.20"}
        }
        assert result == expected
    
    def test_unique_hosts_duplicate_hosts(self):
        """Test that duplicate hosts are overwritten by last occurrence."""
        inventory = {
            "group1": {
                "hosts": {
                    "server1": {"ansible_host": "192.168.1.10"}
                }
            },
            "group2": {
                "hosts": {
                    "server1": {"ansible_host": "192.168.1.11"}  # Different IP
                }
            }
        }
        
        result = unique_hosts(inventory)
        
        # Should contain the last occurrence
        expected = {
            "server1": {"ansible_host": "192.168.1.11"}
        }
        assert result == expected
    
    def test_unique_hosts_empty_inventory(self):
        """Test with empty inventory."""
        inventory = {}
        
        result = unique_hosts(inventory)
        
        assert result == {}
    
    def test_unique_hosts_no_hosts_in_group(self):
        """Test with group that has no hosts."""
        inventory = {
            "empty_group": {
                "hosts": {}
            }
        }
        
        result = unique_hosts(inventory)
        
        assert result == {}
    
    def test_unique_hosts_complex_inventory(self):
        """Test with complex inventory structure."""
        inventory = {
            "webservers": {
                "hosts": {
                    "web1": {
                        "ansible_host": "192.168.1.10",
                        "ansible_user": "admin",
                        "http_port": 80
                    },
                    "web2": {
                        "ansible_host": "192.168.1.11", 
                        "ansible_user": "admin",
                        "http_port": 8080
                    }
                }
            },
            "databases": {
                "hosts": {
                    "db1": {
                        "ansible_host": "192.168.1.20",
                        "ansible_user": "dbadmin",
                        "mysql_port": 3306
                    }
                }
            }
        }
        
        result = unique_hosts(inventory)
        
        expected = {
            "web1": {
                "ansible_host": "192.168.1.10",
                "ansible_user": "admin", 
                "http_port": 80
            },
            "web2": {
                "ansible_host": "192.168.1.11",
                "ansible_user": "admin",
                "http_port": 8080
            },
            "db1": {
                "ansible_host": "192.168.1.20",
                "ansible_user": "dbadmin",
                "mysql_port": 3306
            }
        }
        assert result == expected


# Integration tests
class TestUtilIntegration:
    """Integration tests combining multiple utility functions."""
    
    def test_find_and_read_module_integration(self, tmp_path):
        """Test finding and reading a module together."""
        module_dir = tmp_path / "modules"
        module_dir.mkdir()
        
        module_content = "#!/usr/bin/python3\nprint('integration test')"
        module_file = module_dir / "integration_test.py"
        module_file.write_text(module_content)
        
        # Find the module
        found_path = find_module([str(module_dir)], "integration_test")
        assert found_path is not None
        
        # Read the module
        content = read_module([str(module_dir)], "integration_test")
        assert content == module_content.encode()
    
    def test_ensure_directory_and_cleanup(self, tmp_path):
        """Test creating directory and cleaning up."""
        test_dir = tmp_path / "test_cleanup"
        
        # Create directory
        result = ensure_directory(str(test_dir))
        assert os.path.exists(result)
        
        # Clean up manually for this test
        shutil.rmtree(result)
        assert not os.path.exists(result) 