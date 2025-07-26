"""
Comprehensive unit tests for faster_than_light.gate module.

Tests all gate building functionality including caching, module installation,
dependency management, error handling, and zipapp creation.
"""

import sys
from subprocess import CalledProcessError
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from faster_than_light.exceptions import ModuleNotFound
from faster_than_light.gate import build_ftl_gate, use_gate


class TestUseGate:
    """Tests for use_gate function."""

    def test_use_gate_returns_parameters_unchanged(self):
        """Test that use_gate returns parameters unchanged."""
        cached_gate = "/path/to/cached_gate.pyz"
        gate_hash = "abc123def456"

        result_gate, result_hash = use_gate(cached_gate, gate_hash)

        assert result_gate == cached_gate
        assert result_hash == gate_hash

    def test_use_gate_with_interpreter_parameter(self):
        """Test use_gate with interpreter parameter (ignored)."""
        cached_gate = "/custom/gate.pyz"
        gate_hash = "hash123"
        interpreter = "/usr/bin/python3"

        result_gate, result_hash = use_gate(cached_gate, gate_hash, interpreter)

        assert result_gate == cached_gate
        assert result_hash == gate_hash

    def test_use_gate_with_none_values(self):
        """Test use_gate with None values."""
        result_gate, result_hash = use_gate(None, None)

        assert result_gate is None
        assert result_hash is None

    def test_use_gate_with_empty_strings(self):
        """Test use_gate with empty strings."""
        result_gate, result_hash = use_gate("", "")

        assert result_gate == ""
        assert result_hash == ""


