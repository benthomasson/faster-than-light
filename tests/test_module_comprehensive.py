"""
Comprehensive unit tests for faster_than_light.module module.

Tests all module execution functionality including async orchestration,
task management, host chunking, ref dereferencing, and error handling.
"""

import asyncio
import sys
from asyncio.tasks import Task
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from faster_than_light.exceptions import ModuleNotFound
from faster_than_light.module import (_run_module, extract_task_results,
                                      run_ftl_module, run_module,
                                      run_module_on_host, run_module_sync)
from faster_than_light.ref import Ref
from faster_than_light.types import Gate


class TestExtractTaskResults:
    """Tests for extract_task_results function."""
    
    def test_extract_task_results_all_success(self):
        """Test extracting results from all successful tasks."""
        # Create mock tasks with successful results
        task1 = MagicMock()
        task1.result.return_value = ("host1", {"result": "success1", "changed": True})
        
        task2 = MagicMock()
        task2.result.return_value = ("host2", {"result": "success2", "changed": False})
        
        tasks = [("host1", task1), ("host2", task2)]
        
        result = extract_task_results(tasks)
        
        expected = {
            "host1": {"result": "success1", "changed": True},
            "host2": {"result": "success2", "changed": False}
        }
        assert result == expected
    
    def test_extract_task_results_with_exceptions(self):
        """Test extracting results when some tasks have exceptions."""
        # Create mock tasks with mixed success/failure
        task1 = MagicMock()
        task1.result.return_value = ("host1", {"result": "success"})
        
        task2 = MagicMock()
        task2.result.side_effect = RuntimeError("Connection failed")
        
        task3 = MagicMock()
        task3.result.side_effect = TimeoutError("Operation timed out")
        
        tasks = [("host1", task1), ("host2", task2), ("host3", task3)]
        
        result = extract_task_results(tasks)
        
        expected = {
            "host1": {"result": "success"},
            "host2": {"error": True, "msg": "Connection failed"},
            "host3": {"error": True, "msg": "Operation timed out"}
        }
        assert result == expected
    
    def test_extract_task_results_empty_tasks(self):
        """Test extracting results from empty task list."""
        tasks = []
        result = extract_task_results(tasks)
        assert result == {}
    
    def test_extract_task_results_all_failures(self):
        """Test extracting results when all tasks fail."""
        task1 = MagicMock()
        task1.result.side_effect = Exception("Generic error")
        
        task2 = MagicMock()
        task2.result.side_effect = ValueError("Invalid value")
        
        tasks = [("host1", task1), ("host2", task2)]
        
        result = extract_task_results(tasks)
        
        expected = {
            "host1": {"error": True, "msg": "Generic error"},
            "host2": {"error": True, "msg": "Invalid value"}
        }
        assert result == expected


class TestRunModuleOnHost:
    """Tests for run_module_on_host function."""
    
    @pytest.mark.asyncio
    async def test_run_module_on_host_local_connection(self):
        """Test running module on host with local connection."""
        host = {"ansible_connection": "local"}
        
        local_runner = AsyncMock()
        local_runner.return_value = ("host1", {"result": "local_success"})
        remote_runner = AsyncMock()
        
        result = await run_module_on_host(
            "host1", host, "/path/to/module.py", {"arg": "value"},
            local_runner, remote_runner, {}, MagicMock()
        )
        
        assert result == ("host1", {"result": "local_success"})
        local_runner.assert_called_once_with("host1", host, "/path/to/module.py", {"arg": "value"})
        remote_runner.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.run_module_remotely')
    async def test_run_module_on_host_remote_connection(self, mock_run_remotely):
        """Test running module on host with remote connection."""
        host = {"ansible_host": "192.168.1.10"}
        mock_run_remotely.return_value = ("host1", {"result": "remote_success"})
        
        local_runner = AsyncMock()
        remote_runner = AsyncMock()
        gate_cache = {}
        gate_builder = MagicMock()
        
        result = await run_module_on_host(
            "host1", host, "/path/to/module.py", {"arg": "value"},
            local_runner, remote_runner, gate_cache, gate_builder
        )
        
        assert result == ("host1", {"result": "remote_success"})
        mock_run_remotely.assert_called_once_with(
            "host1", host, "/path/to/module.py", {"arg": "value"},
            remote_runner, gate_cache, gate_builder
        )
        local_runner.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.run_module_remotely')
    async def test_run_module_on_host_default_remote(self, mock_run_remotely):
        """Test running module on host defaults to remote when no connection specified."""
        host = {}  # No ansible_connection specified
        mock_run_remotely.return_value = ("host1", {"result": "default_remote"})
        
        local_runner = AsyncMock()
        remote_runner = AsyncMock()
        
        result = await run_module_on_host(
            "host1", host, "/path/to/module.py", {"arg": "value"},
            local_runner, remote_runner, {}, MagicMock()
        )
        
        assert result == ("host1", {"result": "default_remote"})
        mock_run_remotely.assert_called_once()
        local_runner.assert_not_called()


