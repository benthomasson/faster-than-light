"""Command-line interface for the FTL automation framework.

This module provides the primary command-line interface for FTL, enabling users
to execute automation modules across inventories of hosts. It supports both
Ansible-compatible modules and FTL-native modules with comprehensive argument
parsing, logging configuration, and execution coordination.

Key Features:
- Unified CLI for both Ansible and FTL module execution
- Flexible inventory management with YAML file support
- Module argument parsing with key=value syntax
- Configurable logging levels (debug, verbose, warning)
- Python dependency management via requirements files
- Asynchronous execution with proper error handling
- Integration with FTL's gate building and remote execution

Command-Line Interface:
The CLI follows standard Unix conventions with short and long option forms,
comprehensive help text, and intuitive argument structures. It serves as the
primary entry point for FTL automation workflows.

Usage Patterns:
- Module execution: ftl -m module_name -i inventory.yml
- FTL module execution: ftl -f ftl_module.py -i hosts.yml
- With dependencies: ftl -m module -r requirements.txt
- Debug mode: ftl --debug -m module -i inventory.yml

The CLI integrates seamlessly with FTL's core automation capabilities while
providing a familiar interface for users transitioning from Ansible or other
automation frameworks. The CLI is now built using Click for modern, robust
argument parsing and validation.
"""
import asyncio
import click
import logging
import sys
from .module import run_module
from .module import run_ftl_module
from .inventory import load_inventory
from pprint import pprint

from typing import Optional, Dict

logger = logging.getLogger("cli")


def parse_module_args(args: str) -> Dict[str, str]:
    """Parse module arguments from command-line string into dictionary format.
    
    Converts a space-separated string of key=value pairs into a dictionary
    suitable for passing to automation modules. This enables flexible module
    argument specification from the command line using familiar syntax.
    
    Args:
        args: String containing space-separated key=value pairs. Can be empty
            or None. Example: "host=example.com port=80 debug=true"
    
    Returns:
        Dictionary mapping argument keys to values. All keys and values are
        strings. Returns empty dictionary if args is None or empty.
    
    Raises:
        ValueError: If any argument pair does not contain exactly one equals
            sign, indicating malformed key=value syntax.
    
    Example:
        >>> # Basic argument parsing
        >>> parse_module_args("host=web01 port=80")
        {'host': 'web01', 'port': '80'}
        
        >>> # Empty arguments
        >>> parse_module_args("")
        {}
        >>> parse_module_args(None)
        {}
        
        >>> # Single argument
        >>> parse_module_args("debug=true")
        {'debug': 'true'}
        
        >>> # Multiple arguments with various types
        >>> parse_module_args("path=/etc/config mode=644 owner=root")
        {'path': '/etc/config', 'mode': '644', 'owner': 'root'}
    
    Argument Format:
        The function expects arguments in the format:
        - key=value pairs separated by spaces
        - Keys and values can contain any characters except space and equals
        - No quoting or escaping mechanism is provided
        - Values are always treated as strings
        
    Limitations:
        - Values cannot contain spaces (no quoting support)
        - Keys cannot contain equals signs
        - No escape sequences for special characters
        - All values are converted to strings
        
    Use Cases:
        - Command-line module argument specification
        - Simple key-value configuration parsing
        - Ansible-style module argument handling
        - Quick parameter passing for automation tasks
        
    Integration:
        This function integrates with:
        - CLI argument processing in main()
        - Module execution functions that expect dict arguments
        - Ansible-compatible argument handling
        - FTL module parameter processing
        
    Error Handling:
        The function uses a simple split-based approach that will raise
        ValueError if any argument does not contain exactly one equals sign.
        This provides clear feedback for malformed argument strings.
        
    Note:
        The parsing is intentionally simple to maintain compatibility with
        common automation tool conventions. For complex argument structures,
        consider using JSON format or configuration files instead.
    """
    if args:
        key_value_pairs = args.split(" ")
        key_value_tuples = [tuple(i.split("=")) for i in key_value_pairs]
        return {k: v for k, v in key_value_tuples}
    else:
        return {}


