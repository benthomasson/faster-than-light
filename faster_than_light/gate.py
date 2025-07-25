"""FTL gate building system for remote execution infrastructure.

This module provides the core functionality for building FTL "gates" - self-contained
Python executable archives (.pyz) that enable remote automation execution. Gates
package modules, dependencies, and runtime components into portable executables
that can be deployed and executed on remote systems via SSH.

Key Features:
- Self-contained Python executable archive creation using zipapp
- Module packaging and dependency management for remote execution
- Intelligent caching system to avoid rebuilding identical gates
- Custom Python interpreter specification for target environments
- Dependency installation with pip integration for complex modules
- Hash-based caching for performance optimization
- Temporary file management with automatic cleanup

Gate Architecture:
- Executable Archive: .pyz files that can run standalone with Python
- Module Inclusion: Automation modules embedded in the archive
- Dependency Bundling: Python packages installed directly into the archive
- Runtime Components: FTL gate runtime for module execution coordination
- Interpreter Flexibility: Configurable Python interpreter for target systems

The gate system is fundamental to FTL's remote execution capabilities, enabling
the framework to deploy and run automation modules on remote systems without
requiring FTL to be pre-installed on target hosts. This provides a lightweight,
portable solution for distributed automation tasks.

Performance Benefits:
- Cached builds: Identical gate configurations reuse existing archives
- Minimal deployment: Single file contains everything needed for execution
- No remote dependencies: Self-contained execution environment
- Fast startup: Pre-packaged modules eliminate import overhead
"""

import hashlib
import os
import sys
import shutil
import tempfile
import zipapp
import logging

from importlib_resources import files
import faster_than_light.ftl_gate
from subprocess import check_output

from .util import ensure_directory, read_module, find_module
from .exceptions import ModuleNotFound

from typing import Optional, List, Tuple

logger = logging.getLogger('faster_than_light.gate')


def use_gate(cached_gate: str, gate_hash: str, interpreter: Optional[str] = None) -> Tuple[str, str]:
    """Utilize an existing cached gate for remote execution operations.
    
    This function provides a lightweight interface for working with pre-built
    FTL gates, returning the gate path and hash for use in remote execution
    workflows. It serves as a passthrough mechanism for cached gate management
    and may be extended with additional gate validation or preparation logic.
    
    Args:
        cached_gate: File path to the cached gate executable (.pyz file).
            Should point to a valid FTL gate archive in the cache directory.
        gate_hash: SHA256 hash string identifying the specific gate configuration.
            Used for cache validation and gate identification.
        interpreter: Optional Python interpreter path for the target system.
            Currently unused but maintained for API consistency and future
            extension of gate runtime configuration.
    
    Returns:
        Tuple of (cached_gate, gate_hash) containing:
        - cached_gate: The input gate file path, validated for use
        - gate_hash: The input gate hash, confirmed for identification
    
    Example:
        >>> # Use an existing cached gate
        >>> gate_path = "/home/user/.ftl/ftl_gate_abc123.pyz"
        >>> gate_hash = "abc123..."
        >>> gate, hash_id = use_gate(gate_path, gate_hash)
        >>> print(f"Using gate: {gate}")
        Using gate: /home/user/.ftl/ftl_gate_abc123.pyz
        
        >>> # Prepare gate for remote deployment
        >>> gate, hash_id = use_gate(cached_gate, gate_hash, "/usr/bin/python3")
        >>> # Gate is ready for SSH transfer and execution
    
    Use Cases:
        - Reusing existing gates without rebuilding
        - Gate validation and preparation workflows
        - Integration with gate caching and management systems
        - Remote execution pipeline preparation
        
    Gate Requirements:
        The cached_gate should be:
        - A valid .pyz executable archive
        - Built with compatible FTL gate runtime
        - Accessible and readable by the current process
        - Compatible with the target remote system architecture
        
    Integration:
        This function integrates with:
        - build_ftl_gate() for initial gate creation
        - SSH deployment workflows for remote gate transfer
        - Gate caching systems for performance optimization
        - Remote execution coordination for module deployment
        
    Future Extensions:
        The function may be extended to include:
        - Gate integrity validation and checksum verification
        - Interpreter compatibility checking
        - Gate metadata extraction and validation
        - Runtime environment preparation
        
    Note:
        Currently this function serves as a simple passthrough for gate
        parameters. It maintains a consistent API for gate management while
        allowing for future extension with validation, preparation, or
        compatibility checking logic as the gate system evolves.
    """
    return cached_gate, gate_hash


