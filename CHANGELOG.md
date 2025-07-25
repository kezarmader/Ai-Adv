# Changelog

All notable changes to the AI Advertisement Generator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive structured JSON logging across all services
- Request tracing with unique IDs across microservices  
- Performance timing for all operations with millisecond precision
- GPU memory usage tracking for optimization
- Health check scripts (PowerShell and Python versions)
- Automatic image cleanup after 10 minutes
- Enhanced error handling with detailed context
- Production-ready log rotation configuration

### Changed
- Updated README with comprehensive documentation
- Improved API response format with detailed ad_text structure
- Enhanced troubleshooting section with more scenarios
- Added performance expectations and timing information

### Security
- No PII logging policy implemented
- Request isolation with unique tracking IDs
- Automatic temporary file cleanup
- Local processing guarantee (no external data transmission)

## [1.0.0] - 2025-07-25

### Added
- Initial release of AI Advertisement Generator
- Microservices architecture with 4 services:
  - Orchestrator service (FastAPI)
  - LLM service (Ollama with Llama3)
  - Image Generator service (Stable Diffusion XL)
  - Poster service (Mock publishing)
- Docker Compose deployment configuration
- NVIDIA GPU support for AI processing
- Temporary image storage with automatic cleanup
- RESTful API for advertisement generation
- Brand text and CTA overlay on generated images
- Amazon ASIN reference integration

### Documentation
- Comprehensive README with setup instructions
- API documentation with parameter descriptions
- Docker deployment guide
- Hardware requirements specification
- Usage examples for PowerShell and curl

### Security
- Privacy-conscious design with no PII storage
- Temporary image deletion after 10 minutes
- Local processing without external API calls
- Docker network isolation between services

---

## Release Types

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes
