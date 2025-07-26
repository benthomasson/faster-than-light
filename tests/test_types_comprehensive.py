"""
Comprehensive unit tests for faster_than_light.types module.

Tests the Gate NamedTuple data structure including creation, field access,
immutability, type validation, and integration scenarios.
"""

from typing import get_type_hints
from unittest.mock import MagicMock

import pytest

from faster_than_light.types import Gate


class TestGate:
    """Tests for Gate NamedTuple."""

    def test_gate_creation_basic(self):
        """Test basic Gate creation with all fields."""
        # Create mock objects for the required types
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/test_gate"

        gate = Gate(conn=mock_conn, gate_process=mock_process, temp_dir=temp_dir)

        assert gate.conn is mock_conn
        assert gate.gate_process is mock_process
        assert gate.temp_dir == temp_dir

    def test_gate_creation_with_none_values(self):
        """Test Gate creation with None values."""
        gate = Gate(conn=None, gate_process=None, temp_dir=None)

        assert gate.conn is None
        assert gate.gate_process is None
        assert gate.temp_dir is None

    def test_gate_creation_positional_args(self):
        """Test Gate creation using positional arguments."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/positional"

        gate = Gate(mock_conn, mock_process, temp_dir)

        assert gate.conn is mock_conn
        assert gate.gate_process is mock_process
        assert gate.temp_dir == temp_dir

    def test_gate_field_access(self):
        """Test accessing Gate fields by name."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/field_access"

        gate = Gate(mock_conn, mock_process, temp_dir)

        # Test dot notation access
        assert gate.conn is mock_conn
        assert gate.gate_process is mock_process
        assert gate.temp_dir == temp_dir

        # Test getitem access (NamedTuple supports indexing)
        assert gate[0] is mock_conn
        assert gate[1] is mock_process
        assert gate[2] == temp_dir

    def test_gate_immutability(self):
        """Test that Gate fields cannot be modified (immutable)."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/immutable"

        gate = Gate(mock_conn, mock_process, temp_dir)

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            gate.conn = MagicMock()

        with pytest.raises(AttributeError):
            gate.gate_process = MagicMock()

        with pytest.raises(AttributeError):
            gate.temp_dir = "/new/path"

    def test_gate_equality(self):
        """Test Gate equality comparison."""
        mock_conn1 = MagicMock()
        mock_process1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_process2 = MagicMock()

        gate1 = Gate(mock_conn1, mock_process1, "/tmp/test")
        gate2 = Gate(mock_conn1, mock_process1, "/tmp/test")
        gate3 = Gate(mock_conn2, mock_process2, "/tmp/different")

        # Same objects should be equal
        assert gate1 == gate2

        # Different objects should not be equal
        assert gate1 != gate3

    def test_gate_string_representation(self):
        """Test Gate string representation."""
        mock_conn = MagicMock()
        mock_conn.__repr__ = MagicMock(return_value="<MockConn>")
        mock_process = MagicMock()
        mock_process.__repr__ = MagicMock(return_value="<MockProcess>")

        gate = Gate(mock_conn, mock_process, "/tmp/repr_test")

        gate_str = str(gate)
        assert "Gate" in gate_str
        assert "/tmp/repr_test" in gate_str

    def test_gate_tuple_operations(self):
        """Test Gate tuple-like operations."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/tuple_ops"

        gate = Gate(mock_conn, mock_process, temp_dir)

        # Test length
        assert len(gate) == 3

        # Test iteration
        items = list(gate)
        assert len(items) == 3
        assert items[0] is mock_conn
        assert items[1] is mock_process
        assert items[2] == temp_dir

        # Test unpacking
        conn, process, temp = gate
        assert conn is mock_conn
        assert process is mock_process
        assert temp == temp_dir

    def test_gate_field_names(self):
        """Test Gate field names and _fields attribute."""
        gate = Gate(None, None, None)

        # NamedTuple should have _fields attribute
        assert hasattr(gate, "_fields")
        assert gate._fields == ("conn", "gate_process", "temp_dir")

    def test_gate_asdict(self):
        """Test converting Gate to dictionary."""
        mock_conn = MagicMock()
        mock_process = MagicMock()
        temp_dir = "/tmp/asdict"

        gate = Gate(mock_conn, mock_process, temp_dir)

        # NamedTuple should have _asdict method
        gate_dict = gate._asdict()

        assert isinstance(gate_dict, dict)
        assert gate_dict["conn"] is mock_conn
        assert gate_dict["gate_process"] is mock_process
        assert gate_dict["temp_dir"] == temp_dir

    def test_gate_replace(self):
        """Test Gate _replace method for creating modified copies."""
        mock_conn1 = MagicMock()
        mock_process1 = MagicMock()
        mock_conn2 = MagicMock()

        gate1 = Gate(mock_conn1, mock_process1, "/tmp/original")

        # Replace one field
        gate2 = gate1._replace(conn=mock_conn2)

        assert gate2.conn is mock_conn2
        assert gate2.gate_process is mock_process1  # Unchanged
        assert gate2.temp_dir == "/tmp/original"  # Unchanged

        # Original should be unchanged
        assert gate1.conn is mock_conn1

        # Replace multiple fields
        gate3 = gate1._replace(conn=mock_conn2, temp_dir="/tmp/new")

        assert gate3.conn is mock_conn2
        assert gate3.gate_process is mock_process1
        assert gate3.temp_dir == "/tmp/new"


