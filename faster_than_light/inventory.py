"""Inventory management system for FTL automation framework.

This module provides comprehensive inventory management capabilities for FTL,
including loading Ansible-compatible YAML inventory files and generating
localhost-only inventory configurations. It follows Ansible inventory
conventions while providing FTL-specific optimizations and defaults.

Key Features:
- YAML inventory file loading with full Ansible compatibility
- Localhost inventory generation for local-only execution
- Configurable Python interpreter selection for localhost
- Automatic inventory file writing for quick setup
- Robust error handling for malformed inventory files
- Support for complex nested inventory structures

Inventory Structure Support:
- Standard Ansible inventory format (groups, hosts, vars)
- Host-specific variable definitions
- Group-level variable inheritance
- Connection-specific configuration (ansible_connection, etc.)
- Python interpreter configuration per host
- Local execution optimization with ansible_connection=local

The inventory system enables FTL to work seamlessly with existing Ansible
inventory files while providing convenient defaults for common use cases
like localhost-only automation and testing scenarios.
"""

import sys
from typing import Any, Optional

import yaml


def load_inventory(inventory_file: str) -> Any:
    """Load inventory data from an Ansible-compatible YAML file.

    Reads and parses a YAML inventory file following Ansible inventory format
    conventions. Supports all standard Ansible inventory features including
    groups, hosts, variables, and nested structures. Provides safe YAML loading
    to prevent code execution vulnerabilities.

    Args:
        inventory_file: Path to the YAML inventory file to load. Should be a
            readable file containing valid YAML inventory data in Ansible format.

    Returns:
        Dictionary containing the parsed inventory data with groups, hosts, and
        variables. Returns empty dictionary if the file is empty or contains
        only null values. Structure follows Ansible inventory conventions.

    Raises:
        FileNotFoundError: If the inventory file does not exist.
        PermissionError: If the inventory file cannot be read due to permissions.
        yaml.YAMLError: If the file contains invalid YAML syntax.
        UnicodeDecodeError: If the file contains non-UTF8 content.

    Example:
        >>> # Load a simple inventory
        >>> inventory = load_inventory("hosts.yml")
        >>> print(inventory['all']['hosts'])
        {'web01': {'ansible_host': '192.168.1.10'}, 'db01': {'ansible_host': '192.168.1.20'}}

        >>> # Load complex inventory with groups
        >>> inventory = load_inventory("production.yml")
        >>> print(inventory['webservers']['hosts'])
        {'web01': {...}, 'web02': {...}}
        >>> print(inventory['webservers']['vars'])
        {'http_port': 80, 'max_clients': 200}

        >>> # Load inventory with group hierarchy
        >>> inventory = load_inventory("staging.yml")
        >>> print(inventory['all']['children'])
        ['webservers', 'databases', 'loadbalancers']

    Inventory Format:
        The function expects standard Ansible YAML inventory format:

        ```yaml
        all:
          hosts:
            host1:
              ansible_host: 192.168.1.10
              ansible_user: admin
          children:
            webservers:
              hosts:
                web01:
                  ansible_host: 192.168.1.11
                web02:
                  ansible_host: 192.168.1.12
              vars:
                http_port: 80
            databases:
              hosts:
                db01:
                  ansible_host: 192.168.1.20
        ```

    Supported Features:
        - Host definitions with variables
        - Group definitions with host membership
        - Group variables and inheritance
        - Nested group structures (children)
        - Connection variables (ansible_host, ansible_user, etc.)
        - Custom host and group variables
        - Empty file handling (returns empty dict)

    Security:
        Uses yaml.safe_load() to prevent execution of arbitrary code during
        YAML parsing. This is essential when loading inventory files from
        untrusted sources or when security is a concern.

    Note:
        Returns an empty dictionary for files that are empty or contain only
        null/None values. This provides consistent behavior and prevents
        None return values that could cause issues in inventory processing.
    """

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data or {}


