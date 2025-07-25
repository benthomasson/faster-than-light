"""
Unit tests for faster_than_light.exceptions module.

Tests custom exception classes.
"""

import pytest
from faster_than_light.exceptions import ModuleNotFound, ProtocolError


class TestModuleNotFound:
    """Tests for ModuleNotFound exception."""
    
    def test_module_not_found_creation_no_message(self):
        """Test creating ModuleNotFound without message."""
        exc = ModuleNotFound()
        assert isinstance(exc, Exception)
        assert isinstance(exc, ModuleNotFound)
        assert str(exc) == ""
    
    def test_module_not_found_creation_with_message(self):
        """Test creating ModuleNotFound with message."""
        message = "Module 'test_module' not found in directories"
        exc = ModuleNotFound(message)
        assert str(exc) == message
        assert exc.args == (message,)
    
    def test_module_not_found_inheritance(self):
        """Test ModuleNotFound inheritance hierarchy."""
        exc = ModuleNotFound("test")
        assert isinstance(exc, Exception)
        assert isinstance(exc, ModuleNotFound)
        assert issubclass(ModuleNotFound, Exception)
    
    def test_module_not_found_raising_and_catching(self):
        """Test raising and catching ModuleNotFound."""
        message = "Test module not found"
        
        with pytest.raises(ModuleNotFound) as exc_info:
            raise ModuleNotFound(message)
        
        assert str(exc_info.value) == message
        assert exc_info.type is ModuleNotFound


class TestProtocolError:
    """Tests for ProtocolError exception."""
    
    def test_protocol_error_creation_no_message(self):
        """Test creating ProtocolError without message."""
        exc = ProtocolError()
        assert isinstance(exc, Exception)
        assert isinstance(exc, ProtocolError)
        assert str(exc) == ""
    
    def test_protocol_error_creation_with_message(self):
        """Test creating ProtocolError with message."""
        message = "Invalid protocol message format"
        exc = ProtocolError(message)
        assert str(exc) == message
        assert exc.args == (message,)
    
    def test_protocol_error_inheritance(self):
        """Test ProtocolError inheritance hierarchy."""
        exc = ProtocolError("test")
        assert isinstance(exc, Exception)
        assert isinstance(exc, ProtocolError)
        assert issubclass(ProtocolError, Exception)
    
    def test_protocol_error_raising_and_catching(self):
        """Test raising and catching ProtocolError."""
        message = "Invalid message length"
        
        with pytest.raises(ProtocolError) as exc_info:
            raise ProtocolError(message)
        
        assert str(exc_info.value) == message
        assert exc_info.type is ProtocolError


class TestExceptionTypes:
    """Tests for exception type distinctions."""
    
    def test_exceptions_are_distinct_types(self):
        """Test that ModuleNotFound and ProtocolError are distinct."""
        module_exc = ModuleNotFound("Module error")
        protocol_exc = ProtocolError("Protocol error")
        
        assert type(module_exc) != type(protocol_exc)
        assert not isinstance(module_exc, ProtocolError)
        assert not isinstance(protocol_exc, ModuleNotFound)
    
    def test_module_not_found_in_function(self):
        """Test ModuleNotFound in a typical function scenario."""
        def find_module(module_name, search_paths):
            for path in search_paths:
                if f"{path}/{module_name}" == "/found/test_module":
                    return f"{path}/{module_name}"
            raise ModuleNotFound(f"Module '{module_name}' not found in {search_paths}")
        
        # Should find module
        result = find_module("test_module", ["/found", "/other"])
        assert result == "/found/test_module"
        
        # Should raise ModuleNotFound
        with pytest.raises(ModuleNotFound) as exc_info:
            find_module("missing_module", ["/path1", "/path2"])
        
        assert "missing_module" in str(exc_info.value)
        assert "/path1" in str(exc_info.value)
    
    def test_protocol_error_in_parsing(self):
        """Test ProtocolError in a typical parsing scenario."""
        def parse_message(data):
            if not isinstance(data, bytes):
                raise ProtocolError(f"Expected bytes, got {type(data)}")
            
            if len(data) < 8:
                raise ProtocolError(f"Message too short: {len(data)} bytes, minimum 8")
            
            return {"parsed": True}
        
        # Should parse valid message
        valid_data = b"12345678extra"
        result = parse_message(valid_data)
        assert result == {"parsed": True}
        
        # Should raise ProtocolError for wrong type
        with pytest.raises(ProtocolError, match="Expected bytes"):
            parse_message("string data")
        
        # Should raise ProtocolError for short message
        with pytest.raises(ProtocolError, match="Message too short"):
            parse_message(b"short") 