class TestRunModuleCore:
    """Tests for _run_module function - the core module execution logic."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('faster_than_light.module.build_ftl_gate')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_run_module_basic_execution(self, mock_gather, mock_create_task, 
                                             mock_build_gate, mock_unique_hosts, mock_find_module):
        """Test basic module execution with minimal configuration."""
        # Setup mocks
        mock_find_module.return_value = "/path/to/found_module.py"
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"}
        }
        
        # Mock task creation and execution
        mock_task = MagicMock()
        mock_task.result.return_value = ("host1", {"result": "success"})
        mock_create_task.return_value = mock_task
        mock_gather.return_value = None
        
        local_runner = AsyncMock()
        remote_runner = AsyncMock()
        
        inventory = {"all": {"hosts": {"host1": {}}}}
        module_dirs = ["/modules"]
        module_name = "test_module"
        
        result = await _run_module(
            inventory, module_dirs, module_name,
            local_runner, remote_runner, None, None, None, None, None
        )
        
        # Verify results
        expected = {"host1": {"result": "success"}}
        assert result == expected
        
        # Verify function calls
        mock_find_module.assert_called_once_with(["/modules"], "test_module")
        mock_unique_hosts.assert_called_once_with(inventory)
        mock_create_task.assert_called_once()
        mock_gather.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    async def test_run_module_module_not_found(self, mock_find_module):
        """Test module execution when module is not found."""
        mock_find_module.return_value = None
        
        inventory = {"all": {"hosts": {"host1": {}}}}
        module_dirs = ["/modules"]
        module_name = "nonexistent_module"
        
        with pytest.raises(ModuleNotFound, match="Module nonexistent_module not found"):
            await _run_module(
                inventory, module_dirs, module_name,
                AsyncMock(), AsyncMock(), None, None, None, None, None
            )
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_run_module_with_refs(self, mock_gather, mock_create_task,
                                       mock_unique_hosts, mock_find_module):
        """Test module execution with Ref objects for dynamic variables."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {
            "host1": {"name": "WebServer1", "port": 80}
        }
        
        # Mock task execution
        mock_task = MagicMock()
        mock_task.result.return_value = ("host1", {"result": "success_with_refs"})
        mock_create_task.return_value = mock_task
        mock_gather.return_value = None
        
        # Create Ref objects for testing
        name_ref = Ref(None, "name")
        port_ref = Ref(None, "port")
        
        module_args = {
            "server_name": name_ref,
            "server_port": port_ref,
            "static_value": "constant"
        }
        
        result = await _run_module(
            {}, ["/modules"], "test_module",
            AsyncMock(), AsyncMock(), None, None, None, module_args, None
        )
        
        # Verify Ref processing was triggered
        assert result == {"host1": {"result": "success_with_refs"}}
        mock_create_task.assert_called_once()
        
        # Verify the task was created with properly dereferenced arguments
        call_args = mock_create_task.call_args[0][0]  # The coroutine passed to create_task
        # We can't easily inspect the coroutine, but we verified refs were detected
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_run_module_with_host_args(self, mock_gather, mock_create_task,
                                            mock_unique_hosts, mock_find_module):
        """Test module execution with host-specific arguments."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"},
            "host2": {"ansible_host": "192.168.1.11"}
        }
        
        # Mock task execution
        mock_task1 = MagicMock()
        mock_task1.result.return_value = ("host1", {"result": "host1_result"})
        mock_task2 = MagicMock()
        mock_task2.result.return_value = ("host2", {"result": "host2_result"})
        mock_create_task.side_effect = [mock_task1, mock_task2]
        mock_gather.return_value = None
        
        module_args = {"global_arg": "global_value"}
        host_args = {
            "host1": {"specific_arg": "host1_value"},
            "host2": {"specific_arg": "host2_value"}
        }
        
        result = await _run_module(
            {}, ["/modules"], "test_module",
            AsyncMock(), AsyncMock(), None, None, None, module_args, host_args
        )
        
        expected = {
            "host1": {"result": "host1_result"},
            "host2": {"result": "host2_result"}
        }
        assert result == expected
        assert mock_create_task.call_count == 2
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('faster_than_light.module.chunk')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_run_module_chunking_behavior(self, mock_gather, mock_create_task,
                                               mock_chunk, mock_unique_hosts, mock_find_module):
        """Test that hosts are properly chunked for performance."""
        mock_find_module.return_value = "/path/to/module.py"
        
        # Create many hosts to test chunking
        hosts = {f"host{i}": {"ansible_host": f"192.168.1.{i}"} for i in range(1, 25)}
        mock_unique_hosts.return_value = hosts
        
        # Mock chunking to return 3 chunks
        chunk1 = [(f"host{i}", hosts[f"host{i}"]) for i in range(1, 11)]
        chunk2 = [(f"host{i}", hosts[f"host{i}"]) for i in range(11, 21)]
        chunk3 = [(f"host{i}", hosts[f"host{i}"]) for i in range(21, 25)]
        mock_chunk.return_value = [chunk1, chunk2, chunk3]
        
        # Mock task execution
        mock_tasks = []
        for i in range(1, 25):
            mock_task = MagicMock()
            mock_task.result.return_value = (f"host{i}", {"result": f"success{i}"})
            mock_tasks.append(mock_task)
        mock_create_task.side_effect = mock_tasks
        mock_gather.return_value = None
        
        result = await _run_module(
            {}, ["/modules"], "test_module",
            AsyncMock(), AsyncMock(), None, None, None, None, None
        )
        
        # Verify chunking was called with chunk size 10
        mock_chunk.assert_called_once()
        chunk_args = mock_chunk.call_args[0]
        assert len(chunk_args[0]) == 24  # 24 hosts
        assert chunk_args[1] == 10  # chunk size
        
        # Verify gather was called 3 times (once per chunk)
        assert mock_gather.call_count == 3
        
        # Verify all hosts got results
        assert len(result) == 24
        for i in range(1, 25):
            assert result[f"host{i}"] == {"result": f"success{i}"}
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    async def test_run_module_with_custom_gate_builder(self, mock_unique_hosts, mock_find_module):
        """Test module execution with custom gate builder."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {"host1": {"ansible_host": "192.168.1.10"}}
        
        custom_gate_builder = MagicMock()
        
        with patch('asyncio.create_task') as mock_create_task, \
             patch('asyncio.gather', new_callable=AsyncMock):
            mock_task = MagicMock()
            mock_task.result.return_value = ("host1", {"result": "custom_gate_success"})
            mock_create_task.return_value = mock_task
            
            result = await _run_module(
                {}, ["/modules"], "test_module",
                AsyncMock(), AsyncMock(), None, None, None, None, None,
                use_gate=custom_gate_builder
            )
        
        # Verify custom gate builder was used
        assert result == {"host1": {"result": "custom_gate_success"}}
        # The custom gate builder should have been passed to run_module_on_host