class TestGateTypeAnnotations:
    """Tests for Gate type annotations and hints."""

    def test_gate_type_hints(self):
        """Test that Gate has proper type hints."""
        type_hints = get_type_hints(Gate)

        assert "conn" in type_hints
        assert "gate_process" in type_hints
        assert "temp_dir" in type_hints

        # Check the actual types (imported in types.py)
        from asyncssh.connection import SSHClientConnection
        from asyncssh.process import SSHClientProcess

        assert type_hints["conn"] == SSHClientConnection
        assert type_hints["gate_process"] == SSHClientProcess
        assert type_hints["temp_dir"] is str


class TestGateIntegration:
    """Integration tests for Gate with mock SSH objects."""

    def test_gate_with_realistic_mock_objects(self):
        """Test Gate with more realistic mock SSH objects."""
        # Create more detailed mocks
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_transport.return_value = MagicMock()

        mock_process = MagicMock()
        mock_process.exit_status = None
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        temp_dir = "/tmp/ftl_gate_12345"

        gate = Gate(mock_conn, mock_process, temp_dir)

        # Test that the gate preserves the mock behavior
        assert gate.conn.is_connected() is True
        assert gate.gate_process.exit_status is None
        assert gate.temp_dir == temp_dir

    def test_gate_creation_with_different_temp_dir_formats(self):
        """Test Gate with various temp directory formats."""
        mock_conn = MagicMock()
        mock_process = MagicMock()

        test_cases = [
            "/tmp/ftl_gate_123",
            "/var/tmp/gate",
            "C:\\Temp\\ftl_gate",
            "/tmp/gate with spaces",
            "/tmp/unicode_path_🚀",
            "",  # Empty string
        ]

        for temp_dir in test_cases:
            gate = Gate(mock_conn, mock_process, temp_dir)
            assert gate.temp_dir == temp_dir

    def test_gate_comparison_with_different_objects(self):
        """Test Gate comparison with various object types."""
        mock_conn = MagicMock()
        mock_process = MagicMock()

        gate = Gate(mock_conn, mock_process, "/tmp/test")

        # NamedTuple is equal to regular tuple with same values (Python behavior)
        assert gate == (mock_conn, mock_process, "/tmp/test")  # Regular tuple
        assert gate != {
            "conn": mock_conn,
            "gate_process": mock_process,
            "temp_dir": "/tmp/test",
        }  # Dict
        assert gate is not None
        assert gate != "string"
        assert gate != 123

    def test_gate_hashability(self):
        """Test that Gate can be used as dictionary keys (hashable)."""
        mock_conn1 = MagicMock()
        mock_process1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_process2 = MagicMock()

        gate1 = Gate(mock_conn1, mock_process1, "/tmp/test1")
        gate2 = Gate(mock_conn2, mock_process2, "/tmp/test2")

        # Should be able to use as dict keys
        gate_dict = {gate1: "first_gate", gate2: "second_gate"}

        assert gate_dict[gate1] == "first_gate"
        assert gate_dict[gate2] == "second_gate"

        # Should be able to use in sets
        gate_set = {gate1, gate2}
        assert len(gate_set) == 2
        assert gate1 in gate_set
        assert gate2 in gate_set


class TestGateEdgeCases:
    """Tests for Gate edge cases and error scenarios."""

    def test_gate_with_complex_objects(self):
        """Test Gate with complex nested objects."""
        # Create complex mock objects
        mock_conn = MagicMock()
        mock_conn.nested_attr = {"key": "value", "list": [1, 2, 3]}

        mock_process = MagicMock()
        mock_process.complex_data = {
            "status": "running",
            "metadata": {"created": "2023-01-01", "tags": ["test", "integration"]},
        }

        gate = Gate(mock_conn, mock_process, "/tmp/complex")

        # Should preserve complex nested structures
        assert gate.conn.nested_attr["key"] == "value"
        assert gate.gate_process.complex_data["status"] == "running"
        assert len(gate.gate_process.complex_data["metadata"]["tags"]) == 2

    def test_gate_memory_usage(self):
        """Test Gate memory characteristics."""
        mock_conn = MagicMock()
        mock_process = MagicMock()

        gate1 = Gate(mock_conn, mock_process, "/tmp/memory1")
        gate2 = Gate(mock_conn, mock_process, "/tmp/memory2")

        # Same object references should be preserved
        assert gate1.conn is gate2.conn
        assert gate1.gate_process is gate2.gate_process

        # Different temp_dir strings
        assert gate1.temp_dir != gate2.temp_dir

    def test_gate_with_none_and_empty_values(self):
        """Test Gate with various None and empty values."""
        test_cases = [
            (None, None, None),
            (None, None, ""),
            (None, None, "/tmp/test"),
            (MagicMock(), None, ""),
            (None, MagicMock(), "/tmp/test"),
        ]

        for conn, process, temp_dir in test_cases:
            gate = Gate(conn, process, temp_dir)
            assert gate.conn is conn
            assert gate.gate_process is process
            assert gate.temp_dir == temp_dir
