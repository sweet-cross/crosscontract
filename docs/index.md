# Introduction

**CrossContract** is a robust Python package designed to bring strict data integrity and frictionless interaction to the CROSS ecosystem. It serves as the foundational layer for defining reliable data schemas and contracts.

The package consists of two main components:

*   [**CrossContract**](contracts/index.md): The core library for defining high-integrity, validation-ready data contracts and schemas using Pydantic and Frictionless standards.
*   [**CrossRegistry**](registry/index.md): A data registry to conveniently interact with the
data stored in the CrossPlatform.
*   [**CrossClient**](client/index.md): An low-level API client to interact seamlessly with the CrossPlatform.



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

## Development

We follow a structured development workflow to ensure stability:

*   **Branch Strategy**:
    *   `main`: Main branch released.
*   **Contribution Workflow**:
    1.  [Create an Issue](https://github.com/sweet-cross/crosscontract/issues/new) to discuss the change.
    2.  Clone the repository and branch out from `main`:
        ```bash
        git clone https://github.com/sweet-cross/crosscontract.git
        cd crosscontract
        git checkout dev
        git checkout -b feature/your-feature-name
        ```
    3.  Implement your changes.
    4.  Submit a Pull Request targeting the `main` branch.

## License

This project is licensed under the terms of the MIT license.

## Quick Links

*   [**API Reference**](reference/contracts.md)
*   [**Notebook Examples**](https://github.com/sweet-cross/crosscontract/tree/main/notebooks)
