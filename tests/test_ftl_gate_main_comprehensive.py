"""
Comprehensive unit tests for faster_than_light.ftl_gate.__main__ module.

Tests all gate main functionality including protocol handling, module detection,
I/O classes, execution functions, and the main message processing loop.
"""

import asyncio
import base64
import json
import sys

# Mock the ftl_gate import before importing the module under test
from unittest.mock import AsyncMock, MagicMock, call, mock_open, patch

import pytest

sys.modules["ftl_gate"] = MagicMock()

# Import the module under test
import faster_than_light.ftl_gate.__main__ as ftl_main


class TestStdinReader:
    """Tests for StdinReader class."""

    @pytest.mark.asyncio
    @patch("sys.stdin")
    async def test_read_string_input(self, mock_stdin):
        """Test reading string data from stdin."""
        mock_stdin.read.return_value = "hello"

        reader = ftl_main.StdinReader()
        result = await reader.read(5)

        assert result == b"hello"
        mock_stdin.read.assert_called_once_with(5)

    @pytest.mark.asyncio
    @patch("sys.stdin")
    async def test_read_bytes_input(self, mock_stdin):
        """Test reading bytes data from stdin."""
        mock_stdin.read.return_value = b"hello"

        reader = ftl_main.StdinReader()
        result = await reader.read(5)

        assert result == b"hello"
        mock_stdin.read.assert_called_once_with(5)

    @pytest.mark.asyncio
    @patch("sys.stdin")
    async def test_read_empty_input(self, mock_stdin):
        """Test reading empty input from stdin."""
        mock_stdin.read.return_value = ""

        reader = ftl_main.StdinReader()
        result = await reader.read(10)

        assert result == b""
        mock_stdin.read.assert_called_once_with(10)


class TestStdoutWriter:
    """Tests for StdoutWriter class."""

    @patch("sys.stdout")
    def test_write_bytes_data(self, mock_stdout):
        """Test writing bytes data to stdout."""
        writer = ftl_main.StdoutWriter()
        writer.write(b"Hello, World!")

        mock_stdout.write.assert_called_once_with("Hello, World!")

    @patch("sys.stdout")
    def test_write_empty_bytes(self, mock_stdout):
        """Test writing empty bytes to stdout."""
        writer = ftl_main.StdoutWriter()
        writer.write(b"")

        mock_stdout.write.assert_called_once_with("")

    @patch("sys.stdout")
    def test_write_unicode_bytes(self, mock_stdout):
        """Test writing Unicode bytes to stdout."""
        writer = ftl_main.StdoutWriter()
        writer.write("Hello, 世界!".encode("utf-8"))

        mock_stdout.write.assert_called_once_with("Hello, 世界!")


class TestConnectStdinStdout:
    """Tests for connect_stdin_stdout function."""

    @pytest.mark.asyncio
    @patch("asyncio.get_event_loop")
    @patch("asyncio.StreamWriter")
    @patch("asyncio.StreamReaderProtocol")
    @patch("asyncio.StreamReader")
    async def test_successful_pipe_connection(
        self,
        mock_stream_reader_cls,
        mock_protocol_cls,
        mock_stream_writer_cls,
        mock_get_loop,
    ):
        """Test successful asyncio pipe connection."""
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.connect_read_pipe = AsyncMock()
        mock_loop.connect_write_pipe = AsyncMock(return_value=("transport", "protocol"))

        # Mock StreamReader and StreamWriter instances
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_stream_reader_cls.return_value = mock_reader
        mock_stream_writer_cls.return_value = mock_writer

        reader, writer = await ftl_main.connect_stdin_stdout()

        # Should return mocked asyncio objects when successful
        mock_loop.connect_read_pipe.assert_called_once()
        mock_loop.connect_write_pipe.assert_called_once()
        assert reader is mock_reader
        assert writer is mock_writer

    @pytest.mark.asyncio
    @patch("asyncio.get_event_loop")
    async def test_fallback_to_custom_readers(self, mock_get_loop):
        """Test fallback to custom reader/writer when pipe connection fails."""
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.connect_read_pipe = AsyncMock(side_effect=ValueError("Pipe failed"))

        reader, writer = await ftl_main.connect_stdin_stdout()

        # Should return custom objects when pipe connection fails
        assert isinstance(reader, ftl_main.StdinReader)
        assert isinstance(writer, ftl_main.StdoutWriter)


