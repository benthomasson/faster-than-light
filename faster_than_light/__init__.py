"""Top-level package for Faster Than Light."""

__author__ = """Ben Thomasson"""
__email__ = "benthomasson@gmail.com"
__version__ = "0.1.4"

from .module import run_module, run_ftl_module, run_module_sync
from .ssh import close_gate, copy, copy_sync, copy_from, copy_from_sync
from .inventory import load_inventory, load_localhost

localhost = load_localhost()

__all__ = [
    "run_module",
    "run_ftl_module",
    "load_inventory",
    "close_gate",
    "run_module_sync",
    "copy",
    "copy_from",
    "copy_sync",
    "copy_from_sync",
]
