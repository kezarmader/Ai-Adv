# Contributing to AI Advertisement Generator

Thank you for your interest in contributing! This document provides detailed guidelines for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). 

**Quick summary**: Be respectful, inclusive, and constructive.

## Development Setup

### Prerequisites
- Python 3.11+
- Docker Desktop with NVIDIA Container Toolkit
- NVIDIA GPU with CUDA support
- Git

### Local Development Environment

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/your-username/Ai-Adv.git
   cd Ai-Adv
   ```

2. **Create a virtual environment for each service**:
   ```powershell
   # Orchestrator
   cd orchestrator
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cd ..

   # Image Generator  
   cd image-generator
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cd ..

   # Poster Service
   cd poster-service  
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cd ..
   ```

3. **Test the setup**:
   ```powershell
   docker-compose up --build
   .\health_check.ps1
   ```

## Coding Standards

### Python Code Style
- Follow **PEP 8** style guidelines
- Use **type hints** for function parameters and return values
- Maximum line length: **88 characters** (Black formatter standard)
- Use **descriptive variable and function names**

### Logging Standards
- Use structured logging from `logging_config.py`
- Include relevant context in log messages
- Use appropriate log levels:
  - `DEBUG`: Detailed debugging information
  - `INFO`: Normal operation events
  - `WARNING`: Recoverable issues
  - `ERROR`: Error conditions that need attention

### Error Handling
- Always include proper exception handling
- Log errors with sufficient context
- Use appropriate HTTP status codes in FastAPI endpoints
- Provide meaningful error messages to users

### Example Code Structure
```python
from logging_config import setup_logging, TimingContext

logger = setup_logging("service-name")

@app.post("/endpoint")
async def endpoint_function(data: RequestModel):
    """
    Brief description of the endpoint.
    
    Args:
        data: Request data model with validation
        
    Returns:
        Response model with generated content
        
    Raises:
        HTTPException: When validation or processing fails
    """
    with TimingContext("operation_name", logger) as timer:
        try:
            # Implementation here
            logger.info("Operation completed", extra={
                "operation": "operation_name",
                "duration_ms": timer.duration_ms
            })
            return result
        except Exception as e:
            logger.error("Operation failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=500, detail="Operation failed")
```

## Testing Guidelines

### Manual Testing
1. **Run health checks**: `.\health_check.ps1`
2. **Test API endpoints** using the examples in README.md
3. **Check logs** for errors: `docker-compose logs -f`
4. **Monitor performance** using timing logs

### Integration Testing
- Test complete ad generation pipeline
- Verify image generation and cleanup
- Test error scenarios (invalid input, GPU memory issues)
- Validate logging output format

### Performance Testing
- Monitor response times using structured logs
- Test with different GPU memory configurations
- Verify image cleanup timing (10-minute expiration)

## Pull Request Process

### Before Submitting
1. **Run health checks**: Ensure `.\health_check.ps1` passes
2. **Test your changes**: Verify functionality works as expected
3. **Check logs**: Ensure no new errors in structured logs
4. **Update documentation**: Modify README.md if needed
5. **Update CHANGELOG.md**: Add your changes under `[Unreleased]`

### PR Description Template
When creating a pull request, GitHub will automatically load the PR template with the required sections. Make sure to fill out all relevant sections completely.

### Review Process
1. **Automated checks** must pass
2. **Manual review** by maintainers
3. **Testing verification** in different environments
4. **Documentation review** for completeness

## Issue Guidelines

### Bug Reports
Use this template for bug reports:

```markdown
**Bug Description**
A clear description of what the bug is.

**Environment**
- OS: [e.g., Windows 11, Ubuntu 22.04]
- Docker Desktop Version: [e.g., 4.15.0]
- GPU Model: [e.g., RTX 4090]
- VRAM: [e.g., 24GB]

**Steps to Reproduce**
1. Start services with `docker-compose up`
2. Send request to /run endpoint
3. Error occurs...

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Logs**
```
[Paste relevant logs from docker-compose logs here]
```

**Additional Context**
Any other context about the problem.
```

### Feature Requests
Use this template for feature requests:

```markdown
**Feature Description**
A clear description of what feature you'd like to see added.

**Use Case**
Describe the problem this feature would solve.

**Proposed Solution**
Describe how you envision this feature working.

**Alternatives Considered**
Describe alternative solutions you've considered.

**Additional Context**
Any other context or screenshots about the feature request.
```

## Development Workflow

### Branching Strategy
- `main` - Production-ready code
- `develop` - Integration branch for features  
- `feature/feature-name` - Feature development branches
- `hotfix/fix-name` - Critical bug fixes

### Commit Messages
Use conventional commit format:
```
type(scope): brief description

Longer description if needed

Fixes #issue-number
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Release Process
1. Update version numbers
2. Update CHANGELOG.md
3. Create release tag
4. Build and test Docker images
5. Update documentation

## Getting Help

- **General questions**: GitHub Discussions
- **Bug reports**: GitHub Issues with bug template
- **Feature requests**: GitHub Issues with feature template
- **Security issues**: Contact maintainers directly

Thank you for contributing to the AI Advertisement Generator! 🚀