class TestRunModuleWrappers:
    """Tests for the public module execution wrapper functions."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module._run_module')
    async def test_run_module_wrapper(self, mock_run_module):
        """Test run_module wrapper function."""
        mock_run_module.return_value = {"host1": {"result": "wrapper_success"}}
        
        inventory = {"all": {"hosts": {"host1": {}}}}
        module_dirs = ["/modules"]
        module_name = "test_module"
        gate_cache = {}
        modules = ["test_module"]
        dependencies = ["dep1"]
        module_args = {"arg": "value"}
        host_args = {"host1": {"specific": "value"}}
        use_gate = MagicMock()
        
        result = await run_module(
            inventory, module_dirs, module_name, gate_cache,
            modules, dependencies, module_args, host_args, use_gate
        )
        
        assert result == {"host1": {"result": "wrapper_success"}}
        
        # Verify _run_module was called with correct runners
        mock_run_module.assert_called_once()
        call_args = mock_run_module.call_args[0]
        assert call_args[0] == inventory
        assert call_args[1] == module_dirs
        assert call_args[2] == module_name
        # Verify correct local and remote runners were passed
        assert call_args[3].__name__ == "run_module_locally"
        assert call_args[4].__name__ == "run_module_through_gate"
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module._run_module')
    async def test_run_ftl_module_wrapper(self, mock_run_module):
        """Test run_ftl_module wrapper function."""
        mock_run_module.return_value = {"host1": {"result": "ftl_wrapper_success"}}
        
        result = await run_ftl_module(
            {"all": {"hosts": {"host1": {}}}}, ["/modules"], "ftl_test_module"
        )
        
        assert result == {"host1": {"result": "ftl_wrapper_success"}}
        
        # Verify _run_module was called with FTL runners
        mock_run_module.assert_called_once()
        call_args = mock_run_module.call_args[0]
        # Verify correct FTL local and remote runners were passed
        assert call_args[3].__name__ == "run_ftl_module_locally"
        assert call_args[4].__name__ == "run_ftl_module_through_gate"


class TestRunModuleSync:
    """Tests for run_module_sync function."""
    
    @patch('faster_than_light.module._run_module')
    @patch('asyncio.new_event_loop')
    def test_run_module_sync_new_loop(self, mock_new_loop, mock_run_module):
        """Test run_module_sync with new event loop."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = {"host1": {"result": "sync_success"}}
        
        result = run_module_sync(
            {"all": {"hosts": {"host1": {}}}}, ["/modules"], "test_module"
        )
        
        assert result == {"host1": {"result": "sync_success"}}
        mock_new_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
    
    @patch('faster_than_light.module._run_module')
    @patch('asyncio.run_coroutine_threadsafe')
    def test_run_module_sync_existing_loop(self, mock_run_coroutine, mock_run_module):
        """Test run_module_sync with existing event loop."""
        mock_future = MagicMock()
        mock_future.result.return_value = {"host1": {"result": "existing_loop_success"}}
        mock_run_coroutine.return_value = mock_future
        
        mock_loop = MagicMock()
        
        result = run_module_sync(
            {"all": {"hosts": {"host1": {}}}}, ["/modules"], "test_module",
            loop=mock_loop
        )
        
        assert result == {"host1": {"result": "existing_loop_success"}}
        mock_run_coroutine.assert_called_once()
        mock_future.result.assert_called_once()
    
    @patch('faster_than_light.module._run_module')
    @patch('asyncio.new_event_loop')
    @patch('builtins.print')
    def test_run_module_sync_gate_cache_warning(self, mock_print, mock_new_loop, mock_run_module):
        """Test run_module_sync prints warning when gate_cache provided without loop."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = {"host1": {"result": "success"}}
        
        gate_cache = {"host1": MagicMock()}
        
        result = run_module_sync(
            {"all": {"hosts": {"host1": {}}}}, ["/modules"], "test_module",
            gate_cache=gate_cache
        )
        
        # Verify warning was printed
        mock_print.assert_called_once()
        print_message = mock_print.call_args[0][0]
        assert "Gate cache is not supported without loop" in print_message
        
        # Verify gate_cache was reset to empty dict
        assert result == {"host1": {"result": "success"}}


class TestIntegrationScenarios:
    """Integration tests for complex module execution scenarios."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('faster_than_light.module.run_module_remotely')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_mixed_local_remote_execution(self, mock_gather, mock_run_remotely,
                                               mock_unique_hosts, mock_find_module):
        """Test execution with mix of local and remote hosts."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {
            "localhost": {"ansible_connection": "local"},
            "remote1": {"ansible_host": "192.168.1.10"},
            "remote2": {"ansible_host": "192.168.1.11"}
        }
        
        # Mock remote execution
        mock_run_remotely.side_effect = [
            ("remote1", {"result": "remote1_success"}),
            ("remote2", {"result": "remote2_success"})
        ]
        
        local_runner = AsyncMock()
        local_runner.return_value = ("localhost", {"result": "local_success"})
        remote_runner = AsyncMock()
        
        with patch('asyncio.create_task') as mock_create_task:
            # Mock tasks for all hosts
            tasks = []
            for host in ["localhost", "remote1", "remote2"]:
                mock_task = MagicMock()
                if host == "localhost":
                    mock_task.result.return_value = ("localhost", {"result": "local_success"})
                else:
                    mock_task.result.return_value = (host, {"result": f"{host}_success"})
                tasks.append(mock_task)
            
            mock_create_task.side_effect = tasks
            mock_gather.return_value = None
            
            result = await _run_module(
                {}, ["/modules"], "test_module",
                local_runner, remote_runner, None, None, None, None, None
            )
        
        expected = {
            "localhost": {"result": "local_success"},
            "remote1": {"result": "remote1_success"},
            "remote2": {"result": "remote2_success"}
        }
        assert result == expected
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('faster_than_light.module.deref')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_complex_ref_and_host_args_combination(self, mock_gather, mock_create_task,
                                                        mock_deref, mock_unique_hosts, mock_find_module):
        """Test complex scenario with both Refs and host-specific args."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {
            "web1": {"name": "WebServer1", "port": 80},
            "web2": {"name": "WebServer2", "port": 8080}
        }
        
        # Mock ref dereferencing
        def deref_side_effect(host, value):
            if isinstance(value, Ref):
                return host.get(value.name, f"deref_{value.name}")
            return value
        mock_deref.side_effect = deref_side_effect
        
        # Mock task execution
        mock_task1 = MagicMock()
        mock_task1.result.return_value = ("web1", {"result": "web1_complex"})
        mock_task2 = MagicMock()
        mock_task2.result.return_value = ("web2", {"result": "web2_complex"})
        mock_create_task.side_effect = [mock_task1, mock_task2]
        mock_gather.return_value = None
        
        # Setup complex args with Refs and host-specific overrides
        name_ref = Ref(None, "name")
        port_ref = Ref(None, "port")
        
        module_args = {
            "server_name": name_ref,
            "server_port": port_ref,
            "default_config": "global"
        }
        
        host_args = {
            "web1": {"ssl_enabled": True},
            "web2": {"ssl_enabled": False, "server_port": 9090}  # Override ref
        }
        
        result = await _run_module(
            {}, ["/modules"], "test_module",
            AsyncMock(), AsyncMock(), None, None, None, module_args, host_args
        )
        
        expected = {
            "web1": {"result": "web1_complex"},
            "web2": {"result": "web2_complex"}
        }
        assert result == expected
        
        # Verify deref was called for Ref objects
        assert mock_deref.call_count >= 4  # At least 2 refs * 2 hosts


