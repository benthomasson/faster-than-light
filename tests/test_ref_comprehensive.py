"""
Comprehensive unit tests for faster_than_light.ref module.

Tests the reference system including the Ref class and all associated
functions for building and dereferencing nested attribute paths.
"""

from unittest.mock import MagicMock, patch

import pytest

from faster_than_light.ref import Ref, deref, get_host_path, get_host_value


class TestRef:
    """Tests for the Ref class."""

    def test_ref_constructor(self):
        """Test Ref constructor with parent and name."""
        parent = Ref(None, "root")
        child = Ref(parent, "child")

        assert child._parent is parent
        assert child._name == "child"

    def test_ref_constructor_no_parent(self):
        """Test Ref constructor with no parent (root ref)."""
        root = Ref(None, "root")

        assert root._parent is None
        assert root._name == "root"

    def test_ref_getattr_creates_child_ref(self):
        """Test that __getattr__ creates child Ref objects."""
        root = Ref(None, "root")
        child = root.child

        assert isinstance(child, Ref)
        assert child._parent is root
        assert child._name == "child"

    def test_ref_getattr_caches_attribute(self):
        """Test that __getattr__ caches created attributes."""
        root = Ref(None, "root")
        child1 = root.child
        child2 = root.child

        # Should be the same object (cached)
        assert child1 is child2

    def test_ref_nested_attributes(self):
        """Test creating deeply nested Ref structures."""
        root = Ref(None, "root")
        deep_ref = root.level1.level2.level3.level4

        assert isinstance(deep_ref, Ref)
        assert deep_ref._name == "level4"
        assert deep_ref._parent._name == "level3"
        assert deep_ref._parent._parent._name == "level2"
        assert deep_ref._parent._parent._parent._name == "level1"
        assert deep_ref._parent._parent._parent._parent is root

    def test_ref_multiple_children(self):
        """Test creating multiple child references."""
        root = Ref(None, "root")
        child1 = root.first_child
        child2 = root.second_child
        child3 = root.third_child

        assert child1._name == "first_child"
        assert child2._name == "second_child"
        assert child3._name == "third_child"

        assert child1._parent is root
        assert child2._parent is root
        assert child3._parent is root

    def test_ref_different_name_types(self):
        """Test Ref with different name types."""
        # String names
        ref1 = Ref(None, "string_name")
        assert ref1._name == "string_name"

        # Integer names (though unusual, should work)
        ref2 = Ref(None, 123)
        assert ref2._name == 123

        # None name
        ref3 = Ref(None, None)
        assert ref3._name is None

    def test_ref_complex_tree_structure(self):
        """Test building a complex tree-like reference structure."""
        root = Ref(None, "root")

        # Build a tree structure
        user = root.user
        config = root.config

        user_name = user.name
        user_email = user.email
        user_prefs = user.preferences

        config_db = config.database
        config_cache = config.cache

        db_host = config_db.host
        db_port = config_db.port

        # Verify structure
        assert user_name._parent is user
        assert user_email._parent is user
        assert user_prefs._parent is user

        assert config_db._parent is config
        assert config_cache._parent is config

        assert db_host._parent is config_db
        assert db_port._parent is config_db


class TestGetHostPath:
    """Tests for get_host_path function."""

    def test_get_host_path_single_level(self):
        """Test getting path for single-level reference."""
        root = Ref(None, "root")
        child = root.attribute

        path = get_host_path(child)

        assert path == ["attribute"]

    def test_get_host_path_multiple_levels(self):
        """Test getting path for multi-level reference."""
        root = Ref(None, "root")
        deep_ref = root.level1.level2.level3

        path = get_host_path(deep_ref)

        assert path == ["level1", "level2", "level3"]

    def test_get_host_path_deeply_nested(self):
        """Test getting path for deeply nested reference."""
        root = Ref(None, "root")
        deep_ref = root.a.b.c.d.e.f.g.h.i.j

        path = get_host_path(deep_ref)

        expected = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        assert path == expected

    def test_get_host_path_root_reference(self):
        """Test getting path for root reference (no parent)."""
        root = Ref(None, "root")

        path = get_host_path(root)

        assert path == []

    def test_get_host_path_preserves_order(self):
        """Test that path preserves correct order from root to leaf."""
        root = Ref(None, "root")
        ref = root.first.second.third.fourth

        path = get_host_path(ref)

        # Should be in order from root to leaf
        assert path == ["first", "second", "third", "fourth"]

    def test_get_host_path_different_name_types(self):
        """Test getting path with different name types."""
        root = Ref(None, "root")
        # Manually create refs with different name types
        ref1 = Ref(root, "string")
        ref2 = Ref(ref1, 123)
        ref3 = Ref(ref2, None)

        path = get_host_path(ref3)

        assert path == ["string", 123, None]