def load_localhost(interpreter: Optional[str] = None) -> Any:
    """Generate a localhost-only inventory configuration for local execution.

    Creates a minimal Ansible-compatible inventory containing only localhost
    configured for local execution. This is ideal for testing, development,
    or scenarios where automation tasks need to run only on the control node
    without SSH connections.

    Args:
        interpreter: Path to the Python interpreter to use for localhost
            execution. If None, uses sys.executable (current Python interpreter).
            Should be a valid path to a Python executable.

    Returns:
        Dictionary containing a complete Ansible inventory structure with
        localhost configured for local execution. Includes all necessary
        connection parameters for ansible_connection=local mode.

    Example:
        >>> # Generate localhost inventory with default interpreter
        >>> inventory = load_localhost()
        >>> print(inventory['all']['hosts']['localhost'])
        {'ansible_connection': 'local', 'ansible_python_interpreter': '/usr/bin/python3'}

        >>> # Generate localhost inventory with custom interpreter
        >>> inventory = load_localhost("/opt/python3.9/bin/python")
        >>> print(inventory['all']['hosts']['localhost']['ansible_python_interpreter'])
        /opt/python3.9/bin/python

        >>> # Use in FTL for local-only automation
        >>> inventory = load_localhost()
        >>> # FTL will execute modules locally without SSH
        >>> await run_module(inventory, "setup", {})

    Generated Structure:
        The returned inventory follows this structure:

        ```python
        {
            "all": {
                "hosts": {
                    "localhost": {
                        "ansible_connection": "local",
                        "ansible_python_interpreter": "/path/to/python"
                    }
                }
            }
        }
        ```

    Configuration Details:
        - Host: "localhost" - Standard localhost identifier
        - Connection: "local" - Bypasses SSH, executes directly
        - Interpreter: User-specified or sys.executable
        - Group: "all" - Standard Ansible top-level group

    Use Cases:
        - Development and testing on local machine
        - Control node automation tasks
        - Single-machine deployments
        - Testing FTL modules without remote infrastructure
        - CI/CD environments where tasks run on runner
        - Localhost configuration management

    Local Execution Benefits:
        - No SSH overhead or connection setup
        - Direct file system access
        - Faster execution for local tasks
        - Simplified debugging and development
        - No network dependencies
        - Full access to local environment

    Interpreter Selection:
        The function automatically selects an appropriate Python interpreter:
        - Custom interpreter: Uses provided path if specified
        - Default interpreter: Uses sys.executable (current Python)
        - Validation: Caller responsible for interpreter path validity
        - Consistency: Same interpreter used for inventory generation

    Integration:
        This inventory can be used anywhere FTL expects inventory data:
        - Direct use with run_module() functions
        - Writing to file with write_localhost()
        - Merging with other inventory sources
        - Testing and development workflows

    Note:
        The generated inventory is minimal but complete, containing only
        the essential configuration for localhost execution. Additional
        variables can be added by modifying the returned dictionary
        before use.
    """

    if interpreter is None:
        interpreter = sys.executable

    inventory_data = {
        "all": {
            "hosts": {
                "localhost": {
                    "ansible_connection": "local",
                    "ansible_python_interpreter": interpreter,
                }
            }
        }
    }

    return inventory_data


