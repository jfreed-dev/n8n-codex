# Contributing to n8n-codex

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/n8n-codex.git
   cd n8n-codex
   ```
3. Copy the environment template:
   ```bash
   cp .env.example .env
   # Fill in required values
   ```
4. Start the development stack:
   ```bash
   docker compose up -d
   ```

## Development Setup

### Claude Agent (Python)

```bash
cd claude-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run tests
pytest tests/ -v
```

### n8n Workflows

1. Make changes in the n8n UI (http://localhost:5678)
2. Export workflows via `Import from File` → select workflow → export
3. Save to `workflows/` directory

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates

### Commit Messages

Write clear, concise commit messages:
- Use present tense ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issues when applicable ("Fix #123")

### Code Style

**Python (claude-agent):**
- Follow PEP 8
- Use type hints where practical
- Run `ruff check src/` before committing

**Workflows:**
- Use environment variables for secrets (`$env.VAR_NAME`)
- Enable `allowUnauthorizedCerts` for self-signed certs
- Add meaningful node names

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure CI passes:
   - Lint check (ruff)
   - Tests (pytest)
   - Docker build
4. Update documentation if needed
5. Submit a PR with a clear description
6. Address review feedback

## Testing

### Running Tests Locally

```bash
# Python tests
cd claude-agent
pytest tests/ -v

# Validate docker-compose
docker compose config --quiet

# Validate workflow JSON
python -m json.tool workflows/*.json > /dev/null
```

### Manual Testing

1. Start the stack: `docker compose up -d`
2. Check service health:
   ```bash
   curl http://localhost:8080/api/health  # Claude Agent
   curl http://localhost:5678/healthz     # n8n
   ```
3. Test Slack integration by mentioning the bot

## Reporting Issues

- Use the issue templates provided
- Include relevant logs (`docker compose logs -f <service>`)
- Describe your environment (OS, Docker version)

## Security

- Never commit secrets or API keys
- Report security vulnerabilities privately (see SECURITY.md)
- Use environment variables for all sensitive configuration

## Questions?

Open a discussion or issue if you need help getting started.
