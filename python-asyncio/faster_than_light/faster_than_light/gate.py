import hashlib
import os
import sys
import shutil
import tempfile
import zipapp

from importlib_resources import files
import faster_than_light.ftl_gate
from subprocess import check_output

from .util import ensure_directory, read_module, find_module

from typing import Optional, List


def build_ftl_gate(
    modules: Optional[List[str]] = None,
    module_dirs: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    interpreter: str = sys.executable,
) -> str:

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

    gate_hash = hashlib.sha256("".join(inputs).encode()).hexdigest()

    cached_gate = os.path.join(cache, f"ftl_gate_{gate_hash}.pyz")
    if os.path.exists(cached_gate):
        return cached_gate

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
                raise Exception(f"Cannot find {module} in {module_dirs}")
            module_path = os.path.join(module_dir, os.path.basename(module_name))
            with open(module_path, "wb") as f2:
                f2.write(read_module(module_dirs, module))

    # Install dependencies for Gate
    if dependencies:
        requirements = os.path.join(tempdir, "requirements.txt")
        with open(requirements, "w") as f:
            f.write("\n".join(dependencies))
        output = check_output(
            [
                interpreter,
                "-m",
                "pip",
                "install",
                "-r",
                requirements,
                "--target",
                os.path.join(tempdir, "ftl_gate"),
            ]
        )
        print(output)

    zipapp.create_archive(
        os.path.join(tempdir, "ftl_gate"),
        os.path.join(tempdir, "ftl_gate.pyz"),
        interpreter,
    )
    shutil.rmtree(os.path.join(tempdir, "ftl_gate"))
    shutil.copy(os.path.join(tempdir, "ftl_gate.pyz"), cached_gate)

    return cached_gate
