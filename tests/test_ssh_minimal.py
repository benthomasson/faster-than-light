"""
Minimal unit tests for faster_than_light.ssh module.

Tests core SSH functionality with proper async mocking.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from faster_than_light.ssh import (
    check_version,
    mkdir,
    mkdir_sync,
    copy,
    copy_sync,
    template,
    template_sync,
    copy_from,
    copy_from_sync,
    send_gate,
    open_gate,
    remove_item_from_cache,
    close_gate,
    run_module_through_gate,
    run_ftl_module_through_gate,
)
from faster_than_light.types import Gate
from faster_than_light.exceptions import ModuleNotFound


class TestCheckVersion:
    """Tests for check_version function."""
    
    @pytest.mark.asyncio
    async def test_check_version_python3_success(self):
        """Test successful Python 3 version check."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.stdout = "Python 3.9.5"
        mock_conn.run = AsyncMock(return_value=mock_result)
        
        # Should not raise exception
        await check_version(mock_conn, "/usr/bin/python3")
        
        mock_conn.run.assert_called_once_with("/usr/bin/python3 --version")
    
    @pytest.mark.asyncio
    async def test_check_version_python2_failure(self):
        """Test failure with Python 2."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.stdout = "Python 2.7.18"
        mock_conn.run = AsyncMock(return_value=mock_result)
        
        with pytest.raises(Exception, match="Python 3 or greater required"):
            await check_version(mock_conn, "/usr/bin/python2")
    
    @pytest.mark.asyncio
    async def test_check_version_unexpected_output(self):
        """Test failure with unexpected output."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.stdout = "Welcome to shell\nPython 3.9.5"
        mock_conn.run = AsyncMock(return_value=mock_result)
        
        with pytest.raises(Exception, match="Ensure that non-interactive shells emit no text"):
            await check_version(mock_conn, "/usr/bin/python3")


class TestMkdir:
    """Tests for mkdir function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    @patch('faster_than_light.ssh.connect_ssh')
    async def test_mkdir_without_cache(self, mock_connect_ssh, mock_unique_hosts):
        """Test mkdir without cached connections."""
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"}
        }
        
        # Create mock connection with SFTP
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        mock_connect_ssh.return_value = mock_conn
        
        inventory = {"hosts": {"host1": {}}}
        
        await mkdir(inventory, None, "/tmp/test_dir")
        
        mock_connect_ssh.assert_called_once()
        mock_sftp.makedirs.assert_called_once_with("/tmp/test_dir", exist_ok=True)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    async def test_mkdir_with_cache(self, mock_unique_hosts):
        """Test mkdir using cached gate connections."""
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"}
        }
        
        # Create mock gate with connection
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        
        mock_gate = MagicMock()
        mock_gate.conn = mock_conn
        gate_cache = {"host1": mock_gate}
        
        inventory = {"hosts": {"host1": {}}}
        
        await mkdir(inventory, gate_cache, "/tmp/test_dir")
        
        mock_sftp.makedirs.assert_called_once_with("/tmp/test_dir", exist_ok=True)


class TestCopy:
    """Tests for copy function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    @patch('faster_than_light.ssh.connect_ssh')
    async def test_copy_success(self, mock_connect_ssh, mock_unique_hosts):
        """Test successful file copy operation."""
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"}
        }
        
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        mock_connect_ssh.return_value = mock_conn
        
        inventory = {"hosts": {"host1": {}}}
        
        result = await copy(inventory, {}, "/local/file", "/remote/file")
        
        expected_result = {"host1": {"changed": True}}
        assert result == expected_result
        
        mock_sftp.put.assert_called_once_with("/local/file", "/remote/file", recurse=True)


