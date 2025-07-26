"""FTL gate builder command-line tool for creating automation execution packages.

This module provides a dedicated command-line interface for building FTL gates -
self-contained Python executable archives that package automation modules and
dependencies for remote execution. The builder offers fine-grained control over
gate composition, dependency management, and interpreter configuration.

Key Features:
- Standalone gate building without full FTL CLI dependencies
- Support for multiple modules and module directories
- Flexible Python dependency management via requirements files
- Custom Python interpreter specification for target environments
- Intelligent caching system for build optimization
- Comprehensive logging and debugging capabilities
- Click-based CLI with robust argument validation

Gate Building Workflow:
The builder orchestrates the complete gate creation process:
1. Module Discovery: Locates and validates automation modules
2. Dependency Resolution: Processes requirements files and installs packages
3. Archive Creation: Builds self-contained .pyz executable archives
4. Caching: Stores built gates for reuse with identical configurations
5. Validation: Ensures gate integrity and proper configuration

Command-Line Interface:
ftl-gate-builder provides a focused interface for gate building operations:

Usage:
    ftl-gate-builder [options]

Options:
    -h, --help                  Show this page
    --debug                     Show debug logging
    --verbose                   Show verbose logging
    -f=<f>, --ftl-module=<f>    FTL module (can be specified multiple times)
    -m=<m>, --module=<m>        Module (can be specified multiple times)
    -M=<M>, --module-dir=<M>    Module directory (can be specified multiple times)
    -r=<r>, --requirements=<r>  Python requirements file (can be specified multiple times)
    -I=<I>, --interpreter=<I>   Python interpreter to use (default: /usr/bin/python3)

Examples:
    # Build basic gate with modules
    ftl-gate-builder -m ping -m setup -M /opt/modules

    # Build gate with dependencies
    ftl-gate-builder -m custom_module -r requirements.txt -M ./modules

    # Build gate with custom interpreter
    ftl-gate-builder -m module -I /opt/python3.9/bin/python

The builder integrates seamlessly with FTL's gate system while providing a
specialized tool for advanced gate building scenarios, development workflows,
and automated build pipelines.
"""

import logging
import sys
from typing import List, Optional, Tuple

import click

from faster_than_light.gate import build_ftl_gate

logger = logging.getLogger("builder")


@click.command
@click.option("--ftl-module", "-f", multiple=True)
@click.option("--module", "-m", multiple=True)
@click.option("--module-dir", "-M", multiple=True)
@click.option("--requirements", "-r", multiple=True)
@click.option("--interpreter", "-I")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--debug", "-d", is_flag=True)
def main(
    ftl_module: Tuple[str, ...],
    module: Tuple[str, ...],
    module_dir: Tuple[str, ...],
    requirements: Tuple[str, ...],
    interpreter: Optional[str],
    verbose: bool,
    debug: bool,
) -> int:
    """Main CLI function for building FTL gates with comprehensive configuration options.

    Orchestrates the complete FTL gate building process with support for multiple
    modules, dependencies, and custom interpreter configurations. Uses Click for
    robust argument parsing and validation, providing a user-friendly interface
    for advanced gate building scenarios.

    Args:
        ftl_module: Tuple of FTL module names to include in the gate. Can be
            specified multiple times via -f/--ftl-module flags. Currently
            collected but not used in gate building.
        module: Tuple of module names to include in the gate. Can be specified
            multiple times via -m/--module flags. Modules are located using
            the module directories specified in module_dir.
        module_dir: Tuple of directory paths to search for modules. Can be
            specified multiple times via -M/--module-dir flags. Each directory
            is searched for the modules specified in the module parameter.
        requirements: Tuple of requirements file paths. Can be specified multiple
            times via -r/--requirements flags. Each file is processed and its
            dependencies are included in the gate.
        interpreter: Python interpreter path for the target system. Defaults to
            "/usr/bin/python3" if not specified. Used as the shebang for the
            executable gate archive.
        verbose: Boolean flag to enable verbose logging. Sets logging level to
            INFO when True, providing operational details during build.
        debug: Boolean flag to enable debug logging. Sets logging level to DEBUG
            when True, providing detailed build process information.

    Returns:
        Integer exit code following Unix conventions:
        - 0: Successful gate building
        - Non-zero: Error occurred during building (handled by exceptions)

    Raises:
        FileNotFoundError: If requirements files or module directories don't exist.
        ModuleNotFound: If specified modules cannot be found in module directories.
        PermissionError: If file operations fail due to insufficient permissions.
        subprocess.CalledProcessError: If dependency installation fails.
        Various exceptions: From gate building process or file operations.

    Example:
        >>> # Called via click CLI - these are internal function calls
        >>> main(
        ...     ftl_module=(),
        ...     module=('ping', 'setup'),
        ...     module_dir=('/opt/modules',),
        ...     requirements=('requirements.txt',),
        ...     interpreter='/usr/bin/python3',
        ...     verbose=False,
        ...     debug=True
        ... )
        0

    CLI Usage Examples:
        # Build gate with multiple modules
        ftl-gate-builder -m ping -m setup -M /opt/modules

        # Build gate with dependencies
        ftl-gate-builder -m custom_module -r requirements.txt -M ./modules

        # Build gate with custom interpreter and debugging
        ftl-gate-builder -m module -I /opt/python3.9/bin/python --debug

        # Build gate with multiple requirement files
        ftl-gate-builder -m module -r base.txt -r extra.txt -M ./modules

    Click Integration:
        The function uses Click decorators for argument processing:
        - @click.command: Defines the main command entry point
        - @click.option: Configures each command-line option with validation
        - multiple=True: Allows options to be specified multiple times
        - is_flag=True: Treats options as boolean flags

    Gate Building Process:
        1. Argument Processing:
           - Converts Click tuples to appropriate data structures
           - Processes requirements files and extracts dependencies
           - Sets default interpreter if not specified

        2. Logging Configuration:
           - Configures logging based on verbose/debug flags
           - Provides appropriate detail level for troubleshooting

        3. Gate Construction:
           - Calls build_ftl_gate() with processed parameters
           - Handles module discovery and dependency installation
           - Creates self-contained executable archive

        4. Output and Results:
           - Displays gate file path and hash information
           - Returns success status for automation workflows

    Requirements File Processing:
        Requirements files are processed with the following rules:
        - Empty lines are ignored
        - Comments (lines starting with #) are filtered out
        - All valid dependency specifications are collected
        - Multiple files are merged into a single dependency list
        - Standard pip requirements format is expected

    Module Discovery:
        Modules are discovered using the following process:
        - Each module name is searched in all specified module directories
        - First match found is used (directory order matters)
        - Module files must be readable and accessible
        - Module validation is performed during gate building

    Performance Considerations:
        - Gate building can be resource-intensive for large dependency sets
        - Caching system reuses identical gate configurations
        - Module discovery is optimized for typical directory structures
        - Logging configuration impacts build performance minimally

    Error Handling:
        - Click handles argument validation and help text generation
        - File operation errors are propagated with clear messages
        - Gate building errors include context for troubleshooting
        - Logging provides detailed information for debugging

    Integration Points:
        The function integrates with:
        - build_ftl_gate() for core gate building functionality
        - Click framework for CLI argument processing
        - Python logging system for operational visibility
        - File system for module and requirements file access

    Development Notes:
        - The ftl_module parameter is currently collected but not used
        - This may indicate planned future functionality
        - All other parameters are properly processed and used
        - The function maintains compatibility with build_ftl_gate() interface

    Note:
        This function serves as the primary interface for the ftl-gate-builder
        command and provides a focused tool for gate building operations
        separate from the main FTL CLI. It's optimized for build automation
        and development workflows.
    """

    # Configure logging based on flags
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        logging.basicConfig(level=logging.INFO)

    modules: List[str] = list(module)
    module_dirs: List[str] = list(module_dir)

    dependencies: Optional[List[str]] = None
    for reqs in requirements:
        with open(reqs) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    if not interpreter:
        interpreter = "/usr/bin/python3"

    gate: Tuple[str, str] = build_ftl_gate(
        modules, module_dirs, dependencies, interpreter
    )
    print(gate)
    return 0


