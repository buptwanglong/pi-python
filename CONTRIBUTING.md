# Contributing to Basket-Python

Thank you for your interest in contributing. This project follows the architecture of [pi-mono](https://github.com/badlogic/pi-mono).

## Development workflow

1. **Fork the repository** on GitHub.
2. **Clone your fork** and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and add tests for new functionality.
4. **Ensure all tests pass** (see below).
5. **Submit a pull request** against the main repository’s `main` branch.

## Development environment

- **Python**: 3.12+
- **Package manager**: [Poetry](https://python-poetry.org/)

From the repository root:

```bash
poetry install
```

This installs the root project’s dev dependencies and resolves path dependencies for all packages in the monorepo.

## Running tests

Tests are located under `packages/*/tests`. From the **repository root**:

```bash
poetry run pytest -v
```

Root `pyproject.toml` configures `testpaths = ["packages/*/tests"]`, so this runs tests for all packages. To run tests for a single package:

```bash
cd packages/basket-assistant
poetry run pytest -v
```

## Code style

- **PEP 8**: Follow standard Python style.
- **Type hints**: Use type annotations (Python 3.12+).
- **Docstrings**: Document public modules, classes, and functions.
- **Tests**: Add or update tests for new features and bug fixes.

The root [pyproject.toml](pyproject.toml) configures:

- **Black** (line length 100, Python 3.12)
- **Ruff** (E, F, I, N, W, UP)
- **Mypy** (strict mode)

Before submitting a PR, run from the repo root:

```bash
poetry run black .
poetry run ruff check .
poetry run mypy packages/
```

(Adjust paths if mypy is only run on certain packages.)

## Before submitting a PR

- [ ] All tests pass: `poetry run pytest -v`
- [ ] No leftover debug code or temporary edits
- [ ] New code follows the project’s style (Black, Ruff, type hints)

For more detail on the project structure and packages, see the main [README.md](README.md).