def write_localhost(inventory_file: str = "inventory.yml") -> None:
    """Write a localhost-only inventory configuration to a YAML file.

    Generates and writes a complete localhost inventory to a YAML file,
    creating an immediately usable Ansible-compatible inventory for local
    execution scenarios. Combines load_localhost() generation with file
    output in a single convenient function.

    Args:
        inventory_file: Path to the output YAML file. Defaults to "inventory.yml"
            in the current directory. File will be created or overwritten.
            Parent directories must exist.

    Returns:
        None. The function writes to a file and does not return data.

    Raises:
        PermissionError: If the file cannot be written due to permissions.
        FileNotFoundError: If the parent directory does not exist.
        OSError: If there are other filesystem issues during writing.
        yaml.YAMLError: If YAML serialization fails (unlikely for simple data).

    Example:
        >>> # Write default localhost inventory
        >>> write_localhost()
        >>> # Creates inventory.yml with localhost configuration

        >>> # Write to custom location
        >>> write_localhost("configs/local.yml")
        >>> # Creates configs/local.yml with localhost setup

        >>> # Generated file content example:
        >>> write_localhost("test.yml")
        >>> with open("test.yml") as f:
        ...     print(f.read())
        all:
          hosts:
            localhost:
              ansible_connection: local
              ansible_python_interpreter: /usr/bin/python3

    Generated File Format:
        The written YAML file contains a complete Ansible inventory:

        ```yaml
        all:
          hosts:
            localhost:
              ansible_connection: local
              ansible_python_interpreter: /path/to/python
        ```

    File Characteristics:
        - Format: Standard YAML with proper indentation
        - Encoding: UTF-8 (default for text files)
        - Structure: Ansible-compatible inventory format
        - Size: Minimal (typically < 200 bytes)
        - Compatibility: Works with ansible-playbook and FTL

    Use Cases:
        - Quick setup for new FTL projects
        - Creating localhost inventory for testing
        - Generating baseline inventory files
        - CI/CD pipeline initialization
        - Development environment setup
        - Localhost-only automation projects

    Integration Workflow:
        1. Call write_localhost() to create inventory file
        2. Use with FTL: ftl -i inventory.yml module_name args
        3. Use with Ansible: ansible-playbook -i inventory.yml playbook.yml
        4. Modify file as needed for additional hosts or variables

    File Management:
        - Overwrites existing files without warning
        - Creates new files if they don't exist
        - Requires write permissions to target directory
        - Does not create parent directories
        - Uses system default YAML formatting

    Configuration Source:
        The function uses load_localhost() to generate the inventory data:
        - Python interpreter: sys.executable (current Python)
        - Connection type: Local (no SSH)
        - Host name: localhost
        - Group membership: all group

    Post-Creation Usage:
        After file creation, you can:
        - Use directly with FTL command-line tools
        - Load with load_inventory() for programmatic use
        - Edit manually to add more hosts or variables
        - Version control the file for team collaboration
        - Copy as template for other inventory files

    Note:
        This is a convenience function that combines inventory generation
        and file writing. For more control over the inventory content,
        use load_localhost() to generate data and handle file writing
        manually with custom YAML formatting options.
    """
    with open(inventory_file, "w") as f:
        yaml.dump(load_localhost(), stream=f)


def entry_point() -> None:
    """Command-line entry point for inventory generation functionality.

    Provides a simple command-line interface for generating a default localhost
    inventory file. This function serves as the entry point when the inventory
    module is executed directly, creating a standard inventory.yml file in the
    current directory.

    Returns:
        None. Creates an inventory.yml file as a side effect.

    Raises:
        PermissionError: If the current directory is not writable.
        OSError: If there are filesystem issues during file creation.

    Example:
        >>> # Run from command line
        >>> python -m faster_than_light.inventory
        >>> # Creates inventory.yml in current directory

        >>> # Or call programmatically
        >>> from faster_than_light.inventory import entry_point
        >>> entry_point()
        >>> # Creates inventory.yml with localhost configuration

    Generated Output:
        Creates inventory.yml containing:

        ```yaml
        all:
          hosts:
            localhost:
              ansible_connection: local
              ansible_python_interpreter: /path/to/current/python
        ```

    Command-Line Usage:
        This entry point enables the module to be run directly:

        ```bash
        # Generate default localhost inventory
        python -m faster_than_light.inventory

        # Use the generated inventory with FTL
        ftl -i inventory.yml setup

        # Use with Ansible
        ansible-playbook -i inventory.yml playbook.yml
        ```

    Integration Points:
        - Package entry points in setup.py/pyproject.toml
        - CLI tools and wrapper scripts
        - Makefile targets for project setup
        - Docker container initialization
        - CI/CD pipeline setup scripts

    Workflow Integration:
        Common usage patterns:
        1. Project initialization: Create inventory for new FTL projects
        2. Testing setup: Generate inventory for test environments
        3. Development: Quick localhost inventory for development work
        4. CI/CD: Automated inventory generation in build pipelines

    File Behavior:
        - Always writes to "inventory.yml" in current directory
        - Overwrites existing inventory.yml without warning
        - Uses current Python interpreter path
        - Creates minimal but complete inventory structure

    Use Cases:
        - Quick project setup and initialization
        - Automated inventory generation in scripts
        - Default inventory creation for new users
        - CI/CD pipeline inventory bootstrapping
        - Development environment standardization

    Note:
        This is a convenience wrapper around write_localhost() with
        default parameters. For custom file names or locations, call
        write_localhost() directly with appropriate arguments.
    """
    write_localhost()