class TestTemplate:
    """Tests for template function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    @patch('faster_than_light.ssh.connect_ssh')
    @patch('tempfile.mkstemp')
    @patch('builtins.open')
    @patch('os.write')
    @patch('os.close')
    @patch('os.unlink')
    async def test_template_success(self, mock_unlink, mock_close, mock_write,
                                   mock_open, mock_mkstemp, mock_connect_ssh, 
                                   mock_unique_hosts):
        """Test successful template rendering and copying."""
        mock_unique_hosts.return_value = {
            "host1": {"name": "Alice", "ansible_host": "192.168.1.10"}
        }
        
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        mock_connect_ssh.return_value = mock_conn
        
        mock_mkstemp.return_value = (42, "/tmp/temp_file")
        mock_open.return_value.__enter__.return_value.read.return_value = "Hello {{ name }}!"
        
        inventory = {"hosts": {"host1": {}}}
        
        result = await template(inventory, {}, "/src/template.j2", "/dest/file")
        
        assert result == {"host1": {"changed": True}}
        mock_write.assert_called_once_with(42, b"Hello Alice!")
        mock_close.assert_called_once_with(42)
        mock_unlink.assert_called_once_with("/tmp/temp_file")


class TestCopyFrom:
    """Tests for copy_from function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    @patch('faster_than_light.ssh.connect_ssh')
    @patch('builtins.print')
    async def test_copy_from_success(self, mock_print, mock_connect_ssh, mock_unique_hosts):
        """Test successful file copy from remote."""
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"}
        }
        
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        mock_connect_ssh.return_value = mock_conn
        
        inventory = {"hosts": {"host1": {}}}
        
        await copy_from(inventory, {}, "/remote/file", "/local/file")
        
        mock_sftp.get.assert_called_once_with("/remote/file", "/local/file", recurse=True)
        mock_print.assert_called_once_with("Copy from /remote/file to /local/file")


class TestRemoveItemFromCache:
    """Tests for remove_item_from_cache function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.close_gate')
    async def test_remove_item_from_cache_success(self, mock_close_gate):
        """Test successful cache item removal."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        mock_gate = Gate(mock_conn, mock_process, "/tmp")
        
        gate_cache = {"host1": mock_gate}
        
        await remove_item_from_cache(gate_cache)
        
        assert gate_cache == {}  # Cache should be empty
        mock_close_gate.assert_called_once_with(mock_conn, mock_process, "/tmp")
    
    @pytest.mark.asyncio
    async def test_remove_item_from_cache_none(self):
        """Test removal with None cache."""
        # Should not raise exception
        await remove_item_from_cache(None)
    
    @pytest.mark.asyncio
    async def test_remove_item_from_cache_empty(self):
        """Test removal with empty cache."""
        gate_cache = {}
        
        # Should not raise exception
        await remove_item_from_cache(gate_cache)
        
        assert gate_cache == {}


class TestCloseGate:
    """Tests for close_gate function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    async def test_close_gate_success(self, mock_send_message):
        """Test successful gate closure."""
        mock_conn = MagicMock()
        mock_process = AsyncMock()
        mock_process.exit_status = None
        mock_process.stderr.read.return_value = ""
        
        await close_gate(mock_conn, mock_process, "/tmp")
        
        mock_send_message.assert_called_once_with(mock_process.stdin, "Shutdown", {})
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_gate_none_process(self):
        """Test gate closure with None process."""
        mock_conn = MagicMock()
        
        await close_gate(mock_conn, None, "/tmp")
        
        mock_conn.close.assert_called_once()


class TestRunModuleThroughGate:
    """Tests for run_module_through_gate function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    @patch('faster_than_light.ssh.process_module_result')
    async def test_run_module_through_gate_cached_module(self, mock_process_result,
                                                        mock_read_message, mock_send_message):
        """Test running cached module through gate."""
        mock_process = AsyncMock()
        mock_read_message.return_value = ["ModuleResult", {"stdout": "success"}]
        mock_process_result.return_value = {"result": "success"}
        
        result = await run_module_through_gate(
            mock_process, "/path/to/module.py", "test_module", {"arg": "value"}
        )
        
        assert result == {"result": "success"}
        mock_send_message.assert_called_once_with(
            mock_process.stdin,
            "Module",
            {"module_name": "test_module", "module_args": {"arg": "value"}}
        )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    @patch('faster_than_light.ssh.process_module_result')
    @patch('builtins.open')
    @patch('base64.b64encode')
    async def test_run_module_through_gate_module_not_found(self, mock_b64encode,
                                                           mock_open, mock_process_result,
                                                           mock_read_message, mock_send_message):
        """Test running module when not cached (ModuleNotFound)."""
        mock_process = AsyncMock()
        
        # First call raises ModuleNotFound, second call succeeds
        mock_process_result.side_effect = [
            ModuleNotFound("Module not found"),
            {"result": "success"}
        ]
        mock_read_message.return_value = ["ModuleResult", {"stdout": "success"}]
        mock_b64encode.return_value = b"encoded_content"
        
        mock_file = MagicMock()
        mock_file.read.return_value = b"module content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = await run_module_through_gate(
            mock_process, "/path/to/module.py", "test_module", {"arg": "value"}
        )
        
        assert result == {"result": "success"}
        assert mock_send_message.call_count == 2