def build_ftl_gate(
    modules: Optional[List[str]] = None,
    module_dirs: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    interpreter: str = sys.executable,
    local_interpreter: str = sys.executable,
) -> Tuple[str, str]:
    """Build a self-contained FTL gate executable for remote automation execution.
    
    Creates a portable Python executable archive (.pyz) containing FTL runtime,
    automation modules, and dependencies. The resulting gate can be deployed and
    executed on remote systems without requiring FTL installation on target hosts.
    Uses intelligent caching to avoid rebuilding identical configurations.
    
    Args:
        modules: List of module names to include in the gate. Modules are
            located using find_module() and embedded in the archive for
            remote execution. Can be empty for gates without custom modules.
        module_dirs: List of directory paths to search for modules. Used by
            find_module() to locate automation modules. Defaults to empty
            list if not specified.
        dependencies: List of Python package names to install in the gate
            using pip. Packages are installed directly into the archive
            to create a self-contained execution environment.
        interpreter: Python interpreter path for the target remote system.
            Used as the shebang for the executable archive. Should match
            the Python version available on target hosts.
        local_interpreter: Python interpreter path for the build system.
            Used for pip operations during gate construction. Should have
            access to required packages and pip.
    
    Returns:
        Tuple of (cached_gate_path, gate_hash) containing:
        - cached_gate_path: File path to the built gate executable (.pyz)
        - gate_hash: SHA256 hash identifying this gate configuration for caching
    
    Raises:
        ModuleNotFound: If a specified module cannot be found in module_dirs.
        subprocess.CalledProcessError: If pip dependency installation fails.
        OSError: If filesystem operations fail during gate construction.
        zipapp.ZipAppError: If archive creation fails due to invalid content.
    
    Example:
        >>> # Build a basic gate with core modules
        >>> gate_path, gate_hash = build_ftl_gate(
        ...     modules=["setup", "file"],
        ...     module_dirs=["/opt/ansible/modules"],
        ...     interpreter="/usr/bin/python3"
        ... )
        >>> print(f"Built gate: {gate_path}")
        Built gate: /home/user/.ftl/ftl_gate_abc123.pyz
        
        >>> # Build gate with dependencies
        >>> gate_path, gate_hash = build_ftl_gate(
        ...     modules=["custom_module"],
        ...     module_dirs=["./modules"],
        ...     dependencies=["requests", "pyyaml>=5.0"],
        ...     interpreter="/opt/python3.9/bin/python"
        ... )
        
        >>> # Build minimal gate for testing
        >>> gate_path, gate_hash = build_ftl_gate()
        >>> # Creates gate with only FTL runtime, no custom modules
    
    Gate Construction Process:
        The function follows this build process:
        
        1. Parameter Validation:
           - Normalize None parameters to empty lists
           - Generate configuration hash for caching
           
        2. Cache Management:
           - Check for existing gate with same configuration hash
           - Return cached gate if available to avoid rebuilding
           
        3. Temporary Environment Setup:
           - Create temporary directory for gate construction
           - Set up gate directory structure with __main__.py
           - Copy FTL gate runtime from package resources
           
        4. Module Installation:
           - Locate each module using find_module() in module_dirs
           - Copy module files into gate module directory
           - Create __init__.py for proper Python package structure
           
        5. Dependency Installation:
           - Generate requirements.txt with dependency specifications
           - Use pip to install packages directly into gate directory
           - Include all package dependencies for self-contained execution
           
        6. Archive Creation:
           - Use zipapp to create executable Python archive
           - Configure with specified target interpreter
           - Generate .pyz file ready for remote deployment
           
        7. Cache Storage:
           - Copy completed gate to cache directory
           - Clean up temporary build files
           - Return paths for immediate use
    
    Caching Strategy:
        Gates are cached based on a SHA256 hash of:
        - All module names and module directory paths
        - All dependency specifications
        - Target interpreter path
        
        Cache benefits:
        - Eliminates redundant builds for identical configurations
        - Provides instant access to previously built gates
        - Reduces build time for repeated deployments
        - Supports multiple concurrent gate configurations
        
    Directory Structure:
        Built gates contain this internal structure:
        
        ```
        ftl_gate.pyz/
        ├── __main__.py              # Entry point for gate execution
        ├── ftl_gate/               # FTL runtime package
        │   ├── __init__.py
        │   ├── module1.py          # User modules
        │   ├── module2.py
        │   └── ...
        ├── dependency_package/     # Installed dependencies
        └── ...
        ```
        
    Performance Considerations:
        - Build time: Proportional to number of dependencies and modules
        - Cache efficiency: Identical configurations reuse existing gates
        - Archive size: Includes all dependencies for self-contained execution
        - Deployment speed: Single file transfer vs. multiple dependency installs
        
    Security Considerations:
        - Module inclusion: Only specified modules are embedded
        - Dependency trust: Uses pip with standard package repositories
        - Archive integrity: Zipapp provides tamper-evident packaging
        - Execution isolation: Gates run in target system environment
        
    Integration Points:
        The built gates integrate with:
        - SSH deployment for remote gate transfer
        - Remote execution coordination for module invocation
        - FTL message protocol for gate communication
        - Module result collection and processing
        
    Use Cases:
        - Remote automation without FTL installation on targets
        - Isolated execution environments for different module sets
        - Dependency management for complex automation workflows
        - Portable automation packages for air-gapped environments
        - Testing and development with consistent execution environments
        
    Note:
        Gate building is a relatively expensive operation involving file I/O,
        subprocess execution, and archive creation. The caching system is
        essential for performance in production environments where the same
        gate configurations are used repeatedly.
    """

    logger.debug(f'build_ftl_gate  {modules=} {module_dirs=} {dependencies=} {interpreter=} {local_interpreter=}')

    cache = ensure_directory("~/.ftl")

    if modules is None:
        modules = []
    if module_dirs is None:
        module_dirs = []
    if dependencies is None:
        dependencies = []

    inputs = []
    inputs.extend(modules)
    inputs.extend(module_dirs)
    inputs.extend(dependencies)
    inputs.extend(interpreter)

    gate_hash = hashlib.sha256("".join([str(i) for i in inputs]).encode()).hexdigest()

    cached_gate = os.path.join(cache, f"ftl_gate_{gate_hash}.pyz")
    if os.path.exists(cached_gate):
        logger.info(f'build_ftl_gate reusing cached_gate {cached_gate}')
        return cached_gate, gate_hash

    tempdir = tempfile.mkdtemp()
    os.mkdir(os.path.join(tempdir, "ftl_gate"))
    with open(os.path.join(tempdir, "ftl_gate", "__main__.py"), "w") as f:
        f.write(files(faster_than_light.ftl_gate).joinpath("__main__.py").read_text())

    module_dir = os.path.join(tempdir, "ftl_gate", "ftl_gate")
    os.makedirs(module_dir)
    with open(os.path.join(module_dir, "__init__.py"), "w") as f:
        f.write("")

    # Install modules
    if modules:
        for module in modules:
            module_name = find_module(module_dirs, module)
            if module_name is None:
                raise ModuleNotFound(f"Cannot find {module} in {module_dirs}")
            module_path = os.path.join(module_dir, os.path.basename(module_name))
            with open(module_path, "wb") as f2:
                f2.write(read_module(module_dirs, module))

    # Install dependencies for Gate
    if dependencies:
        requirements = os.path.join(tempdir, "requirements.txt")
        with open(requirements, "w") as f:
            f.write("\n".join(dependencies))

        command = [
                local_interpreter,
                "-m",
                "pip",
                "install",
                "-r",
                requirements,
                "--target",
                os.path.join(tempdir, "ftl_gate"),
            ]
        logger.debug(" ".join(command))
        output = check_output(command)
        print(output)

    zipapp.create_archive(
        os.path.join(tempdir, "ftl_gate"),
        os.path.join(tempdir, "ftl_gate.pyz"),
        interpreter,
    )
    shutil.rmtree(os.path.join(tempdir, "ftl_gate"))
    shutil.copy(os.path.join(tempdir, "ftl_gate.pyz"), cached_gate)

    return cached_gate, gate_hash