class TestGetHostValue:
    """Tests for get_host_value function."""

    def test_get_host_value_single_level(self):
        """Test getting value from single-level path."""
        host = {"name": "Alice", "age": 30}
        path = ["name"]

        result = get_host_value(host, path)

        assert result == "Alice"

    def test_get_host_value_multiple_levels(self):
        """Test getting value from multi-level path."""
        host = {"user": {"profile": {"name": "Alice", "age": 30}}}
        path = ["user", "profile", "name"]

        result = get_host_value(host, path)

        assert result == "Alice"

    def test_get_host_value_deeply_nested(self):
        """Test getting value from deeply nested structure."""
        host = {"a": {"b": {"c": {"d": {"e": "deep_value"}}}}}
        path = ["a", "b", "c", "d", "e"]

        result = get_host_value(host, path)

        assert result == "deep_value"

    def test_get_host_value_empty_path(self):
        """Test getting value with empty path returns host itself."""
        host = {"key": "value"}
        path = []

        result = get_host_value(host, path)

        assert result is host

    def test_get_host_value_different_data_types(self):
        """Test getting different data types from host."""
        host = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        assert get_host_value(host, ["string"]) == "text"
        assert get_host_value(host, ["integer"]) == 42
        assert get_host_value(host, ["float"]) == 3.14
        assert get_host_value(host, ["boolean"]) is True
        assert get_host_value(host, ["none"]) is None
        assert get_host_value(host, ["list"]) == [1, 2, 3]
        assert get_host_value(host, ["dict"]) == {"nested": "value"}

    def test_get_host_value_nested_different_types(self):
        """Test getting values from nested structures with different types."""
        host = {
            "config": {
                "database": {
                    "port": 5432,
                    "enabled": True,
                    "hosts": ["db1", "db2", "db3"],
                }
            }
        }

        assert get_host_value(host, ["config", "database", "port"]) == 5432
        assert get_host_value(host, ["config", "database", "enabled"]) is True
        assert get_host_value(host, ["config", "database", "hosts"]) == [
            "db1",
            "db2",
            "db3",
        ]

    def test_get_host_value_key_error(self):
        """Test that KeyError is raised for missing keys."""
        host = {"existing": "value"}
        path = ["nonexistent"]

        with pytest.raises(KeyError):
            get_host_value(host, path)

    def test_get_host_value_nested_key_error(self):
        """Test that KeyError is raised for missing nested keys."""
        host = {"level1": {"level2": {"existing": "value"}}}
        path = ["level1", "level2", "nonexistent"]

        with pytest.raises(KeyError):
            get_host_value(host, path)

    def test_get_host_value_type_error(self):
        """Test that TypeError is raised when trying to access non-dict."""
        host = {"string_value": "not a dict"}
        path = ["string_value", "attribute"]

        with pytest.raises(TypeError):
            get_host_value(host, path)


class TestDeref:
    """Tests for deref function."""

    def test_deref_with_ref_object(self):
        """Test dereferencing a Ref object."""
        host = {"user": {"name": "Alice"}}

        root = Ref(None, "root")
        ref = root.user.name

        result = deref(host, ref)

        assert result == "Alice"

    def test_deref_with_non_ref_value(self):
        """Test deref returns non-Ref values unchanged."""
        host = {"key": "value"}

        # Test different types of non-Ref values
        assert deref(host, "string") == "string"
        assert deref(host, 42) == 42
        assert deref(host, 3.14) == 3.14
        assert deref(host, True) is True
        assert deref(host, None) is None
        assert deref(host, [1, 2, 3]) == [1, 2, 3]
        assert deref(host, {"key": "value"}) == {"key": "value"}

    def test_deref_complex_nested_ref(self):
        """Test dereferencing complex nested Ref structures."""
        host = {
            "application": {
                "database": {
                    "connection": {
                        "host": "localhost",
                        "port": 5432,
                        "credentials": {"username": "admin", "password": "secret"},
                    }
                }
            }
        }

        root = Ref(None, "root")
        host_ref = root.application.database.connection.host
        port_ref = root.application.database.connection.port
        username_ref = root.application.database.connection.credentials.username

        assert deref(host, host_ref) == "localhost"
        assert deref(host, port_ref) == 5432
        assert deref(host, username_ref) == "admin"

    def test_deref_multiple_refs_same_host(self):
        """Test dereferencing multiple different refs against same host."""
        host = {
            "config": {
                "app_name": "MyApp",
                "version": "1.0.0",
                "features": {"auth": True, "logging": False},
            }
        }

        root = Ref(None, "root")
        name_ref = root.config.app_name
        version_ref = root.config.version
        auth_ref = root.config.features.auth
        logging_ref = root.config.features.logging

        assert deref(host, name_ref) == "MyApp"
        assert deref(host, version_ref) == "1.0.0"
        assert deref(host, auth_ref) is True
        assert deref(host, logging_ref) is False

    def test_deref_with_ref_key_error(self):
        """Test deref propagates KeyError from missing keys."""
        host = {"existing": "value"}

        root = Ref(None, "root")
        ref = root.nonexistent

        with pytest.raises(KeyError):
            deref(host, ref)

    def test_deref_with_ref_type_error(self):
        """Test deref propagates TypeError from invalid access."""
        host = {"string_value": "not a dict"}

        root = Ref(None, "root")
        ref = root.string_value.attribute

        with pytest.raises(TypeError):
            deref(host, ref)

    def test_deref_different_ref_instances(self):
        """Test deref works with different Ref instances for same path."""
        host = {"data": {"value": "test"}}

        # Create two different Ref instances with same path
        root1 = Ref(None, "root1")
        ref1 = root1.data.value

        root2 = Ref(None, "root2")
        ref2 = root2.data.value

        # Both should resolve to same value despite different root names
        assert deref(host, ref1) == "test"
        assert deref(host, ref2) == "test"

    def test_deref_integration_with_isinstance_check(self):
        """Test that deref correctly identifies Ref objects."""
        host = {"key": "value"}

        root = Ref(None, "root")
        ref = root.key

        # Verify isinstance check works as expected
        assert isinstance(ref, Ref)
        assert not isinstance("not_a_ref", Ref)
        assert not isinstance(42, Ref)
        assert not isinstance({"dict": "value"}, Ref)