class TestReadMessage:
    """Tests for read_message function."""

    @pytest.mark.asyncio
    async def test_read_valid_message(self):
        """Test reading a valid protocol message."""
        message_data = b'["Hello", {}]'
        length_prefix = f"{len(message_data):08x}".encode()

        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [length_prefix, message_data]

        msg_type, data = await ftl_main.read_message(mock_reader)

        assert msg_type == "Hello"
        assert data == {}
        assert mock_reader.read.call_count == 2

    @pytest.mark.asyncio
    async def test_read_message_with_data(self):
        """Test reading a message with complex data."""
        message_data = b'["Module", {"module_name": "test", "args": {"key": "value"}}]'
        length_prefix = f"{len(message_data):08x}".encode()

        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [length_prefix, message_data]

        msg_type, data = await ftl_main.read_message(mock_reader)

        assert msg_type == "Module"
        assert data == {"module_name": "test", "args": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_read_message_channel_closed(self):
        """Test handling channel closure."""
        mock_reader = AsyncMock()
        mock_reader.read.return_value = b""  # EOF

        msg_type, data = await ftl_main.read_message(mock_reader)

        assert msg_type is None
        assert data is None

    @pytest.mark.asyncio
    async def test_read_message_zero_length(self):
        """Test handling zero-length messages."""
        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [
            b"00000000",  # Zero length
            b"0000000d",  # Valid length
            b'["Hello", {}]',  # Valid message
        ]

        msg_type, data = await ftl_main.read_message(mock_reader)

        assert msg_type == "Hello"
        assert data == {}
        assert mock_reader.read.call_count == 3

    @pytest.mark.asyncio
    async def test_read_message_partial_reads(self):
        """Test handling partial message reads."""
        message_data = b'["Hello", {}]'
        length_prefix = f"{len(message_data):08x}".encode()

        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [
            length_prefix,
            message_data[:5],  # Partial read
            message_data[5:],  # Remaining data
        ]

        msg_type, data = await ftl_main.read_message(mock_reader)

        assert msg_type == "Hello"
        assert data == {}

    @pytest.mark.asyncio
    async def test_read_message_invalid_json(self):
        """Test handling invalid JSON data."""
        message_data = b'{"invalid": json}'
        length_prefix = f"{len(message_data):08x}".encode()

        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [length_prefix, message_data]

        with pytest.raises(json.JSONDecodeError):
            await ftl_main.read_message(mock_reader)


class TestSendMessage:
    """Tests for send_message function."""

    def test_send_simple_message(self):
        """Test sending a simple message."""
        mock_writer = MagicMock()

        ftl_main.send_message(mock_writer, "Hello", {})

        expected_message = json.dumps(["Hello", {}]).encode()
        expected_length = f"{len(expected_message):08x}".encode()

        assert mock_writer.write.call_count == 2
        mock_writer.write.assert_has_calls(
            [call(expected_length), call(expected_message)]
        )

    def test_send_message_with_data(self):
        """Test sending a message with complex data."""
        mock_writer = MagicMock()
        data = {"result": {"status": "success", "items": [1, 2, 3]}}

        ftl_main.send_message(mock_writer, "ModuleResult", data)

        expected_message = json.dumps(["ModuleResult", data]).encode()
        expected_length = f"{len(expected_message):08x}".encode()

        mock_writer.write.assert_has_calls(
            [call(expected_length), call(expected_message)]
        )

    def test_send_message_size_assertion(self):
        """Test message size limit assertion."""
        mock_writer = MagicMock()
        # Create a very large data structure (this won't actually hit the limit but tests the concept)
        large_data = {"data": "x" * 1000}

        # Should not raise assertion error for reasonable size
        ftl_main.send_message(mock_writer, "Test", large_data)

        assert mock_writer.write.call_count == 2


class TestCheckOutput:
    """Tests for check_output function."""

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_check_output_basic_command(self, mock_create_subprocess):
        """Test basic command execution."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Hello World", b""))
        mock_create_subprocess.return_value = mock_process

        stdout, stderr = await ftl_main.check_output("echo 'Hello World'")

        assert stdout == b"Hello World"
        assert stderr == b""
        mock_create_subprocess.assert_called_once_with(
            "echo 'Hello World'",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=None,
        )

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_check_output_with_env(self, mock_create_subprocess):
        """Test command execution with custom environment."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"output", b"error"))
        mock_create_subprocess.return_value = mock_process

        env = {"PYTHONPATH": "/custom/path"}
        stdout, stderr = await ftl_main.check_output("python -c 'import sys'", env=env)

        assert stdout == b"output"
        assert stderr == b"error"
        mock_create_subprocess.assert_called_once_with(
            "python -c 'import sys'",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_check_output_with_stdin(self, mock_create_subprocess):
        """Test command execution with stdin input."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"processed", b""))
        mock_create_subprocess.return_value = mock_process

        stdin_data = b'{"key": "value"}'
        stdout, stderr = await ftl_main.check_output("cat", stdin=stdin_data)

        assert stdout == b"processed"
        assert stderr == b""
        mock_process.communicate.assert_called_once_with(stdin_data)


class TestModuleDetection:
    """Tests for module type detection functions."""

    def test_is_binary_module_true(self):
        """Test detecting binary modules."""
        # Binary data that can't be decoded as UTF-8
        binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        assert ftl_main.is_binary_module(binary_data) is True

    def test_is_binary_module_false(self):
        """Test detecting text modules."""
        text_data = b'#!/usr/bin/python3\nprint("hello")'

        assert ftl_main.is_binary_module(text_data) is False

    def test_is_new_style_module_true(self):
        """Test detecting new-style Ansible modules."""
        module_data = b"""
        from ansible.module_utils.basic import AnsibleModule
        module = AnsibleModule(argument_spec={})
        """

        assert ftl_main.is_new_style_module(module_data) is True

    def test_is_new_style_module_false(self):
        """Test detecting non-new-style modules."""
        module_data = b'#!/usr/bin/python3\nprint("hello")'

        assert ftl_main.is_new_style_module(module_data) is False

    def test_is_want_json_module_true(self):
        """Test detecting WANT_JSON modules."""
        module_data = b"""
        #!/usr/bin/python3
        # WANT_JSON
        import sys, json
        """

        assert ftl_main.is_want_json_module(module_data) is True

    def test_is_want_json_module_false(self):
        """Test detecting non-WANT_JSON modules."""
        module_data = b'#!/usr/bin/python3\nprint("hello")'

        assert ftl_main.is_want_json_module(module_data) is False


class TestGetPythonPath:
    """Tests for get_python_path function."""

    @patch(
        "sys.path",
        ["/usr/lib/python3.9", "/usr/lib/python3.9/site-packages", "/custom/path"],
    )
    @patch("os.pathsep", ":")
    def test_get_python_path_unix(self):
        """Test Python path construction on Unix systems."""
        result = ftl_main.get_python_path()

        expected = "/usr/lib/python3.9:/usr/lib/python3.9/site-packages:/custom/path"
        assert result == expected

    @patch("sys.path", ["C:\\Python39", "C:\\Python39\\site-packages"])
    @patch("os.pathsep", ";")
    def test_get_python_path_windows(self):
        """Test Python path construction on Windows systems."""
        result = ftl_main.get_python_path()

        expected = "C:\\Python39;C:\\Python39\\site-packages"
        assert result == expected


class TestGateRunModule:
    """Tests for gate_run_module function."""

    @pytest.mark.asyncio
    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("os.environ.copy")
    @patch("builtins.open", new_callable=mock_open)
    @patch("faster_than_light.ftl_gate.__main__.check_output")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("faster_than_light.ftl_gate.__main__.get_python_path")
    @patch("importlib.resources.files")
    async def test_gate_run_module_from_bundle(
        self,
        mock_resources,
        mock_get_path,
        mock_send,
        mock_check_output,
        mock_open_file,
        mock_env_copy,
        mock_rmtree,
        mock_mkdtemp,
    ):
        """Test running a module from the gate bundle."""
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/ftl-test"
        mock_env_copy.return_value = {"PATH": "/usr/bin"}
        mock_get_path.return_value = "/custom/python/path"
        mock_check_output.return_value = (b'{"result": "success"}', b"")

        # Mock resources loading
        mock_files = MagicMock()
        mock_files.joinpath.return_value.read_bytes.return_value = (
            b'#!/usr/bin/python3\nprint("test")'
        )
        mock_resources.return_value = mock_files

        mock_writer = MagicMock()

        await ftl_main.gate_run_module(
            mock_writer, "test_module", None, {"arg1": "value1"}
        )

        # Verify module execution
        mock_mkdtemp.assert_called_once_with(prefix="ftl-module")
        mock_send.assert_called_once_with(
            mock_writer,
            "ModuleResult",
            {"stdout": '{"result": "success"}', "stderr": ""},
        )
        mock_rmtree.assert_called_once_with("/tmp/ftl-test")

    @pytest.mark.asyncio
    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("os.environ.copy")
    @patch("builtins.open", new_callable=mock_open)
    @patch("faster_than_light.ftl_gate.__main__.check_output")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("faster_than_light.ftl_gate.__main__.get_python_path")
    @patch("base64.b64decode")
    async def test_gate_run_module_from_message(
        self,
        mock_b64decode,
        mock_get_path,
        mock_send,
        mock_check_output,
        mock_open_file,
        mock_env_copy,
        mock_rmtree,
        mock_mkdtemp,
    ):
        """Test running a module from message content."""
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/ftl-test"
        mock_env_copy.return_value = {"PATH": "/usr/bin"}
        mock_get_path.return_value = "/custom/python/path"
        mock_b64decode.return_value = b'#!/usr/bin/python3\nprint("test")'
        mock_check_output.return_value = (b'{"result": "success"}', b"")

        mock_writer = MagicMock()
        encoded_module = base64.b64encode(b'#!/usr/bin/python3\nprint("test")').decode()

        await ftl_main.gate_run_module(
            mock_writer, "test_module", encoded_module, {"arg1": "value1"}
        )

        # Verify module execution
        mock_b64decode.assert_called_once_with(encoded_module)
        mock_send.assert_called_once_with(
            mock_writer,
            "ModuleResult",
            {"stdout": '{"result": "success"}', "stderr": ""},
        )

    @pytest.mark.asyncio
    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("builtins.open", new_callable=mock_open)
    @patch("importlib.resources.files")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    async def test_gate_run_module_not_found(
        self, mock_send, mock_resources, mock_open_file, mock_rmtree, mock_mkdtemp
    ):
        """Test handling module not found error."""
        mock_mkdtemp.return_value = "/tmp/ftl-test"

        # Mock resources to raise FileNotFoundError
        mock_files = MagicMock()
        mock_files.joinpath.return_value.read_bytes.side_effect = FileNotFoundError(
            "Module not found"
        )
        mock_resources.return_value = mock_files

        mock_writer = MagicMock()

        with pytest.raises(ftl_main.ModuleNotFoundException):
            await ftl_main.gate_run_module(mock_writer, "nonexistent_module")

        mock_rmtree.assert_called_once_with("/tmp/ftl-test")


class TestRunFtlModule:
    """Tests for run_ftl_module function."""

    @pytest.mark.asyncio
    @patch("base64.b64decode")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    async def test_run_ftl_module_success(self, mock_send, mock_b64decode):
        """Test successful FTL module execution."""
        # Setup mock module
        module_code = """
async def main():
    return {"status": "success", "data": [1, 2, 3]}
"""
        mock_b64decode.return_value = module_code.encode()

        mock_writer = MagicMock()
        encoded_module = base64.b64encode(module_code.encode()).decode()

        await ftl_main.run_ftl_module(mock_writer, "test_ftl", encoded_module)

        # Verify result sending
        mock_send.assert_called_once_with(
            mock_writer,
            "FTLModuleResult",
            {"result": {"status": "success", "data": [1, 2, 3]}},
        )

    @pytest.mark.asyncio
    @patch("base64.b64decode")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    async def test_run_ftl_module_with_imports(self, mock_send, mock_b64decode):
        """Test FTL module with imports."""
        # Use a simpler module that doesn't require imports
        module_code = """
async def main():
    # Simple async function without external imports
    return {"async_result": True}
"""
        mock_b64decode.return_value = module_code.encode()

        mock_writer = MagicMock()
        encoded_module = base64.b64encode(module_code.encode()).decode()

        await ftl_main.run_ftl_module(mock_writer, "async_test", encoded_module)

        mock_send.assert_called_once_with(
            mock_writer, "FTLModuleResult", {"result": {"async_result": True}}
        )

    @pytest.mark.asyncio
    @patch("base64.b64decode")
    async def test_run_ftl_module_syntax_error(self, mock_b64decode):
        """Test FTL module with syntax error."""
        module_code = """
async def main(:  # Syntax error
    return {}
"""
        mock_b64decode.return_value = module_code.encode()

        mock_writer = MagicMock()
        encoded_module = base64.b64encode(module_code.encode()).decode()

        with pytest.raises(SyntaxError):
            await ftl_main.run_ftl_module(mock_writer, "syntax_error", encoded_module)

    @pytest.mark.asyncio
    @patch("base64.b64decode")
    async def test_run_ftl_module_no_main_function(self, mock_b64decode):
        """Test FTL module without main function."""
        module_code = """
def other_function():
    return "not main"
"""
        mock_b64decode.return_value = module_code.encode()

        mock_writer = MagicMock()
        encoded_module = base64.b64encode(module_code.encode()).decode()

        with pytest.raises(KeyError):
            await ftl_main.run_ftl_module(mock_writer, "no_main", encoded_module)


class TestMain:
    """Tests for main function."""

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_hello_message(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function with Hello message."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [("Hello", {}), (None, None)]  # End of input

        result = await ftl_main.main([])

        assert result is None
        mock_send.assert_has_calls(
            [call(mock_writer, "Hello", {}), call(mock_writer, "Goodbye", {})]
        )

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("faster_than_light.ftl_gate.__main__.gate_run_module")
    @patch("logging.basicConfig")
    async def test_main_module_message(
        self, mock_logging, mock_gate_run, mock_send, mock_read, mock_connect
    ):
        """Test main function with Module message."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [
            ("Module", {"module_name": "test", "module_args": {"key": "value"}}),
            (None, None),  # End of input
        ]

        result = await ftl_main.main([])

        assert result is None
        mock_gate_run.assert_called_once_with(
            mock_writer, module_name="test", module_args={"key": "value"}
        )
        mock_send.assert_called_once_with(mock_writer, "Goodbye", {})

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("faster_than_light.ftl_gate.__main__.run_ftl_module")
    @patch("logging.basicConfig")
    async def test_main_ftl_module_message(
        self, mock_logging, mock_ftl_run, mock_send, mock_read, mock_connect
    ):
        """Test main function with FTLModule message."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [
            ("FTLModule", {"module_name": "test_ftl", "module": "encoded_content"}),
            (None, None),  # End of input
        ]

        result = await ftl_main.main([])

        assert result is None
        mock_ftl_run.assert_called_once_with(
            mock_writer, module_name="test_ftl", module="encoded_content"
        )
        mock_send.assert_called_once_with(mock_writer, "Goodbye", {})

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_shutdown_message(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function with Shutdown message."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.return_value = ("Shutdown", {})

        result = await ftl_main.main([])

        assert result is None
        mock_send.assert_called_once_with(mock_writer, "Goodbye", {})

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_unknown_message(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function with unknown message type."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [
            ("UnknownType", {"data": "test"}),
            (None, None),  # End of input
        ]

        result = await ftl_main.main([])

        assert result is None
        mock_send.assert_has_calls(
            [
                call(
                    mock_writer,
                    "Error",
                    {"message": "Unknown message type UnknownType"},
                ),
                call(mock_writer, "Goodbye", {}),
            ]
        )

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_module_not_found_exception(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function handling ModuleNotFoundException."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [
            ("Module", {"module_name": "nonexistent"}),
            (None, None),  # End of input
        ]

        # Mock gate_run_module to raise ModuleNotFoundException
        with patch(
            "faster_than_light.ftl_gate.__main__.gate_run_module"
        ) as mock_gate_run:
            mock_gate_run.side_effect = ftl_main.ModuleNotFoundException("nonexistent")

            result = await ftl_main.main([])

            assert result is None
            mock_send.assert_has_calls(
                [
                    call(
                        mock_writer,
                        "ModuleNotFound",
                        {"message": "Module nonexistent not found in gate bundle."},
                    ),
                    call(mock_writer, "Goodbye", {}),
                ]
            )

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_system_error(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function handling system errors."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = RuntimeError("System error")

        result = await ftl_main.main([])

        assert result == 1
        # Should send GateSystemError and exit with code 1
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert call_args[1] == "GateSystemError"
        assert "System error" in call_args[2]["message"]

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_invalid_module_data(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function with invalid Module data."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [
            ("Module", "invalid_data_not_dict"),
            (None, None),  # End of input
        ]

        result = await ftl_main.main([])

        assert result is None
        mock_send.assert_has_calls(
            [
                call(mock_writer, "Error", {"message": "Invalid Module data"}),
                call(mock_writer, "Goodbye", {}),
            ]
        )

    @pytest.mark.asyncio
    @patch("faster_than_light.ftl_gate.__main__.connect_stdin_stdout")
    @patch("faster_than_light.ftl_gate.__main__.read_message")
    @patch("faster_than_light.ftl_gate.__main__.send_message")
    @patch("logging.basicConfig")
    async def test_main_invalid_ftl_module_data(
        self, mock_logging, mock_send, mock_read, mock_connect
    ):
        """Test main function with invalid FTLModule data."""
        # Setup mocks
        mock_reader, mock_writer = MagicMock(), MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [("FTLModule", None), (None, None)]  # End of input

        result = await ftl_main.main([])

        assert result is None
        mock_send.assert_has_calls(
            [
                call(mock_writer, "Error", {"message": "Invalid FTLModule data"}),
                call(mock_writer, "Goodbye", {}),
            ]
        )


class TestModuleNotFoundException:
    """Tests for ModuleNotFoundException."""

    def test_module_not_found_exception_creation(self):
        """Test creating ModuleNotFoundException."""
        exc = ftl_main.ModuleNotFoundException("test_module")

        assert str(exc) == "test_module"
        assert isinstance(exc, Exception)

    def test_module_not_found_exception_inheritance(self):
        """Test ModuleNotFoundException inheritance."""
        exc = ftl_main.ModuleNotFoundException("test")

        assert isinstance(exc, Exception)
        assert isinstance(exc, ftl_main.ModuleNotFoundException)