class TestRunFtlModuleThroughGate:
    """Tests for run_ftl_module_through_gate function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    @patch('faster_than_light.ssh.process_module_result')
    @patch('builtins.open')
    @patch('base64.b64encode')
    async def test_run_ftl_module_through_gate_success(self, mock_b64encode, mock_open,
                                                      mock_process_result, mock_read_message,
                                                      mock_send_message):
        """Test running FTL module through gate."""
        mock_process = AsyncMock()
        mock_read_message.return_value = ["FTLModuleResult", {"result": {"key": "value"}}]
        mock_process_result.return_value = {"result": {"key": "value"}}
        mock_b64encode.return_value = b"encoded_ftl_content"
        
        mock_file = MagicMock()
        mock_file.read.return_value = b"ftl module content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = await run_ftl_module_through_gate(
            mock_process, "/path/to/ftl_module.py", "ftl_test", {"param": "test"}
        )
        
        assert result == {"result": {"key": "value"}}
        mock_send_message.assert_called_once_with(
            mock_process.stdin,
            "FTLModule",
            {
                "module": "encoded_ftl_content",
                "module_name": "ftl_test",
                "module_args": {"param": "test"}
            }
        )


class TestSendGate:
    """Tests for send_gate function."""
    
    @pytest.mark.asyncio
    async def test_send_gate_new_file(self):
        """Test sending gate when file doesn't exist."""
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_sftp.exists.return_value = False
        
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        
        mock_gate_builder = MagicMock()
        mock_gate_builder.return_value = ("/path/to/gate.pyz", "hash123")
        
        mock_result = MagicMock()
        mock_result.exit_status = 0
        mock_conn.run = AsyncMock(return_value=mock_result)
        
        result = await send_gate(mock_gate_builder, mock_conn, "/tmp", "/usr/bin/python3")
        
        assert result == "/tmp/ftl_gate_hash123.pyz"
        mock_sftp.put.assert_called_once_with("/path/to/gate.pyz", "/tmp/ftl_gate_hash123.pyz")
        mock_conn.run.assert_called_once_with("chmod 700 /tmp/ftl_gate_hash123.pyz", check=True)
    
    @pytest.mark.asyncio
    async def test_send_gate_exists_nonzero_size(self):
        """Test reusing existing gate file with non-zero size."""
        mock_conn = MagicMock()
        mock_sftp = AsyncMock()
        mock_sftp.exists.return_value = True
        
        mock_stats = MagicMock()
        mock_stats.size = 1024
        mock_sftp.lstat.return_value = mock_stats
        
        mock_conn.start_sftp_client.return_value.__aenter__.return_value = mock_sftp
        
        mock_gate_builder = MagicMock()
        mock_gate_builder.return_value = ("/path/to/gate.pyz", "hash123")
        
        result = await send_gate(mock_gate_builder, mock_conn, "/tmp", "/usr/bin/python3")
        
        assert result == "/tmp/ftl_gate_hash123.pyz"
        mock_sftp.put.assert_not_called()  # Should reuse existing file