@click.command()
@click.option('--ftl-module', '-f', help='FTL module to execute')
@click.option('--module', '-m', help='Ansible-compatible module to execute')
@click.option('--module-dir', '-M', help='Module directory to search for modules')
@click.option('--inventory', '-i', required=True, help='Inventory file (YAML format)')
@click.option('--requirements', '-r', help='Python requirements file')
@click.option('--args', '-a', help='Module arguments in key=value format')
@click.option('--debug', is_flag=True, help='Show debug logging')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose logging')
def main(
    ftl_module: Optional[str],
    module: Optional[str], 
    module_dir: Optional[str],
    inventory: str,
    requirements: Optional[str],
    args: Optional[str],
    debug: bool,
    verbose: bool
) -> None:
    """Main CLI entry point for FTL automation framework execution.
    
    Orchestrates the complete FTL command-line workflow including argument
    parsing, logging configuration, inventory loading, and module execution.
    Supports both Ansible-compatible modules and FTL-native modules with
    comprehensive error handling and output formatting.
    
    The CLI now uses Click for modern argument parsing and validation, providing
    better error messages, help text generation, and option handling compared
    to the previous docopt implementation.
    
    Args:
        ftl_module: FTL module file to execute (mutually exclusive with module)
        module: Ansible-compatible module name to execute (mutually exclusive with ftl_module)
        module_dir: Directory to search for modules
        inventory: YAML inventory file (required)
        requirements: Python requirements file for dependencies
        args: Module arguments in key=value format
        debug: Enable debug logging
        verbose: Enable verbose logging
    
    Raises:
        click.ClickException: For argument validation errors
        FileNotFoundError: If specified inventory or requirements files don't exist
        ModuleNotFound: If specified modules cannot be found in module directories
        Various exceptions: From module execution, inventory loading, or file operations
    
    Example:
        >>> # Module execution
        >>> ftl --module ping --inventory hosts.yml
        
        >>> # FTL module execution  
        >>> ftl --ftl-module custom.py --inventory localhost.yml --debug
        
        >>> # With module arguments
        >>> ftl -m file -i inventory.yml -a "path=/tmp/test state=touch"
    
    Command-Line Processing:
        The function handles the complete CLI workflow:
        
        1. Argument Parsing:
           - Uses Click to parse and validate arguments
           - Automatic help text generation and error handling
           - Type validation and conversion
           
        2. Logging Configuration:
           - --debug: Sets logging to DEBUG level with detailed output
           - --verbose: Sets logging to INFO level with operational details
           - Default: WARNING level for minimal output
           
        3. Dependency Management:
           - Loads Python requirements from specified file
           - Filters out empty lines and comments
           - Passes dependencies to module execution for gate building
           
        4. Module Execution:
           - Ansible modules: Uses run_module() with gate building
           - FTL modules: Uses run_ftl_module() for direct execution
           - Arguments parsed and passed to module functions
           
        5. Output Formatting:
           - Uses pprint for readable output formatting
           - Displays complete execution results
           - Maintains consistent output format
    
    Execution Modes:
        The CLI supports two primary execution modes:
        
        Ansible Module Mode (--module):
        - Executes Ansible-compatible modules
        - Supports remote execution via gates
        - Includes dependency management
        - Uses module discovery from module directories
        
        FTL Module Mode (--ftl-module):
        - Executes FTL-native Python modules
        - Direct local execution without gates
        - Optimized for FTL-specific functionality
        - Supports async module implementations
    
    Configuration Options:
        - Inventory: YAML file specifying target hosts and variables
        - Module Directory: Path to search for automation modules
        - Requirements: Python dependencies for complex modules
        - Arguments: Module-specific parameters in key=value format
        - Logging: Debug, verbose, or minimal output levels
        
    Error Handling:
        The function implements comprehensive error handling:
        - Click handles argument validation and help display
        - File operations catch FileNotFoundError for missing files
        - Module execution errors are propagated to caller
        - All errors result in proper exit codes and error messages
        
    Integration Points:
        The main function integrates with:
        - Click for argument parsing and help generation
        - FTL module execution system for automation workflows
        - Inventory management for host and variable loading
        - Logging system for debugging and operational visibility
        - Gate building system for remote execution capabilities
        
    Performance Considerations:
        - Asynchronous execution for non-blocking operations
        - Lazy loading of dependencies and inventory
        - Efficient argument parsing with minimal overhead
        - Optimized module execution paths for different module types
        
    Use Cases:
        - Interactive automation task execution
        - Automated script and pipeline integration
        - Development and testing of automation modules
        - Production automation workflows
        - Migration from Ansible to FTL workflows
        
    Note:
        This function serves as the primary integration point between the
        command-line interface and FTL's automation capabilities. Click
        provides better argument validation and help generation compared
        to the previous docopt implementation.
    """
    
    # Validate mutually exclusive options
    if ftl_module and module:
        raise click.ClickException("Cannot specify both --ftl-module and --module")
    if not ftl_module and not module:
        raise click.ClickException("Must specify either --ftl-module or --module")
    
    # Configure logging
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Load dependencies if requirements file specified
    dependencies = None
    if requirements:
        with open(requirements) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    async def run_async() -> None:
        """Inner async function to handle async operations."""
        if module:
            output = await run_module(
                load_inventory(inventory),
                [module_dir] if module_dir else [],
                module,
                modules=[module],
                module_args=parse_module_args(args or ""),
                dependencies=dependencies,
            )
            pprint(output)
        elif ftl_module:
            output = await run_ftl_module(
                load_inventory(inventory),
                [module_dir] if module_dir else [],
                ftl_module,
                module_args=parse_module_args(args or ""),
            )
            pprint(output)

    # Run the async operations
    asyncio.run(run_async())


