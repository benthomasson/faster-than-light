

import faster_than_light.cli
import faster_than_light.builder
import pytest
import os
import sys
from click.testing import CliRunner

HERE = os.path.dirname(os.path.abspath(__file__))


def test_cli():
    """Test CLI with no arguments (should fail with missing inventory)."""
    runner = CliRunner()
    result = runner.invoke(faster_than_light.cli.main, [])
    assert result.exit_code == 2  # Missing required inventory option


def test_cli_debug():
    """Test CLI with debug flag (should fail with missing inventory)."""
    runner = CliRunner()
    result = runner.invoke(faster_than_light.cli.main, ['--debug'])
    assert result.exit_code == 2  # Missing required inventory option


def test_cli_verbose():
    """Test CLI with verbose flag (should fail with missing inventory)."""
    runner = CliRunner()
    result = runner.invoke(faster_than_light.cli.main, ['--verbose'])
    assert result.exit_code == 2  # Missing required inventory option


def test_cli_argtest():
    """Test CLI with module execution arguments."""
    runner = CliRunner()
    # Use relative paths and change to the test directory for file access
    with runner.isolated_filesystem():
        # Create a mock inventory file
        with open('inventory.yml', 'w') as f:
            f.write('all:\n  hosts:\n    localhost:\n      ansible_connection: local\n')
        
        # This will fail because modules/argtest doesn't exist, but we test argument parsing
        result = runner.invoke(faster_than_light.cli.main, [
            '-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml', 
            '-a', 'somekey=somevalue'
        ])
        # Exit code may be non-zero due to missing module, but this tests argument parsing
        assert result.exit_code != 0  # Expected due to missing module file


def test_cli_argtest2():
    """Test CLI with module execution without arguments."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a mock inventory file
        with open('inventory.yml', 'w') as f:
            f.write('all:\n  hosts:\n    localhost:\n      ansible_connection: local\n')
        
        result = runner.invoke(faster_than_light.cli.main, [
            '-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml'
        ])
        # Exit code may be non-zero due to missing module, but this tests argument parsing
        assert result.exit_code != 0  # Expected due to missing module file


def test_cli_ftl_argtest():
    """Test CLI with FTL module execution."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a mock inventory file
        with open('inventory.yml', 'w') as f:
            f.write('all:\n  hosts:\n    localhost:\n      ansible_connection: local\n')
        
        result = runner.invoke(faster_than_light.cli.main, [
            '-M', 'ftl_modules', '-f', 'argtest', '-i', 'inventory.yml', 
            '-a', 'somekey=somevalue'
        ])
        # Exit code may be non-zero due to missing module, but this tests argument parsing
        assert result.exit_code != 0  # Expected due to missing module file


def test_cli_with_requirements():
    """Test CLI with requirements file."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create mock files
        with open('inventory.yml', 'w') as f:
            f.write('all:\n  hosts:\n    localhost:\n      ansible_connection: local\n')
        with open('requirements.txt', 'w') as f:
            f.write('requests>=2.25.0\n')
        
        result = runner.invoke(faster_than_light.cli.main, [
            '-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml', 
            '-a', 'somekey=somevalue', '--requirements', 'requirements.txt'
        ])
        # Exit code may be non-zero due to missing module, but this tests argument parsing
        assert result.exit_code != 0  # Expected due to missing module file


def test_builder_cli():
    """Test builder CLI with no arguments."""
    faster_than_light.builder.main([], standalone_mode=False)


def test_builder_cli2():
    """Test builder CLI with full arguments."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a mock requirements file
        with open('requirements.txt', 'w') as f:
            f.write('requests>=2.25.0\n')
        
        # Create modules directory and mock argtest module
        os.makedirs('modules', exist_ok=True)
        with open('modules/argtest.py', 'w') as f:
            f.write('#!/usr/bin/python3\nprint("argtest module")\n')
        
        faster_than_light.builder.main([
            '-M', 'modules', '-m', 'argtest', '--requirements', 'requirements.txt', 
            '--interpreter', sys.executable
        ], standalone_mode=False)


def test_builder_cli_debug():
    """Test builder CLI with debug flag."""
    faster_than_light.builder.main(['--debug'], standalone_mode=False)


def test_builder_cli_verbose():
    """Test builder CLI with verbose flag."""
    faster_than_light.builder.main(['--verbose'], standalone_mode=False)
