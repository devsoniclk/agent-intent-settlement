# Contributing to Agent Intent Settlement Engine

We welcome community contributions, bug fixes, algorithmic enhancements, and venue connectors.

## Development Workflow

1. Fork the repository and create your feature branch from `main`:
   ```bash
   git checkout -b feature/new-venue-connector
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run test suites and ensure 100% pass rate:
   ```bash
   pytest --cov=agent_intent_settlement tests/
   ```

4. Format and lint code:
   ```bash
   ruff check .
   ```

5. Submit a Pull Request with a clear description of the problem solved.
