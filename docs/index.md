# Introduction

**CrossContract** is a robust Python package designed to bring strict data integrity and frictionless interaction to the CROSS ecosystem. It serves as the foundational layer for defining reliable data schemas and contracts.

The package consists of two main components:

*   [**CrossContract**](contracts/index.md): The core library for defining high-integrity, validation-ready data contracts and schemas using Pydantic and Frictionless standards.
*   [**CrossRegistry**](registry/index.md): A data registry to conveniently interact with the
data stored in the CrossPlatform.
*   [**CrossClient**](client/index.md): A low-level API client to interact seamlessly with the CrossPlatform.



## Requirements

*   **Python:** 3.11 or higher

## Installation

This package is hosted directly on GitHub. We strongly recommend installing it within a **virtual environment**.

### Using pip

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

pip install crosscontract
```

### Using uv

```bash
uv venv
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

uv pip crosscontract
```

Alternatively, if you use a project-based approach with uv:

```bash
uv init
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

uv add crosscontract
```


### Using poetry

```bash
poetry init
poetry shell

poetry add crosscontract
```

## Dependencies

The key libraries powering CrossContract are:

*   **Pydantic**: For data validation and settings management.
*   **Pandas**: For powerful data manipulation and analysis.
*   **SQLAlchemy**: For database abstraction and interaction.
*   **httpx**: For synchronous and asynchronous HTTP requests (CrossClient).

## Contributing

We use a two-branch flow with `python-semantic-release` for versioning. See the [Contributing](contributing.md) guide for the branching model, PR conventions, and release process.

## License

This project is licensed under the terms of the MIT license.

## Quick Links

*   [**API Reference**](reference/contracts.md)
*   [**Notebook Examples**](https://github.com/sweet-cross/crosscontract/tree/main/notebooks)