class TestBuildFtlGateBasic:
    """Tests for basic build_ftl_gate functionality."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    def test_build_ftl_gate_minimal_parameters(
        self, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate with minimal parameters."""
        # Setup mocks
        mock_ensure_dir.return_value = "/home/user/.ftl"
        mock_exists.return_value = True  # Cached gate exists
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "test_hash_123"
        mock_sha256.return_value = mock_hash_obj

        result_gate, result_hash = build_ftl_gate()

        # Verify cache directory creation
        mock_ensure_dir.assert_called_once_with("~/.ftl")

        # Verify hash calculation
        mock_sha256.assert_called_once()
        expected_input = "".join([str(i) for i in [sys.executable]])
        mock_sha256.assert_called_with(expected_input.encode())

        # Verify cached gate path
        expected_gate = "/home/user/.ftl/ftl_gate_test_hash_123.pyz"
        assert result_gate == expected_gate
        assert result_hash == "test_hash_123"

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    def test_build_ftl_gate_with_all_parameters(
        self, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate with all parameters."""
        # Setup mocks
        mock_ensure_dir.return_value = "/custom/cache"
        mock_exists.return_value = True  # Cached gate exists
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "complex_hash_456"
        mock_sha256.return_value = mock_hash_obj

        modules = ["module1", "module2"]
        module_dirs = ["/path/to/modules", "/other/modules"]
        dependencies = ["requests>=2.25.0", "pytest"]
        interpreter = "/usr/bin/python3.9"
        local_interpreter = "/usr/bin/python3.8"

        result_gate, result_hash = build_ftl_gate(
            modules=modules,
            module_dirs=module_dirs,
            dependencies=dependencies,
            interpreter=interpreter,
            local_interpreter=local_interpreter,
        )

        # Verify hash calculation includes all inputs
        expected_inputs = []
        expected_inputs.extend(modules)
        expected_inputs.extend(module_dirs)
        expected_inputs.extend(dependencies)
        expected_inputs.extend(interpreter)
        expected_input_str = "".join([str(i) for i in expected_inputs])
        mock_sha256.assert_called_with(expected_input_str.encode())

        expected_gate = "/custom/cache/ftl_gate_complex_hash_456.pyz"
        assert result_gate == expected_gate
        assert result_hash == "complex_hash_456"


class TestBuildFtlGateCaching:
    """Tests for build_ftl_gate caching behavior."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.logger")
    def test_build_ftl_gate_cache_hit(
        self, mock_logger, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate returns cached gate when it exists."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = True
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "cached_hash"
        mock_sha256.return_value = mock_hash_obj

        result_gate, result_hash = build_ftl_gate(modules=["test_module"])

        # Verify cache hit path
        expected_gate = "/cache/ftl_gate_cached_hash.pyz"
        mock_exists.assert_called_once_with(expected_gate)
        mock_logger.info.assert_called_once()
        assert "reusing cached_gate" in mock_logger.info.call_args[0][0]

        assert result_gate == expected_gate
        assert result_hash == "cached_hash"

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    def test_build_ftl_gate_cache_miss_triggers_build(
        self, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate builds new gate when cache miss."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False  # Cache miss
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "new_hash"
        mock_sha256.return_value = mock_hash_obj

        with (
            patch("faster_than_light.gate.tempfile.mkdtemp") as mock_mkdtemp,
            patch("faster_than_light.gate.os.mkdir"),
            patch("faster_than_light.gate.os.makedirs"),
            patch("builtins.open", mock_open()),
            patch("faster_than_light.gate.files") as mock_files,
            patch("faster_than_light.gate.zipapp.create_archive"),
            patch("faster_than_light.gate.shutil.rmtree"),
            patch("faster_than_light.gate.shutil.copy"),
        ):
            mock_mkdtemp.return_value = "/tmp/test_build"
            mock_files.return_value.joinpath.return_value.read_text.return_value = (
                "# gate main"
            )

            result_gate, result_hash = build_ftl_gate()

            # Verify build process was triggered
            mock_mkdtemp.assert_called_once()
            expected_gate = "/cache/ftl_gate_new_hash.pyz"
            assert result_gate == expected_gate


class TestBuildFtlGateModuleInstallation:
    """Tests for module installation in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.find_module")
    @patch("faster_than_light.gate.read_module")
    @patch("faster_than_light.gate.zipapp.create_archive")
    @patch("faster_than_light.gate.shutil.rmtree")
    @patch("faster_than_light.gate.shutil.copy")
    def test_build_ftl_gate_installs_modules(
        self,
        mock_copy,
        mock_rmtree,
        mock_zipapp,
        mock_read_module,
        mock_find_module,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test that modules are properly installed in the gate."""
        # Setup mocks
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/gate_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "module_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"

        # Module installation mocks
        mock_find_module.side_effect = ["/modules/test1.py", "/modules/test2.py"]
        mock_read_module.side_effect = [b"module1_content", b"module2_content"]

        modules = ["test1", "test2"]
        module_dirs = ["/modules"]

        with patch("builtins.open", mock_open()) as mock_file:
            build_ftl_gate(modules=modules, module_dirs=module_dirs)

            # Verify module discovery
            expected_find_calls = [
                call(module_dirs, "test1"),
                call(module_dirs, "test2"),
            ]
            mock_find_module.assert_has_calls(expected_find_calls)

            # Verify module reading
            expected_read_calls = [
                call(module_dirs, "test1"),
                call(module_dirs, "test2"),
            ]
            mock_read_module.assert_has_calls(expected_read_calls)

            # Verify module files were written
            # The mock_file will have been called multiple times for different files
            assert (
                mock_file.call_count >= 4
            )  # At least __main__.py, __init__.py, and 2 modules

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.find_module")
    def test_build_ftl_gate_module_not_found_error(
        self, mock_find_module, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test ModuleNotFound is raised when module cannot be found."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "error_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_find_module.return_value = None  # Module not found

        with (
            patch("faster_than_light.gate.tempfile.mkdtemp"),
            patch("faster_than_light.gate.os.mkdir"),
            patch("faster_than_light.gate.os.makedirs"),
            patch("builtins.open", mock_open()),
            patch("faster_than_light.gate.files"),
        ):
            with pytest.raises(ModuleNotFound, match="Cannot find missing_module in"):
                build_ftl_gate(modules=["missing_module"], module_dirs=["/modules"])


class TestBuildFtlGateDependencies:
    """Tests for dependency installation in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.check_output")
    @patch("faster_than_light.gate.zipapp.create_archive")
    @patch("faster_than_light.gate.shutil.rmtree")
    @patch("faster_than_light.gate.shutil.copy")
    def test_build_ftl_gate_installs_dependencies(
        self,
        mock_copy,
        mock_rmtree,
        mock_zipapp,
        mock_check_output,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test that dependencies are installed via pip."""
        # Setup mocks
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/dep_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "dep_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"
        mock_check_output.return_value = b"Successfully installed packages"

        dependencies = ["requests>=2.25.0", "pytest>=6.0"]
        local_interpreter = "/usr/bin/python3.9"

        with patch("builtins.open", mock_open()) as mock_file:
            build_ftl_gate(
                dependencies=dependencies, local_interpreter=local_interpreter
            )

            # Verify requirements.txt was written
            requirements_calls = [
                call
                for call in mock_file.call_args_list
                if "/tmp/dep_build/requirements.txt" in str(call)
            ]
            assert len(requirements_calls) > 0

            # Verify pip was called with correct arguments
            expected_command = [
                local_interpreter,
                "-m",
                "pip",
                "install",
                "-r",
                "/tmp/dep_build/requirements.txt",
                "--target",
                "/tmp/dep_build/ftl_gate",
            ]
            mock_check_output.assert_called_once_with(expected_command)

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.check_output")
    def test_build_ftl_gate_pip_failure(
        self,
        mock_check_output,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test error handling when pip installation fails."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/fail_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "fail_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"
        mock_check_output.side_effect = CalledProcessError(
            1, "pip", b"Package not found"
        )

        with patch("builtins.open", mock_open()):
            with pytest.raises(CalledProcessError):
                build_ftl_gate(dependencies=["nonexistent-package"])


class TestBuildFtlGateZipappCreation:
    """Tests for zipapp creation in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.zipapp.create_archive")
    @patch("faster_than_light.gate.shutil.rmtree")
    @patch("faster_than_light.gate.shutil.copy")
    def test_build_ftl_gate_creates_zipapp(
        self,
        mock_copy,
        mock_rmtree,
        mock_zipapp,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test that zipapp is created with correct parameters."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/zip_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "zip_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"

        interpreter = "/usr/bin/python3.10"

        with patch("builtins.open", mock_open()):
            build_ftl_gate(interpreter=interpreter)

            # Verify zipapp creation
            mock_zipapp.assert_called_once_with(
                "/tmp/zip_build/ftl_gate", "/tmp/zip_build/ftl_gate.pyz", interpreter
            )

            # Verify cleanup and copy
            mock_rmtree.assert_called_once_with("/tmp/zip_build/ftl_gate")
            mock_copy.assert_called_once_with(
                "/tmp/zip_build/ftl_gate.pyz", "/cache/ftl_gate_zip_hash.pyz"
            )


class TestBuildFtlGateFileOperations:
    """Tests for file operations in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.zipapp.create_archive")
    @patch("faster_than_light.gate.shutil.rmtree")
    @patch("faster_than_light.gate.shutil.copy")
    def test_build_ftl_gate_directory_structure(
        self,
        mock_copy,
        mock_rmtree,
        mock_zipapp,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test that correct directory structure is created."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/struct_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "struct_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"

        with patch("builtins.open", mock_open()):
            build_ftl_gate()

            # Verify directory creation
            mock_mkdir.assert_called_once_with("/tmp/struct_build/ftl_gate")
            mock_makedirs.assert_called_once_with("/tmp/struct_build/ftl_gate/ftl_gate")

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    def test_build_ftl_gate_file_write_failure(
        self,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test error handling when file writing fails."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/fail_write"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "write_fail_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = "# main"

        with patch("builtins.open", side_effect=PermissionError("Cannot write file")):
            with pytest.raises(PermissionError):
                build_ftl_gate()


class TestBuildFtlGateIntegration:
    """Integration tests for build_ftl_gate functionality."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    @patch("faster_than_light.gate.os.mkdir")
    @patch("faster_than_light.gate.os.makedirs")
    @patch("faster_than_light.gate.files")
    @patch("faster_than_light.gate.find_module")
    @patch("faster_than_light.gate.read_module")
    @patch("faster_than_light.gate.check_output")
    @patch("faster_than_light.gate.zipapp.create_archive")
    @patch("faster_than_light.gate.shutil.rmtree")
    @patch("faster_than_light.gate.shutil.copy")
    def test_build_ftl_gate_full_workflow(
        self,
        mock_copy,
        mock_rmtree,
        mock_zipapp,
        mock_check_output,
        mock_read_module,
        mock_find_module,
        mock_files,
        mock_makedirs,
        mock_mkdir,
        mock_mkdtemp,
        mock_sha256,
        mock_exists,
        mock_ensure_dir,
    ):
        """Test complete gate building workflow."""
        # Setup comprehensive mocks
        mock_ensure_dir.return_value = "/test/cache"
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/full_build"
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "full_workflow_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_files.return_value.joinpath.return_value.read_text.return_value = (
            "#!/usr/bin/env python3\n# Gate main"
        )
        mock_find_module.return_value = "/modules/service.py"
        mock_read_module.return_value = b"def main(): pass"
        mock_check_output.return_value = b"Successfully installed requests"

        modules = ["service"]
        module_dirs = ["/custom/modules"]
        dependencies = ["requests>=2.25.0"]
        interpreter = "/usr/bin/python3.9"
        local_interpreter = "/usr/bin/python3.8"

        with patch("builtins.open", mock_open()):
            result_gate, result_hash = build_ftl_gate(
                modules=modules,
                module_dirs=module_dirs,
                dependencies=dependencies,
                interpreter=interpreter,
                local_interpreter=local_interpreter,
            )

            # Verify complete workflow
            assert result_gate == "/test/cache/ftl_gate_full_workflow_hash.pyz"
            assert result_hash == "full_workflow_hash"

            # Verify all major steps were called
            mock_ensure_dir.assert_called_once_with("~/.ftl")
            mock_find_module.assert_called_once_with(module_dirs, "service")
            mock_read_module.assert_called_once_with(module_dirs, "service")
            mock_check_output.assert_called_once()
            mock_zipapp.assert_called_once()
            mock_copy.assert_called_once()

    @patch("faster_than_light.gate.logger")
    def test_build_ftl_gate_debug_logging(self, mock_logger):
        """Test that debug logging works correctly."""
        with (
            patch("faster_than_light.gate.ensure_directory"),
            patch("faster_than_light.gate.os.path.exists", return_value=True),
            patch("faster_than_light.gate.hashlib.sha256") as mock_sha256,
        ):
            mock_hash_obj = MagicMock()
            mock_hash_obj.hexdigest.return_value = "debug_hash"
            mock_sha256.return_value = mock_hash_obj

            modules = ["test"]
            module_dirs = ["/test"]
            dependencies = ["dep1"]

            build_ftl_gate(
                modules=modules, module_dirs=module_dirs, dependencies=dependencies
            )

            # Verify debug logging was called
            mock_logger.debug.assert_called_once()
            debug_call = mock_logger.debug.call_args[0][0]
            assert "build_ftl_gate" in debug_call
            assert "modules=" in debug_call


class TestBuildFtlGateEdgeCases:
    """Tests for edge cases and error scenarios in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    def test_build_ftl_gate_empty_lists(
        self, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate with explicitly empty lists."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = True
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "empty_hash"
        mock_sha256.return_value = mock_hash_obj

        result_gate, result_hash = build_ftl_gate(
            modules=[], module_dirs=[], dependencies=[]
        )

        # Should work with empty lists
        assert result_gate == "/cache/ftl_gate_empty_hash.pyz"
        assert result_hash == "empty_hash"

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    def test_build_ftl_gate_special_characters_in_parameters(
        self, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test build_ftl_gate with special characters in parameters."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = True
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "special_hash"
        mock_sha256.return_value = mock_hash_obj

        # Test with special characters that might affect hashing
        modules = ["module-with-dashes", "module_with_underscores"]
        module_dirs = ["/path with spaces/modules", "/path/with/unicode/🚀"]
        dependencies = ["package>=1.0.0", "git+https://github.com/user/repo.git"]

        result_gate, result_hash = build_ftl_gate(
            modules=modules, module_dirs=module_dirs, dependencies=dependencies
        )

        # Should handle special characters without issues
        assert result_gate == "/cache/ftl_gate_special_hash.pyz"
        assert result_hash == "special_hash"

    @patch("faster_than_light.gate.ensure_directory")
    def test_build_ftl_gate_cache_directory_creation_failure(self, mock_ensure_dir):
        """Test error handling when cache directory creation fails."""
        mock_ensure_dir.side_effect = PermissionError("Cannot create cache directory")

        with pytest.raises(PermissionError):
            build_ftl_gate()

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    @patch("faster_than_light.gate.hashlib.sha256")
    @patch("faster_than_light.gate.tempfile.mkdtemp")
    def test_build_ftl_gate_temp_directory_failure(
        self, mock_mkdtemp, mock_sha256, mock_exists, mock_ensure_dir
    ):
        """Test error handling when temporary directory creation fails."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = False
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = "temp_fail_hash"
        mock_sha256.return_value = mock_hash_obj
        mock_mkdtemp.side_effect = OSError("Cannot create temp directory")

        with pytest.raises(OSError):
            build_ftl_gate()


class TestBuildFtlGateHashGeneration:
    """Tests for hash generation in build_ftl_gate."""

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    def test_build_ftl_gate_hash_consistency(self, mock_exists, mock_ensure_dir):
        """Test that identical inputs produce identical hashes."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = True

        # Call with identical parameters twice
        modules = ["mod1", "mod2"]
        module_dirs = ["/dir1", "/dir2"]
        dependencies = ["dep1", "dep2"]
        interpreter = "/usr/bin/python3"

        _, hash1 = build_ftl_gate(
            modules=modules,
            module_dirs=module_dirs,
            dependencies=dependencies,
            interpreter=interpreter,
        )

        _, hash2 = build_ftl_gate(
            modules=modules,
            module_dirs=module_dirs,
            dependencies=dependencies,
            interpreter=interpreter,
        )

        assert hash1 == hash2

    @patch("faster_than_light.gate.ensure_directory")
    @patch("faster_than_light.gate.os.path.exists")
    def test_build_ftl_gate_hash_different_inputs(self, mock_exists, mock_ensure_dir):
        """Test that different inputs produce different hashes."""
        mock_ensure_dir.return_value = "/cache"
        mock_exists.return_value = True

        _, hash1 = build_ftl_gate(modules=["mod1"], interpreter="/usr/bin/python3")
        _, hash2 = build_ftl_gate(modules=["mod2"], interpreter="/usr/bin/python3")
        _, hash3 = build_ftl_gate(modules=["mod1"], interpreter="/usr/bin/python3.9")

        # All hashes should be different
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3