class TestRefIntegration:
    """Integration tests combining all ref functionality."""

    def test_full_ref_workflow(self):
        """Test complete workflow from creating refs to dereferencing."""
        # Create complex host data
        host = {
            "server": {
                "config": {
                    "database": {
                        "host": "db.example.com",
                        "port": 5432,
                        "name": "production",
                    },
                    "cache": {"redis": {"host": "cache.example.com", "port": 6379}},
                }
            },
            "application": {
                "name": "WebApp",
                "version": "2.1.0",
                "features": ["auth", "logging", "metrics"],
            },
        }

        # Create references
        root = Ref(None, "config")
        db_host_ref = root.server.config.database.host
        db_port_ref = root.server.config.database.port
        redis_host_ref = root.server.config.cache.redis.host
        app_name_ref = root.application.name
        features_ref = root.application.features

        # Test path extraction
        assert get_host_path(db_host_ref) == ["server", "config", "database", "host"]
        assert get_host_path(redis_host_ref) == [
            "server",
            "config",
            "cache",
            "redis",
            "host",
        ]
        assert get_host_path(app_name_ref) == ["application", "name"]

        # Test direct value access
        assert (
            get_host_value(host, ["server", "config", "database", "host"])
            == "db.example.com"
        )
        assert get_host_value(host, ["application", "name"]) == "WebApp"

        # Test dereferencing
        assert deref(host, db_host_ref) == "db.example.com"
        assert deref(host, db_port_ref) == 5432
        assert deref(host, redis_host_ref) == "cache.example.com"
        assert deref(host, app_name_ref) == "WebApp"
        assert deref(host, features_ref) == ["auth", "logging", "metrics"]

        # Test non-ref values
        assert deref(host, "literal_string") == "literal_string"
        assert deref(host, 12345) == 12345

    def test_ansible_style_variable_refs(self):
        """Test refs that mimic Ansible-style variable references."""
        # Ansible-style host data
        host = {
            "ansible_host": "192.168.1.100",
            "ansible_user": "deploy",
            "ansible_ssh_port": 22,
            "group_vars": {"webservers": {"http_port": 80, "https_port": 443}},
            "host_vars": {"web1": {"server_id": 1, "role": "primary"}},
        }

        # Create Ansible-style references
        root = Ref(None, "hostvars")

        # Basic host variables
        host_ip = root.ansible_host
        ssh_user = root.ansible_user
        ssh_port = root.ansible_ssh_port

        # Group variables
        http_port = root.group_vars.webservers.http_port
        https_port = root.group_vars.webservers.https_port

        # Host-specific variables
        server_id = root.host_vars.web1.server_id
        server_role = root.host_vars.web1.role

        # Test dereferencing
        assert deref(host, host_ip) == "192.168.1.100"
        assert deref(host, ssh_user) == "deploy"
        assert deref(host, ssh_port) == 22
        assert deref(host, http_port) == 80
        assert deref(host, https_port) == 443
        assert deref(host, server_id) == 1
        assert deref(host, server_role) == "primary"

    def test_ref_caching_and_reuse(self):
        """Test that refs are properly cached and can be reused."""
        host = {"config": {"value": "cached_test"}}

        root = Ref(None, "root")

        # Access same path multiple times
        ref1 = root.config.value
        ref2 = root.config.value
        ref3 = root.config.value

        # Should be same cached object
        assert ref1 is ref2
        assert ref2 is ref3

        # All should dereference to same value
        assert deref(host, ref1) == "cached_test"
        assert deref(host, ref2) == "cached_test"
        assert deref(host, ref3) == "cached_test"

    def test_error_propagation_through_deref(self):
        """Test that errors are properly propagated through the deref chain."""
        # Test KeyError propagation
        host_missing_key = {"existing": "value"}
        root = Ref(None, "root")
        missing_ref = root.nonexistent.key

        with pytest.raises(KeyError):
            deref(host_missing_key, missing_ref)

        # Test TypeError propagation
        host_type_error = {"string": "not_a_dict"}
        type_error_ref = root.string.invalid_access

        with pytest.raises(TypeError):
            deref(host_type_error, type_error_ref)
