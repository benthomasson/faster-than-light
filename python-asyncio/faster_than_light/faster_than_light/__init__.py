"""Top-level package for Faster Than Light."""

__author__ = """Ben Thomasson"""
__email__ = 'benthomasson@gmail.com'
__version__ = '0.1.2'

from .module import run_module, run_ftl_module, close_gate
from .inventory import load_inventory

__all__ = ['run_module', 'run_ftl_module', 'load_inventory', 'close_gate']