class TestOpenGate:
    """Tests for open_gate function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    async def test_open_gate_success(self, mock_read_message, mock_send_message):
        """Test successful gate opening."""
        mock_conn = MagicMock()
        mock_process = AsyncMock()
        mock_conn.create_process = AsyncMock(return_value=mock_process)
        mock_read_message.return_value = ["Hello", {}]
        
        result = await open_gate(mock_conn, "/tmp/gate.pyz")
        
        assert result is mock_process
        mock_conn.create_process.assert_called_once_with("/tmp/gate.pyz")
        mock_send_message.assert_called_once_with(mock_process.stdin, "Hello", {})
        mock_read_message.assert_called_once_with(mock_process.stdout)
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    async def test_open_gate_failure(self, mock_read_message, mock_send_message):
        """Test gate opening failure."""
        mock_conn = MagicMock()
        mock_process = AsyncMock()
        mock_conn.create_process = AsyncMock(return_value=mock_process)
        mock_read_message.return_value = ["Error", {"message": "Failed"}]
        mock_process.stderr.read.return_value = "Detailed error"
        
        with pytest.raises(Exception, match="Detailed error"):
            await open_gate(mock_conn, "/tmp/gate.pyz")


class TestSyncFunctions:
    """Tests for synchronous wrapper functions."""
    
    @patch('faster_than_light.ssh.mkdir')
    @patch('asyncio.new_event_loop')
    def test_mkdir_sync_new_loop(self, mock_new_loop, mock_mkdir):
        """Test mkdir_sync with new event loop."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = None
        
        mkdir_sync({}, {}, "/tmp/test")
        
        mock_new_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
    
    @patch('faster_than_light.ssh.mkdir')
    @patch('asyncio.run_coroutine_threadsafe')
    def test_mkdir_sync_existing_loop(self, mock_run_coroutine, mock_mkdir):
        """Test mkdir_sync with existing event loop."""
        mock_future = MagicMock()
        mock_future.result.return_value = None
        mock_run_coroutine.return_value = mock_future
        
        mock_loop = MagicMock()
        
        mkdir_sync({}, {}, "/tmp/test", loop=mock_loop)
        
        mock_future.result.assert_called_once()
    
    @patch('faster_than_light.ssh.copy')
    def test_copy_sync_new_loop(self, mock_copy):
        """Test copy_sync with new event loop."""
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = {"host1": {"changed": True}}
            
            copy_sync({}, {}, "/src", "/dest")
            
            mock_new_loop.assert_called_once()
    
    @patch('faster_than_light.ssh.template')
    def test_template_sync_new_loop(self, mock_template):
        """Test template_sync with new event loop."""
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = {"host1": {"changed": True}}
            
            template_sync({}, {}, "/src.j2", "/dest")
            
            mock_new_loop.assert_called_once()
    
    @patch('faster_than_light.ssh.copy_from')
    def test_copy_from_sync_new_loop(self, mock_copy_from):
        """Test copy_from_sync with new event loop."""
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = None
            
            copy_from_sync({}, {}, "/remote", "/local")
            
            mock_new_loop.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    async def test_mkdir_empty_inventory(self, mock_unique_hosts):
        """Test mkdir with empty inventory."""
        mock_unique_hosts.return_value = {}
        
        # Should not raise exception
        await mkdir({}, {}, "/tmp/test")
        
        mock_unique_hosts.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    async def test_copy_empty_inventory(self, mock_unique_hosts):
        """Test copy with empty inventory."""
        mock_unique_hosts.return_value = {}
        
        result = await copy({}, {}, "/src", "/dest")
        
        assert result == {}
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    async def test_template_empty_inventory(self, mock_unique_hosts):
        """Test template with empty inventory."""
        mock_unique_hosts.return_value = {}
        
        result = await template({}, {}, "/src.j2", "/dest")
        
        assert result == {}
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.unique_hosts')
    async def test_copy_from_empty_inventory(self, mock_unique_hosts):
        """Test copy_from with empty inventory."""
        mock_unique_hosts.return_value = {}
        
        # Should not raise exception
        await copy_from({}, {}, "/remote", "/local")
        
        mock_unique_hosts.assert_called_once()


class TestCloseGateExtended:
    """Extended tests for close_gate function."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    async def test_close_gate_with_exit_status(self, mock_send_message):
        """Test gate closure when process has exit status."""
        mock_conn = MagicMock()
        mock_process = AsyncMock()
        mock_process.exit_status = 0
        mock_process.stderr.read.return_value = ""
        
        await close_gate(mock_conn, mock_process, "/tmp")
        
        mock_send_message.assert_called_once_with(mock_process.stdin, "Shutdown", {})
        mock_process.stderr.read.assert_called_once()
        mock_conn.close.assert_called_once()


# Integration test
class TestSshIntegration:
    """Integration tests for SSH functionality."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.ssh.send_message_str')
    @patch('faster_than_light.ssh.read_message')
    @patch('faster_than_light.ssh.process_module_result')
    async def test_module_execution_workflow(self, mock_process_result, mock_read_message,
                                           mock_send_message):
        """Test module execution through gate workflow."""
        mock_process = AsyncMock()
        mock_read_message.return_value = ["ModuleResult", {"stdout": "integration_success"}]
        mock_process_result.return_value = {"result": "integration_success"}
        
        # Run module through gate
        result = await run_module_through_gate(
            mock_process, "/path/to/module.py", "integration_test", {"test": "value"}
        )
        
        # Verify workflow
        assert result == {"result": "integration_success"}
        mock_send_message.assert_called_once()
        mock_read_message.assert_called_once()
        mock_process_result.assert_called_once() 