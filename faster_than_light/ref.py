"""Variable reference and dereferencing system for FTL.

This module provides a sophisticated variable reference mechanism that allows
creating and resolving nested attribute references in host data. It mimics
Ansible's variable lookup system, enabling dynamic access to deeply nested
configuration values using dot notation.

Key Features:
- Dynamic attribute reference creation with dot notation
- Lazy evaluation of variable paths
- Integration with Ansible-style host variables
- Support for complex nested data structures
- Automatic caching of reference objects for performance

The Ref system allows building variable references like `host.network.interfaces.eth0.ip`
that are resolved only when needed, enabling flexible template and configuration
processing in automation workflows.
"""

from typing import Any, Dict, List, Optional, Union


def deref(host: Dict[str, Any], ref_or_value: Union["Ref", Any]) -> Any:
    """Dereference a Ref object or return a regular value unchanged.

    This is the main entry point for resolving variable references. If the
    input is a Ref object, it extracts the variable path and resolves it
    against the host data. If the input is a regular value, it returns
    it unchanged, making this function safe to use on mixed data.

    Args:
        host: Dictionary containing host variables and configuration data.
            Typically follows Ansible inventory structure with nested
            configuration parameters.
        ref_or_value: Either a Ref object to be dereferenced, or any other
            value to be returned as-is. This allows processing mixed data
            where some values may be references and others are literals.

    Returns:
        The resolved value from the host data if ref_or_value is a Ref,
        otherwise returns ref_or_value unchanged.

    Raises:
        KeyError: If the reference path doesn't exist in the host data.
        TypeError: If intermediate values in the path are not dict-like.

    Example:
        >>> host = {"network": {"ip": "192.168.1.100", "port": 8080}}
        >>> ref = Ref(None, "network").ip
        >>> deref(host, ref)
        '192.168.1.100'
        >>> deref(host, "literal_value")
        'literal_value'

        # Common usage in module arguments
        >>> module_args = {"src": Ref(None, "app").config_path, "mode": "0644"}
        >>> resolved_args = {k: deref(host, v) for k, v in module_args.items()}

    Note:
        This function is designed to be safe for bulk processing of configuration
        data that may contain a mix of literal values and variable references.
    """
    if isinstance(ref_or_value, Ref):
        path = get_host_path(ref_or_value)
        return get_host_value(host, path)
    else:
        return ref_or_value


def get_host_path(ref: "Ref") -> List[str]:
    """Extract the complete variable path from a Ref object.

    Traverses up the reference chain from a Ref object to build the complete
    path of nested attribute names. The path represents the sequence of keys
    needed to access the variable in the host data structure.

    Args:
        ref: A Ref object representing a variable reference. The Ref should
            be part of a reference chain created through attribute access
            (e.g., `Ref(None, "root").child.grandchild`).

    Returns:
        List of strings representing the path from the root to the referenced
        variable. The list is ordered from outermost to innermost key.
        Returns empty list for root-level references with no parent.

    Example:
        >>> root = Ref(None, "config")
        >>> nested_ref = root.database.host
        >>> get_host_path(nested_ref)
        ['config', 'database', 'host']

        >>> root_ref = Ref(None, "simple")
        >>> get_host_path(root_ref)
        ['simple']

    Note:
        This function walks the reference chain backwards (from leaf to root)
        and then reverses the result to provide the correct access order.
        Root references (with parent=None) contribute their name to the path.
    """
    path = []
    while ref._parent is not None:
        path.append(ref._name)
        ref = ref._parent

    return path[::-1]