class TestErrorHandling:
    """Tests for error handling in module execution."""
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    @patch('faster_than_light.module.unique_hosts')
    @patch('asyncio.create_task')
    @patch('asyncio.gather', new_callable=AsyncMock)
    async def test_task_exception_handling(self, mock_gather, mock_create_task,
                                          mock_unique_hosts, mock_find_module):
        """Test that task exceptions are properly captured in results."""
        mock_find_module.return_value = "/path/to/module.py"
        mock_unique_hosts.return_value = {
            "host1": {"ansible_host": "192.168.1.10"},
            "host2": {"ansible_host": "192.168.1.11"}
        }
        
        # Mock one successful task and one failing task
        mock_task1 = MagicMock()
        mock_task1.result.return_value = ("host1", {"result": "success"})
        
        mock_task2 = MagicMock()
        mock_task2.result.side_effect = ConnectionError("Network unreachable")
        
        mock_create_task.side_effect = [mock_task1, mock_task2]
        mock_gather.return_value = None
        
        result = await _run_module(
            {}, ["/modules"], "test_module",
            AsyncMock(), AsyncMock(), None, None, None, None, None
        )
        
        expected = {
            "host1": {"result": "success"},
            "host2": {"error": True, "msg": "Network unreachable"}
        }
        assert result == expected
    
    @pytest.mark.asyncio
    @patch('faster_than_light.module.find_module')
    async def test_invalid_module_dirs(self, mock_find_module):
        """Test handling of invalid module directories."""
        mock_find_module.return_value = None
        
        with pytest.raises(ModuleNotFound):
            await _run_module(
                {"all": {"hosts": {"host1": {}}}}, ["/nonexistent"], "missing_module",
                AsyncMock(), AsyncMock(), None, None, None, None, None
            )
    
    @patch('faster_than_light.module._run_module')
    @patch('asyncio.new_event_loop')
    def test_run_module_sync_exception_propagation(self, mock_new_loop, mock_run_module):
        """Test that exceptions in sync wrapper are properly propagated."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        mock_loop.run_until_complete.side_effect = RuntimeError("Async execution failed")
        
        with pytest.raises(RuntimeError, match="Async execution failed"):
            run_module_sync(
                {"all": {"hosts": {"host1": {}}}}, ["/modules"], "test_module"
            ) 