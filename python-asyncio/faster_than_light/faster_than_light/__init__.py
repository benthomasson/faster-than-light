"""Top-level package for Faster Than Light."""

__author__ = """Ben Thomasson"""
__email__ = 'benthomasson@gmail.com'
__version__ = '0.1.1'

from .module import run_module, run_ftl_module
from .inventory import load_inventory

__all__ = ['run_module', 'run_ftl_module', 'load_inventory']
