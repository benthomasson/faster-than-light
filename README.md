# Faster Than Light (FTL)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![image](https://img.shields.io/pypi/v/faster-than-light.svg)](https://pypi.python.org/pypi/faster-than-light)
[![codecov](https://codecov.io/github/benthomasson/faster-than-light/branch/main/graph/badge.svg?token=SRAAGLDORB)](https://codecov.io/github/benthomasson/faster-than-light)
![ci](https://github.com/benthomasson/faster-than-light/actions/workflows/ci.yml/badge.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.gg/aAhDQz6ywr)
[![image](https://img.shields.io/pypi/pyversions/faster-than-light.svg)](https://pypi.python.org/pypi/faster-than-light)


An experimental automation framework built for speed and scalability, designed as a high-performance alternative to Ansible using modern Python asyncio.

## 🚀 Overview

Faster Than Light is a from-scratch automation framework that explores the performance limits of infrastructure automation. Built with Python 3 and asyncio, FTL aims to be significantly faster than traditional automation tools while maintaining compatibility with existing Ansible modules.

## ✨ Key Features

- **🏃‍♂️ High Performance**: Benchmarks show significant speedups over Ansible 2.10.9
- **⚡ Async-First Architecture**: Built with Python asyncio for maximum concurrency
- **🔌 Ansible Compatibility**: Run existing Ansible modules without modification
- **🌐 Efficient Remote Execution**: Persistent SSH "gates" for optimized remote operations
- **📊 Built-in Benchmarking**: Comprehensive performance testing and measurement tools
- **🎯 Modern Python**: Leverages latest Python features and best practices

## 📈 Performance Results

FTL demonstrates substantial performance improvements over Ansible:

- **Local Execution**: 2-10x faster depending on the number of hosts
- **Remote Execution**: Significant improvements through connection pooling and async execution
- **Scalability**: Better performance scaling as host count increases

See the [performance blog posts](blog/) for detailed benchmarking results and analysis.

## 🛠️ Installation

### From Source

```bash
git clone https://github.com/your-org/faster-than-light.git
cd faster-than-light
pip install -e .
```

### Dependencies

FTL requires Python 3.7+ and installs these key dependencies:
- `asyncssh` - Async SSH connections
- `asyncio` - Async execution framework
- `pyyaml` - YAML parsing for inventories
- `jinja2` - Template rendering
- `click` - CLI framework

## 🚀 Quick Start

### Basic Module Execution

Run a module against your inventory:

```bash
# Run an Ansible module
ftl --module setup --inventory inventory.yml --module-dir /path/to/modules

# Run an FTL-optimized module
ftl --ftl-module timetest --inventory inventory.yml --module-dir ./ftl_modules
```

### Example Inventory

Create an `inventory.yml` file:

```yaml
all:
  hosts:
    server1:
      ansible_host: 192.168.1.10
      ansible_user: admin
    server2:
      ansible_host: 192.168.1.11
      ansible_user: admin
  vars:
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

### Module Arguments

Pass arguments to modules:

```bash
ftl --module command --args "cmd='uptime'" --inventory inventory.yml
```

## 📚 CLI Usage

```
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
```

## 🔧 Available Commands

- **`ftl`** - Main automation CLI
- **`ftl-gate-builder`** - Build FTL gates for remote execution
- **`ftl-localhost`** - Inventory management for localhost

## 🏗️ Architecture

FTL uses several key architectural components:

- **Gate System**: Persistent SSH connections for efficient remote execution
- **Async Module Runner**: Concurrent execution across multiple hosts
- **Inventory Management**: Ansible-compatible inventory parsing
- **Local/Remote Execution**: Seamless switching between local and remote execution modes

## 🧪 Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements_dev.txt

# Run tests
pytest tests/

# Run performance tests
cd performance-test/python-asyncio/local
./run_perf_async.sh
```

### Performance Testing

The project includes comprehensive performance testing:

```bash
# Local performance tests
cd performance-test/python-asyncio/local
./run_perf.sh

# Remote performance tests  
cd performance-test/python-asyncio/remote
./run_perf.sh
```

## 📖 Documentation

Detailed documentation and development journey available in the [blog notebooks](blog/):

- [Introduction](blog/0001-Introduction.ipynb) - Project goals and overview
- [The Beginning](blog/0002-The-Beginning.ipynb) - Architecture decisions
- [Modules](blog/0003-Modules.ipynb) - Module system design
- [Local Execution](blog/0004-Local-Execution.ipynb) - Local execution performance
- [Remote Execution](blog/0005-Remote-Execution.ipynb) - Remote execution optimization
- [Performance Analysis](blog/0006-Performance.ipynb) - Benchmark results

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by Ansible's module system and inventory management
- Built to explore the performance potential of modern Python async frameworks
- Performance benchmarking methodology adapted from infrastructure automation best practices

## 📊 Project Status

This is an experimental project focused on performance research and exploring the limits of automation frameworks. While functional, it's primarily intended for research, benchmarking, and educational purposes.

---

**Note**: This project is experimental and designed for performance research. For production automation needs, consider using established tools like Ansible, while keeping an eye on this project's performance insights and architectural innovations.