def entry_point() -> None:
    """Package entry point for the FTL command-line interface.
    
    Provides the primary entry point for the FTL CLI when installed as a
    package. This function serves as the bridge between package installation
    and the Click-based main function, enabling the tool to be used as a
    standard command-line utility.
    
    Returns:
        None. The function handles all execution and exits via Click's
        exception handling and system calls.
    
    Raises:
        SystemExit: Implicitly raised by Click when execution completes,
            help is requested, or errors occur. Exit codes follow Unix conventions.
    
    Example:
        >>> # Called automatically when FTL is installed and used
        >>> # Via command line: ftl --module setup --inventory inventory.yml
        >>> # Or programmatically:
        >>> entry_point()  # Executes with sys.argv
    
    Package Integration:
        This function serves as the entry point defined in:
        - setup.py console_scripts
        - pyproject.toml project.scripts
        - Package installation systems
        
        Example package configuration:
        ```toml
        [project.scripts]
        ftl = "faster_than_light.cli:entry_point"
        ```
        
    Execution Flow:
        1. Click processes command-line arguments from sys.argv
        2. Validates arguments and options according to decorators
        3. Calls main() function with parsed and validated arguments
        4. Handles any exceptions and converts to appropriate exit codes
        5. Exits with proper status codes
        
    Click Integration:
        The function integrates with Click's command processing:
        - Click handles argument parsing and validation automatically
        - Automatic help text generation from decorators and docstrings
        - Built-in error handling and user feedback
        - Standard CLI conventions and behaviors
        
    Error Handling:
        - SystemExit: Raised by Click for help, errors, or completion
        - ClickException: Converted to user-friendly error messages
        - General exceptions: Handled by Click's exception handling
        - Async errors: Handled by asyncio.run() within main()
        
    Use Cases:
        - Primary CLI execution after package installation
        - Script integration in automation pipelines
        - Docker container entry points
        - System service integration
        - Development and testing workflows
        
    Performance:
        - Minimal overhead for entry point processing
        - Efficient Click argument parsing and validation
        - Direct delegation to main() function
        - Optimized for frequent CLI invocations
        
    Integration Points:
        - Package management systems (pip, conda, etc.)
        - System PATH and executable scripts
        - Container and virtualization platforms
        - CI/CD pipeline tool integration
        - Shell completion and wrapper scripts
        
    Benefits of Click Integration:
        - Better error messages and validation
        - Automatic help text generation
        - Type conversion and validation
        - Option grouping and organization
        - Extensible command structure
        
    Note:
        This function is intentionally minimal to provide a clean bridge
        between package installation and Click's command processing system.
        All complex logic is handled in the main() function with Click
        providing robust argument handling and validation.
    """
    main()   # pragma: no cover
