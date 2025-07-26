"""Top-level package for Faster Than Light."""

__author__ = """Ben Thomasson"""
__email__ = "benthomasson@gmail.com"
__version__ = "0.1.4"

from .inventory import load_inventory, load_localhost
from .module import run_ftl_module, run_module, run_module_sync
from .ssh import (
    close_gate,
    copy,
    copy_from,
    copy_from_sync,
    copy_sync,
    mkdir,
    mkdir_sync,
    template,
    template_sync,
)

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
    "template",
    "template_sync",
    "mkdir",
    "mkdir_sync",
]