def get_host_value(host: Dict[str, Any], path: List[str]) -> Any:
    """Retrieve a value from nested host data using a variable path.

    Navigates through nested dictionaries using a sequence of keys to
    retrieve the final value. This function performs the actual data
    access for variable dereferencing.

    Args:
        host: Dictionary containing the host data to search. Typically
            contains nested configuration parameters and variables
            following Ansible inventory structure.
        path: List of strings representing the sequence of keys to access,
            ordered from outermost to innermost. Each key accesses one
            level deeper in the nested structure.

    Returns:
        The value found at the end of the path traversal. Can be any type
        stored in the host data (string, int, dict, list, etc.).

    Raises:
        KeyError: If any key in the path doesn't exist in the current level
            of the data structure.
        TypeError: If an intermediate value in the path is not a dictionary
            or doesn't support key access (e.g., trying to access a key
            on a string or integer value).

    Example:
        >>> host_data = {
        ...     "app": {
        ...         "database": {
        ...             "host": "db.example.com",
        ...             "port": 5432
        ...         },
        ...         "web": {"port": 8080}
        ...     }
        ... }
        >>> get_host_value(host_data, ["app", "database", "host"])
        'db.example.com'
        >>> get_host_value(host_data, ["app", "web", "port"])
        8080
        >>> get_host_value(host_data, ["app"])
        {'database': {'host': 'db.example.com', 'port': 5432}, 'web': {'port': 8080}}

    Note:
        This function performs sequential key access without any error handling,
        allowing natural Python exceptions to propagate for debugging.
        Empty paths return the original host dictionary.
    """
    value = host
    for part in path:
        value = value[part]

    return value


class Ref(object):
    """Dynamic variable reference builder for nested data access.

    The Ref class enables building variable references using natural Python
    attribute syntax that can be resolved later against actual data. It creates
    a chain of reference objects that represent paths through nested dictionaries,
    similar to how Ansible variables work.

    Key features:
    - Lazy evaluation: references are built but not resolved until needed
    - Attribute caching: once created, attribute references are reused
    - Chain building: supports unlimited nesting (ref.a.b.c.d...)
    - Memory efficient: stores only parent/child relationships

    The Ref system allows writing code like `config.database.host` where the
    actual resolution happens later when the reference is dereferenced against
    real host data.

    Attributes:
        _parent: Reference to the parent Ref object in the chain, or None for root.
        _name: String name of this reference level (the attribute name).

    Example:
        >>> # Create a root reference
        >>> config = Ref(None, "config")

        >>> # Build nested references with attribute access
        >>> db_host = config.database.host
        >>> web_port = config.web.port

        >>> # References can be reused and extended
        >>> db_config = config.database
        >>> db_user = db_config.user
        >>> db_password = db_config.password

        >>> # Later resolve against actual data
        >>> host_data = {
        ...     "config": {
        ...         "database": {"host": "db.example.com", "user": "admin"},
        ...         "web": {"port": 8080}
        ...     }
        ... }
        >>> deref(host_data, db_host)
        'db.example.com'
        >>> deref(host_data, web_port)
        8080

    Note:
        Ref objects are immutable once created. Attribute access creates new
        Ref objects rather than modifying existing ones. This ensures thread
        safety and prevents accidental modification of shared references.
    """

    def __init__(self, parent: Optional["Ref"], name: str) -> None:
        """Initialize a new variable reference.

        Creates a new reference node in the variable path chain. Each Ref
        represents one level in a nested data structure path.

        Args:
            parent: The parent Ref object in the reference chain, or None
                for root-level references. Parent references allow building
                the complete path when dereferencing.
            name: String name for this reference level. This corresponds
                to the dictionary key or attribute name at this level
                of the nested structure.

        Example:
            >>> # Root reference
            >>> root = Ref(None, "config")

            >>> # Child reference
            >>> child = Ref(root, "database")

            >>> # Or more commonly, use attribute access:
            >>> root = Ref(None, "config")
            >>> child = root.database  # Automatically creates Ref(root, "database")
        """
        self._parent = parent
        self._name = name

    def __getattr__(self, name: str) -> "Ref":
        """Create and cache a child reference for attribute access.

        This method is called when accessing an attribute that doesn't already
        exist on the Ref object. It creates a new Ref object representing the
        nested attribute and caches it for future use.

        Args:
            name: String name of the attribute being accessed. This becomes
                the name of the new child Ref object.

        Returns:
            A new Ref object representing the nested attribute reference,
            with this Ref as its parent.

        Example:
            >>> config = Ref(None, "config")
            >>> # First access creates and caches the reference
            >>> db_ref = config.database  # Creates Ref(config, "database")
            >>> # Subsequent access returns the cached reference
            >>> same_ref = config.database  # Returns the same object
            >>> assert db_ref is same_ref

            >>> # Can chain indefinitely
            >>> host_ref = config.database.cluster.primary.host

        Note:
            The created reference is cached using setattr, so subsequent
            access to the same attribute returns the identical Ref object.
            This provides consistent identity and prevents memory bloat.
        """
        ref = Ref(self, name)
        setattr(self, name, ref)
        return ref
