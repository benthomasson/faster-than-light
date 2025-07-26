"""
Comprehensive unit tests for faster_than_light.message module.

Tests all message protocol functionality including message sending, reading,
error handling, and protocol validation.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faster_than_light.exceptions import ProtocolError
from faster_than_light.message import (
    GateMessage,
    read_message,
    send_message,
    send_message_str,
)


class TestGateMessage:
    """Tests for GateMessage NamedTuple."""

    def test_gate_message_creation(self):
        """Test creating a GateMessage with type and body."""
        message = GateMessage("Module", {"arg": "value"})

        assert message.message_type == "Module"
        assert message.message_body == {"arg": "value"}

    def test_gate_message_named_tuple_properties(self):
        """Test GateMessage behaves as NamedTuple."""
        message = GateMessage("FTLModule", ["data", "list"])

        # Test indexing
        assert message[0] == "FTLModule"
        assert message[1] == ["data", "list"]

        # Test unpacking
        msg_type, msg_body = message
        assert msg_type == "FTLModule"
        assert msg_body == ["data", "list"]

        # Test immutability
        with pytest.raises(AttributeError):
            message.message_type = "NewType"

    def test_gate_message_equality(self):
        """Test GateMessage equality comparison."""
        message1 = GateMessage("Test", {"key": "value"})
        message2 = GateMessage("Test", {"key": "value"})
        message3 = GateMessage("Different", {"key": "value"})

        assert message1 == message2
        assert message1 != message3

    def test_gate_message_with_complex_data(self):
        """Test GateMessage with complex data structures."""
        complex_data = {
            "nested": {"dict": True},
            "list": [1, 2, 3],
            "null": None,
            "bool": False,
        }

        message = GateMessage("ComplexTest", complex_data)

        assert message.message_type == "ComplexTest"
        assert message.message_body == complex_data
        assert message.message_body["nested"]["dict"] is True
        assert message.message_body["null"] is None


class TestSendMessage:
    """Tests for send_message function (binary encoding)."""

    def test_send_message_basic(self):
        """Test basic message sending with binary encoding."""
        mock_writer = MagicMock()

        send_message(mock_writer, "TestType", {"test": "data"})

        # Verify the calls made to writer
        assert mock_writer.write.call_count == 2

        # First call should be the length (8 hex chars)
        length_call = mock_writer.write.call_args_list[0][0][0]
        assert len(length_call) == 8  # 8 hex characters
        assert isinstance(length_call, bytes)

        # Second call should be the JSON message
        message_call = mock_writer.write.call_args_list[1][0][0]
        expected_message = json.dumps(["TestType", {"test": "data"}]).encode()
        assert message_call == expected_message

    def test_send_message_length_calculation(self):
        """Test that message length is correctly calculated and encoded."""
        mock_writer = MagicMock()

        # Send a message with known content
        test_data = {"key": "value"}
        send_message(mock_writer, "Length", test_data)

        # Calculate expected length
        expected_json = json.dumps(["Length", test_data])
        expected_length = len(expected_json.encode())
        expected_length_hex = "{:08x}".format(expected_length).encode()

        # Verify length was sent correctly
        length_call = mock_writer.write.call_args_list[0][0][0]
        assert length_call == expected_length_hex

    def test_send_message_complex_data(self):
        """Test sending message with complex data structures."""
        mock_writer = MagicMock()

        complex_data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null_value": None,
            "list": [1, "two", {"three": 3}],
            "nested": {"deep": {"value": "found"}},
        }

        send_message(mock_writer, "Complex", complex_data)

        # Verify JSON serialization works correctly
        message_call = mock_writer.write.call_args_list[1][0][0]
        decoded_message = json.loads(message_call.decode())

        assert decoded_message[0] == "Complex"
        assert decoded_message[1] == complex_data

    def test_send_message_empty_data(self):
        """Test sending message with empty data."""
        mock_writer = MagicMock()

        send_message(mock_writer, "Empty", {})

        # Verify empty dict is handled correctly
        message_call = mock_writer.write.call_args_list[1][0][0]
        expected_message = json.dumps(["Empty", {}]).encode()
        assert message_call == expected_message

    def test_send_message_unicode_content(self):
        """Test sending message with unicode content."""
        mock_writer = MagicMock()

        unicode_data = {"message": "Hello 世界", "emoji": "🚀"}
        send_message(mock_writer, "Unicode", unicode_data)

        # Verify unicode is properly encoded
        message_call = mock_writer.write.call_args_list[1][0][0]
        decoded_message = json.loads(message_call.decode("utf-8"))

        assert decoded_message[1]["message"] == "Hello 世界"
        assert decoded_message[1]["emoji"] == "🚀"


class TestSendMessageStr:
    """Tests for send_message_str function (string encoding with error handling)."""

    def test_send_message_str_basic(self):
        """Test basic string message sending."""
        mock_writer = MagicMock()

        send_message_str(mock_writer, "StringType", {"str": "data"})

        # Verify the calls made to writer
        assert mock_writer.write.call_count == 2

        # First call should be the length (8 hex chars as string)
        length_call = mock_writer.write.call_args_list[0][0][0]
        assert len(length_call) == 8  # 8 hex characters
        assert isinstance(length_call, str)

        # Second call should be the JSON message as string
        message_call = mock_writer.write.call_args_list[1][0][0]
        expected_message = json.dumps(["StringType", {"str": "data"}])
        assert message_call == expected_message

    def test_send_message_str_broken_pipe_handling(self):
        """Test BrokenPipeError handling in send_message_str."""
        mock_writer = MagicMock()
        mock_writer.write.side_effect = BrokenPipeError("Pipe broken")

        with patch("faster_than_light.message.logger") as mock_logger:
            # Should not raise exception, just log error
            send_message_str(mock_writer, "TestType", {"data": "test"})

            # Verify error was logged
            mock_logger.error.assert_called_once_with("BrokenPipeError")

    def test_send_message_str_broken_pipe_on_second_write(self):
        """Test BrokenPipeError on message content write."""
        mock_writer = MagicMock()
        # First write (length) succeeds, second write (message) fails
        mock_writer.write.side_effect = [None, BrokenPipeError("Pipe broken")]

        with patch("faster_than_light.message.logger") as mock_logger:
            send_message_str(mock_writer, "TestType", {"data": "test"})

            # Should have attempted both writes
            assert mock_writer.write.call_count == 2
            mock_logger.error.assert_called_once_with("BrokenPipeError")

    def test_send_message_str_other_exceptions_propagate(self):
        """Test that non-BrokenPipeError exceptions are propagated."""
        mock_writer = MagicMock()
        mock_writer.write.side_effect = RuntimeError("Different error")

        with pytest.raises(RuntimeError, match="Different error"):
            send_message_str(mock_writer, "TestType", {"data": "test"})

    def test_send_message_str_length_format(self):
        """Test string length formatting in send_message_str."""
        mock_writer = MagicMock()

        send_message_str(mock_writer, "Format", {"test": "length"})

        # Verify length is formatted as 8-character hex string
        length_call = mock_writer.write.call_args_list[0][0][0]

        # Should be 8 characters, hex format, string type
        assert len(length_call) == 8
        assert isinstance(length_call, str)
        assert all(c in "0123456789abcdef" for c in length_call.lower())


class TestReadMessage:
    """Tests for read_message async function."""

    @pytest.mark.asyncio
    async def test_read_message_successful(self):
        """Test successful message reading."""
        mock_reader = AsyncMock()

        # Prepare test data
        test_message = ["TestType", {"key": "value"}]
        json_data = json.dumps(test_message).encode()
        length_hex = "{:08x}".format(len(json_data)).encode()

        # Mock the reads: first for length, second for message
        mock_reader.read.side_effect = [length_hex, json_data]

        result = await read_message(mock_reader)

        assert result == test_message
        assert mock_reader.read.call_count == 2

        # Verify read calls
        calls = mock_reader.read.call_args_list
        assert calls[0][0][0] == 8  # First read for 8-byte length
        assert calls[1][0][0] == len(json_data)  # Second read for message content

    @pytest.mark.asyncio
    async def test_read_message_empty_length_returns_none(self):
        """Test that empty length read returns None."""
        mock_reader = AsyncMock()
        mock_reader.read.return_value = b""  # Empty bytes indicate EOF

        result = await read_message(mock_reader)

        assert result is None
        mock_reader.read.assert_called_once_with(8)

    @pytest.mark.asyncio
    async def test_read_message_invalid_hex_length(self):
        """Test ProtocolError on invalid hex length."""
        mock_reader = AsyncMock()

        # Return invalid hex and some additional data
        invalid_length = b"invalid!"
        additional_data = b"more_data"
        mock_reader.read.side_effect = [invalid_length, additional_data]

        with pytest.raises(ProtocolError):
            await read_message(mock_reader)

        # Should have read length and additional data for error message
        assert mock_reader.read.call_count == 2
        calls = mock_reader.read.call_args_list
        assert calls[0][0][0] == 8  # Length read
        assert len(calls[1][0]) == 0  # Additional data read with no args

    @pytest.mark.asyncio
    async def test_read_message_protocol_error_includes_data(self):
        """Test that ProtocolError includes the invalid data."""
        mock_reader = AsyncMock()

        invalid_hex = b"notahex!"
        error_data = b"error_context"
        mock_reader.read.side_effect = [invalid_hex, error_data]

        try:
            await read_message(mock_reader)
            pytest.fail("Should have raised ProtocolError")
        except ProtocolError as e:
            # Error should contain the concatenated invalid data
            assert invalid_hex + error_data in str(e).encode()

    @pytest.mark.asyncio
    async def test_read_message_complex_json_data(self):
        """Test reading complex JSON message data."""
        mock_reader = AsyncMock()

        # Complex test message
        complex_message = [
            "ComplexType",
            {
                "nested": {"deep": {"value": True}},
                "array": [1, 2, {"item": "test"}],
                "unicode": "测试 🎉",
                "numbers": {"int": 42, "float": 3.14159},
                "nulls": None,
            },
        ]

        json_data = json.dumps(complex_message).encode("utf-8")
        length_hex = "{:08x}".format(len(json_data)).encode()

        mock_reader.read.side_effect = [length_hex, json_data]

        result = await read_message(mock_reader)

        assert result == complex_message
        assert result[1]["unicode"] == "测试 🎉"
        assert result[1]["nested"]["deep"]["value"] is True

    @pytest.mark.asyncio
    async def test_read_message_partial_length_read(self):
        """Test handling of partial length reads that causes ValueError."""
        mock_reader = AsyncMock()

        # Return length that contains invalid hex characters
        invalid_hex_length = b"12xyza!@"  # 8 bytes but invalid hex
        additional_data = b"error_data"
        mock_reader.read.side_effect = [invalid_hex_length, additional_data]

        with pytest.raises(ProtocolError):
            await read_message(mock_reader)

    @pytest.mark.asyncio
    async def test_read_message_short_but_valid_length_read(self):
        """Test handling of shorter but valid hex length reads with truncated data."""
        mock_reader = AsyncMock()

        # Return short length (less than 8 bytes but valid hex)
        short_length = b"1a"  # Only 2 bytes, but valid hex (26 in decimal)
        # Provide exactly 26 bytes but make it invalid JSON due to truncation
        truncated_json = b'["Short", {"data": "tes'  # Exactly 26 bytes, invalid JSON

        mock_reader.read.side_effect = [short_length, truncated_json]

        # This should fail JSON parsing due to truncated data
        with pytest.raises(json.JSONDecodeError):
            await read_message(mock_reader)

    @pytest.mark.asyncio
    async def test_read_message_zero_length_message(self):
        """Test reading a zero-length message."""
        mock_reader = AsyncMock()

        # Zero length message
        zero_length = b"00000000"
        empty_data = b""
        mock_reader.read.side_effect = [zero_length, empty_data]

        # Should result in JSON decode error due to empty data
        with pytest.raises(json.JSONDecodeError):
            await read_message(mock_reader)

    @pytest.mark.asyncio
    async def test_read_message_malformed_json(self):
        """Test handling of malformed JSON data."""
        mock_reader = AsyncMock()

        # Valid length but invalid JSON
        malformed_json = b'{"incomplete": '
        length_hex = "{:08x}".format(len(malformed_json)).encode()

        mock_reader.read.side_effect = [length_hex, malformed_json]

        with pytest.raises(json.JSONDecodeError):
            await read_message(mock_reader)

    @pytest.mark.asyncio
    async def test_read_message_large_message(self):
        """Test reading a large message."""
        mock_reader = AsyncMock()

        # Create a large message
        large_data = {"data": "x" * 10000}  # 10KB of data
        large_message = ["LargeType", large_data]

        json_data = json.dumps(large_message).encode()
        length_hex = "{:08x}".format(len(json_data)).encode()

        mock_reader.read.side_effect = [length_hex, json_data]

        result = await read_message(mock_reader)

        assert result == large_message
        assert len(result[1]["data"]) == 10000


class TestMessageProtocolIntegration:
    """Integration tests for the complete message protocol."""

    def test_send_read_roundtrip_binary(self):
        """Test sending and reading message roundtrip (simulated)."""
        # Simulate the binary protocol
        message_type = "TestRoundtrip"
        message_data = {"roundtrip": "test", "number": 42}

        # Capture what send_message would write
        mock_writer = MagicMock()
        send_message(mock_writer, message_type, message_data)

        # Extract the written data
        length_bytes = mock_writer.write.call_args_list[0][0][0]
        message_bytes = mock_writer.write.call_args_list[1][0][0]

        # Verify we can parse it back
        expected_length = int(length_bytes.decode(), 16)
        assert len(message_bytes) == expected_length

        parsed_message = json.loads(message_bytes.decode())
        assert parsed_message == [message_type, message_data]

    def test_send_read_roundtrip_string(self):
        """Test string protocol roundtrip (simulated)."""
        message_type = "StringRoundtrip"
        message_data = {"string_test": "value"}

        # Capture what send_message_str would write
        mock_writer = MagicMock()
        send_message_str(mock_writer, message_type, message_data)

        # Extract the written data
        length_str = mock_writer.write.call_args_list[0][0][0]
        message_str = mock_writer.write.call_args_list[1][0][0]

        # Verify consistency
        expected_length = int(length_str, 16)
        assert len(message_str.encode()) == expected_length

        parsed_message = json.loads(message_str)
        assert parsed_message == [message_type, message_data]

    @pytest.mark.asyncio
    async def test_message_protocol_edge_cases(self):
        """Test various edge cases in the message protocol."""
        test_cases = [
            # Empty message
            ("Empty", {}),
            # Null data
            ("Null", None),
            # Array data
            ("Array", [1, 2, 3]),
            # Boolean data
            ("Boolean", True),
            # Number data
            ("Number", 42),
            # String data
            ("String", "just a string"),
        ]

        for msg_type, msg_data in test_cases:
            # Test binary protocol
            mock_writer = MagicMock()
            send_message(mock_writer, msg_type, msg_data)

            # Verify serialization works
            message_bytes = mock_writer.write.call_args_list[1][0][0]
            parsed = json.loads(message_bytes.decode())
            assert parsed == [msg_type, msg_data]

    def test_length_encoding_consistency(self):
        """Test that length encoding is consistent between send functions."""
        test_message = {"consistency": "test"}

        # Test binary version
        mock_writer_bin = MagicMock()
        send_message(mock_writer_bin, "Test", test_message)
        length_bin = mock_writer_bin.write.call_args_list[0][0][0]

        # Test string version
        mock_writer_str = MagicMock()
        send_message_str(mock_writer_str, "Test", test_message)
        length_str = mock_writer_str.write.call_args_list[0][0][0]

        # Lengths should be the same when decoded
        assert int(length_bin.decode(), 16) == int(length_str, 16)


class TestErrorScenarios:
    """Tests for various error scenarios and edge cases."""

    def test_send_message_json_serialization_error(self):
        """Test handling of JSON serialization errors."""
        mock_writer = MagicMock()

        # Create non-serializable data
        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            send_message(mock_writer, "Error", {"bad": NonSerializable()})

    def test_send_message_str_json_serialization_error(self):
        """Test JSON serialization error in string version."""
        mock_writer = MagicMock()

        # Create non-serializable data
        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            send_message_str(mock_writer, "Error", {"bad": NonSerializable()})

    @pytest.mark.asyncio
    async def test_read_message_reader_exception(self):
        """Test handling of reader exceptions."""
        mock_reader = AsyncMock()
        mock_reader.read.side_effect = ConnectionError("Connection lost")

        with pytest.raises(ConnectionError, match="Connection lost"):
            await read_message(mock_reader)

    @pytest.mark.asyncio
    async def test_read_message_partial_message_read(self):
        """Test handling of partial message reads."""
        mock_reader = AsyncMock()

        # Valid length but partial message
        full_message = json.dumps(["Test", {"data": "value"}]).encode()
        length_hex = "{:08x}".format(len(full_message)).encode()
        partial_message = full_message[
            : len(full_message) // 2
        ]  # Only half the message

        mock_reader.read.side_effect = [length_hex, partial_message]

        # Should result in JSON decode error due to incomplete data
        with pytest.raises(json.JSONDecodeError):
            await read_message(mock_reader)
