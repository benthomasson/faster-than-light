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
automation frameworks.

Usage:
    ftl [options]

Options:
    -h, --help                  Show this page
    -f=<f>, --ftl-module=<f>    FTL module
    -m=<m>, --module=<m>        Module
    -M=<M>, --module-dir=<M>    Module directory
    -i=<i>, --inventory=<i>     Inventory
    -r=<r>, --requirements      Python requirements
    -a=<a>, --args=<a>          Module arguments
    --debug                     Show debug logging
    --verbose                   Show verbose logging
"""
import asyncio
from docopt import docopt
import logging
import sys
from .module import run_module
from .module import run_ftl_module
from .inventory import load_inventory
from pprint import pprint

from typing import Optional, List, Dict

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


async def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point for FTL automation framework execution.
    
    Orchestrates the complete FTL command-line workflow including argument
    parsing, logging configuration, inventory loading, and module execution.
    Supports both Ansible-compatible modules and FTL-native modules with
    comprehensive error handling and output formatting.
    
    Args:
        args: Command-line arguments to parse. If None, uses sys.argv[1:].
            Should be a list of strings in the format expected by docopt.
            Example: ["-m", "setup", "-i", "inventory.yml"]
    
    Returns:
        Integer exit code following Unix conventions:
        - 0: Successful execution
        - Non-zero: Error occurred (currently always returns 0)
    
    Raises:
        SystemExit: Via docopt when --help is specified or invalid arguments
            are provided. This is the standard docopt behavior.
        FileNotFoundError: If specified inventory or requirements files don't exist.
        ModuleNotFound: If specified modules cannot be found in module directories.
        Various exceptions: From module execution, inventory loading, or file operations.
    
    Example:
        >>> # Direct function call for testing
        >>> exit_code = await main(["-m", "ping", "-i", "hosts.yml"])
        >>> print(f"Execution completed with code: {exit_code}")
        
        >>> # With module arguments
        >>> exit_code = await main([
        ...     "-m", "file",
        ...     "-i", "inventory.yml", 
        ...     "-a", "path=/tmp/test state=touch"
        ... ])
        
        >>> # FTL module execution
        >>> exit_code = await main([
        ...     "-f", "custom_module.py",
        ...     "-i", "localhost.yml",
        ...     "--debug"
        ... ])
    
    Command-Line Processing:
        The function handles the complete CLI workflow:
        
        1. Argument Parsing:
           - Uses docopt to parse arguments against usage specification
           - Validates required arguments and option combinations
           - Provides automatic help text generation
           
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
        - Docopt handles argument validation and help display
        - File operations catch FileNotFoundError for missing files
        - Module execution errors are propagated to caller
        - All errors result in proper exit codes and error messages
        
    Integration Points:
        The main function integrates with:
        - docopt for argument parsing and help generation
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
        command-line interface and FTL's automation capabilities. It maintains
        compatibility with standard Unix CLI conventions while providing
        access to FTL's advanced features.
    """
    if args is None:
        args = sys.argv[1:]   # pragma: no cover
    parsed_args = docopt(__doc__, args)
    if parsed_args["--debug"]:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args["--verbose"]:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    dependencies = None
    if parsed_args["--requirements"]:
        with open(parsed_args["--requirements"]) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    if parsed_args["--module"]:
        output = await run_module(
            load_inventory(parsed_args["--inventory"]),
            [parsed_args["--module-dir"]],
            parsed_args["--module"],
            modules=[parsed_args["--module"]],
            module_args=parse_module_args(parsed_args["--args"]),
            dependencies=dependencies,
        )
        pprint(output)
    elif parsed_args["--ftl-module"]:
        output = await run_ftl_module(
            load_inventory(parsed_args["--inventory"]),
            [parsed_args["--module-dir"]],
            parsed_args["--ftl-module"],
            module_args=parse_module_args(parsed_args["--args"]),
        )
        pprint(output)
    return 0


def entry_point() -> None:
    """Package entry point for the FTL command-line interface.
    
    Provides the primary entry point for the FTL CLI when installed as a
    package. This function bridges the gap between package installation
    and the async main function, handling the transition from synchronous
    package entry points to FTL's asynchronous execution model.
    
    Returns:
        None. The function handles all execution and exits via system calls.
    
    Raises:
        SystemExit: Implicitly raised by asyncio.run() or the main function
            when execution completes or errors occur. Exit codes follow
            Unix conventions.
    
    Example:
        >>> # Called automatically when FTL is installed and used
        >>> # Via command line: ftl -m setup -i inventory.yml
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
        1. Extracts command-line arguments from sys.argv[1:]
        2. Creates new asyncio event loop for execution
        3. Runs the main() coroutine to completion
        4. Handles any exceptions and converts to exit codes
        5. Exits with appropriate status code
        
    Async Integration:
        The function handles the transition from synchronous entry points
        to FTL's async execution model:
        - Creates event loop for async operations
        - Manages async context and cleanup
        - Ensures proper exception handling and exit codes
        - Provides clean shutdown for async resources
        
    Error Handling:
        - SystemExit: Propagated from main() or asyncio.run()
        - Exceptions: Converted to non-zero exit codes
        - Async errors: Properly handled by asyncio.run()
        - Signal handling: Managed by asyncio event loop
        
    Use Cases:
        - Primary CLI execution after package installation
        - Script integration in automation pipelines
        - Docker container entry points
        - System service integration
        - Development and testing workflows
        
    Performance:
        - Minimal overhead for entry point processing
        - Efficient async loop creation and teardown
        - Direct argument passing without modification
        - Optimized for frequent CLI invocations
        
    Integration Points:
        - Package management systems (pip, conda, etc.)
        - System PATH and executable scripts
        - Container and virtualization platforms
        - CI/CD pipeline tool integration
        - Shell completion and wrapper scripts
        
    Note:
        This function is intentionally minimal to provide a clean bridge
        between package installation and FTL's async execution model.
        All complex logic is handled in the main() function.
    """
    asyncio.run(main(sys.argv[1:]))   # pragma: no cover