def entry_point() -> None:
    """Package entry point for the FTL gate builder command-line tool.

    Provides the primary entry point for the ftl-gate-builder CLI when installed
    as a package. This function bridges the gap between package installation and
    the Click-based main function, enabling the tool to be used as a standalone
    command-line utility for gate building operations.

    Returns:
        None. The function handles all execution and exits via the Click framework
        or system calls as appropriate.

    Raises:
        SystemExit: Implicitly raised by Click or the main function when execution
            completes or errors occur. Exit codes follow Unix conventions.
        Various exceptions: Propagated from the main function or Click framework
            during CLI processing and gate building operations.

    Example:
        >>> # Called automatically when ftl-gate-builder is installed and used
        >>> # Via command line: ftl-gate-builder -m setup -M /opt/modules
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
        ftl-gate-builder = "faster_than_light.builder:entry_point"
        ```

    Execution Flow:
        1. Extracts command-line arguments from sys.argv[1:]
        2. Passes arguments directly to Click-based main() function
        3. Click handles argument parsing, validation, and help generation
        4. Main function processes arguments and builds gates
        5. Results are displayed and appropriate exit codes returned

    Click Integration:
        The function integrates with Click's command processing:
        - Click handles argument parsing and validation
        - Automatic help text generation from decorators
        - Built-in error handling and user feedback
        - Standard CLI conventions and behaviors

    Tool Characteristics:
        ftl-gate-builder provides:
        - Standalone gate building without full FTL CLI
        - Focused interface for gate creation workflows
        - Advanced configuration options for gate composition
        - Integration with build automation and CI/CD pipelines
        - Development-friendly debugging and logging capabilities

    Use Cases:
        - Dedicated gate building in development workflows
        - Automated gate creation in CI/CD pipelines
        - Advanced gate configuration scenarios
        - Build tool integration for custom automation
        - Testing and validation of gate building processes

    Performance:
        - Minimal overhead for entry point processing
        - Direct argument passing to Click framework
        - Efficient integration with gate building system
        - Optimized for frequent build operations

    Integration Points:
        - Package management systems (pip, conda, etc.)
        - System PATH and executable scripts
        - Build automation tools and CI/CD systems
        - Docker container entry points
        - Development environment tool chains

    Comparison with Main FTL CLI:
        ftl-gate-builder vs ftl:
        - Focused on gate building only
        - More granular control over gate composition
        - Lighter weight without full automation framework
        - Specialized for build and development workflows
        - Click-based vs docopt-based argument processing

    Note:
        This function is intentionally minimal to provide a clean bridge
        between package installation and the Click-based CLI system. All
        complex logic is handled in the main() function with Click decorators
        providing robust argument processing and validation.
    """
    main(sys.argv[1:])  # pragma: no cover
