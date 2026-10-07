# Changelog

All notable changes to the MasterChief Enterprise DevOps Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.0.0] - 2026-10-06

### Added
- Guided architecture-to-code workflow in the Terraform Wizard, with starter designs, component selection, live Terraform previews, and downloadable module packages.
- Blueprint-style architecture diagrams with grouped virtual networks and subnets, labeled hub-and-spoke peerings, and SVG/Visio export.
- Local Terraform validation scaffolding, optional storage-emulator guidance, isolated Azure sandbox instructions, and validate/plan CI/CD starter templates.
- Code archetypes with architecture previews, code scaffolding, and explicit editor handoff.
- Expanded Echo script-library and command-catalog workflows, Roku playlist/EPG support, and the associated navigation, diagnostics, and integration updates included in this milestone.
- Local pipeline YAML/JSON import and export, parallel-stage execution, persisted run history, and manual approval gates; Terraform Apply stages require explicit approval.
- An Observability Center for existing Prometheus, Grafana, and Loki installations, plus low-cardinality HTTP metrics, matching dashboards/alerts, and scrape guidance.
- Admin-only, confirmation-gated source-bundle staging for local Windows/Linux, WSL/WSL2, and USB destinations, with unsupported destinations identified as future work.
- A custom MasterChief Echo Starlite wordmark shown in the shared shell and on standalone HTML pages.
- Fresh source-install instructions with a clear separation between base, optional, and development dependencies.

### Changed
- Terraform architecture previews use a legible blueprint layout rather than radial component placement and display CIDR ranges without object-string artifacts.
- Architecture generation remains review-first: generated infrastructure is not automatically applied.
- Observability service URLs and bearer tokens are configured on the server; no monitoring stack is installed or started automatically.
- Deployment Center creates non-overwriting source archives only; it does not install or start the app, access cloud infrastructure, or implement the future targets.
- Production database password configuration uses the existing Vault-reference pattern rather than a checked-in literal.
- About and Feature Management pages describe the 4.0 milestone and distinguish available workflows from external services that still require credentials or configuration.

### Notes
- CI/CD templates validate and plan only; they do not include an automatic apply stage.
- Local emulation is limited to the services explicitly provided by the selected emulator; it does not emulate Azure networking, SQL, AKS, identity, or ExpressRoute.
- Azure resources are not deployed as part of this release.
- Five legacy IRC voice-automation test modules are explicitly skipped when their corresponding source modules are absent from the checkout.

## [2.2.8] - 2026-10-01

### Added
- One-command cross-platform setup instructions and the prompted `MASTER_SETUP.ps1` menu.
- PyPI extras for optional audio, async, database, and utility dependencies.
- Combined PyPI and Chocolatey deployment script with preflight and dry-run support.

### Changed
- First-run scripts bootstrap a virtual environment without downloading AI models by default.
- Chocolatey packaging pins its source archive and verifies its SHA-256 checksum.

## [2.2.6] - 2026-05-30

### Added
- GitHub Actions workflow directory restored (`ci.yml`, `chocolatey.yml`, `ansible-validation.yml`, `dsc-validation.yml`, `module-loader-tests.yml`, `terraform-validation.yml`).
- New `pypi-publish.yml` workflow: publishes to PyPI automatically on GitHub release or version tag push using OIDC trusted publishing.
- `ai` extras group in `setup.py` for optional local GGUF/ML dependencies.
- `all` extras group flattened to an explicit list to avoid self-referential packaging issues.

### Changed
- `requirements-optional.txt`: `llama-cpp-python` install now gated to `python_version < "3.14"` to prevent broken wheel installs on Python 3.14.
- `requirements.txt`: full-platform install command added to header comments.
- `setup.py` docstring version updated to 2.2.6 / May 2026.
- `echo/runtime/model_runtime.py`: rebuilt as plain module-level functions; eliminates `TypeError: 'classmethod' object is not callable` at startup.
- `main.py`: missing `llama_cpp` on startup now logs a warning instead of a traceback. Fixed two embedded-JS regex escape sequences that triggered Python `SyntaxWarning`.

### Fixed
- `data/echo_training/learned_patterns.json`: cleared git conflict markers and rewritten as valid UTF-8 JSON to stop parse errors at startup.
- `README.md`: replaced duplicated/concatenated historical content with a single current source of truth.

## [1.2.1] - 2026-02-06

### Added
- Training orchestration and UI (versioned release 1.2.1)
  - `/echo-train` web UI to start, monitor, and cancel training jobs.
  - Server-side training orchestration with stub and PEFT engine selection.
  - `tools/peft_train.py` minimal PEFT/LoRA training wrapper (template).
  - `tools/dataset_helpers.py` to convert resources into JSONL training examples.
  - `/api/resources/convert_to_training` to generate training files from resources.
  - Persistent training job metadata stored in `data/models_output/train_jobs.json`.
  - Background cleanup/archiving for old training artifacts.

### Changed
- Upload/resource handling
  - Server-side validation for resource uploads (allowed types, size limits, safe filenames).
  - Resources index improvements and UI preview fixes.

### Fixed
- Several resource endpoint NameError issues and improved error handling for resource preview.

## [1.2.1] - 2026-02-06

### Added
- Training orchestration (stub) and UI.
- Dataset helpers for JSONL conversion.
- Secure upload validation for resources.

### Notes
- The PEFT/LoRA training wrapper is a template; for efficient fine-tuning, GPU and additional dependencies are recommended. The default `stub` engine is suitable for CPU-only testing.


### Added
- **All-Inclusive Data Ingestion System for IRC Bot**
  - Comprehensive ingestion framework with base classes and manager
  - Webhook ingestion with support for:
    - GitHub webhooks (push, PR, issues)
    - GitLab webhooks
    - Jenkins CI/CD webhooks
    - Alertmanager alerts
    - PagerDuty incidents
    - Generic webhooks with HMAC signature validation
  - REST API ingestion with:
    - Multiple authentication methods (API key, Bearer, Basic, OAuth)
    - Configurable polling intervals
    - Response transformation support
    - Change detection
  - File-based ingestion with:
    - CSV, JSON, YAML, and XML format support
    - Watchdog-based file monitoring
    - File change detection (create, modify)
    - Glob pattern matching
    - Recursive directory watching
  - Database ingestion with:
    - PostgreSQL support (asyncpg)
    - MySQL support (aiomysql)
    - SQLite support (aiosqlite)
    - MongoDB support (motor)
    - Change detection and scheduled queries
  - Streaming data ingestion with:
    - Kafka consumer support
    - RabbitMQ queue consumer
    - Redis Pub/Sub support
    - Reliable message processing with acknowledgments
  - Log ingestion with:
    - Real-time log tailing
    - Syslog format parser
    - JSON log parser
    - Custom regex pattern support
    - Log rotation handling
  - Metrics ingestion with:
    - Prometheus query support
    - StatsD integration
    - InfluxDB query support
    - Threshold-based alerting
    - Configurable polling intervals
  - Extended BindType enum with 7 new ingestion types
  - Integration with existing IRC bot binding system
  - Comprehensive unit tests for all ingestion types
  - Updated architecture documentation with ingestion details
  - Complete examples documentation for all ingestion types
  - Configuration support in config.yml

### Changed
- Updated requirements.txt with ingestion dependencies:
  - watchdog for file monitoring
  - kafka-python for Kafka
  - pika for RabbitMQ
  - redis for Redis
  - asyncpg, aiomysql, aiosqlite, motor for databases
  - prometheus-client, statsd, influxdb-client for metrics

## [1.0.0] - 2026-01-12

### Added
- Core platform engine with module loader, config engine, and event bus
- CLI tool with commands: init, module, deploy, status, logs, interactive
- Terraform Azure modules for networking, compute, storage, database, and security
- Ansible roles for common configuration, security hardening, and monitoring
- IRC bot engine with TCL-inspired Python bindings
- Hierarchical configuration system (global, environment, module)
- Event-driven architecture for module communication
- Comprehensive documentation (architecture, runbooks, ADRs)
- Complete directory structure for enterprise DevOps platform
- Python package setup with dependencies
- Module manifest schema for plugin development
- Hot-reload capabilities for modules
- Secret reference resolution for Azure Key Vault
- Permission system for IRC bot commands
- Support for multiple environments (dev, staging, prod)

### Infrastructure Modules
- VNet with multi-tier subnet architecture
- AKS cluster with auto-scaling node pools
- Network security groups
- Storage accounts
- Database configurations

### Documentation
- Comprehensive README with quick start guide
- Architecture documentation with diagrams
- Runbooks for operations
- Module development guide
- API reference structure

### Configuration
- Global configuration templates
- Environment-specific configurations
- Example configurations for dev and prod

## [Unreleased]

### Added
- **Voice Automation System**: Full hands-free control using voice commands
  - Wake word detection (OpenWakeWord, Porcupine, Whisper)
  - Speech-to-text using OpenAI Whisper
  - Text-to-speech using pyttsx3
  - Natural language command processing with Ollama LLM or pattern matching
  - Multi-turn conversation management with context awareness
  - Voice control for scripts, deployments, monitoring, and system management
  - Audio feedback system with chimes and confirmations
  - IRC integration for voice commands
  - Comprehensive voice automation documentation
  - Voice cloning module (placeholder for future implementation)
  - Voice announcements for IRC events
- Comprehensive script automation suite with AI generation, templates, validation, and scheduling
- AI script generation using local LLMs via Ollama (CodeLlama, Llama2, Mistral)
- Voice-to-script functionality with STT/TTS integration
- 10+ pre-built script templates for backup, monitoring, deployment, security, and maintenance
- Script validation with security scanning and dangerous command detection
- Script scheduling with cron-based recurring execution and history tracking
- Template manager with Jinja2 variable substitution
- Script validator with shellcheck and ruff integration
- Execution history tracking and notifications
- Enhanced ScriptManager with automation features
- Comprehensive test suite for script automation
- Documentation for script automation features (docs/guides/script-automation.md)
- Voice cloning capability for IRC Bot
  - XTTS/Coqui TTS implementation (primary, recommended)
  - Tortoise TTS implementation (high quality option)
  - OpenVoice implementation (fast cloning option)
  - Voice profile management system
  - Master voice persona for bot
  - Interactive voice sample recording
  - CLI for voice cloning operations
  - Voice training utilities
  - Comprehensive documentation and examples
- Local voice/audio system for IRC bot with offline processing
- Text-to-Speech (TTS) engine using pyttsx3
- Speech-to-Text (STT) engine using OpenAI Whisper (local)
- Audio recording with sounddevice and voice activity detection (VAD)
- Audio playback for WAV, MP3, OGG formats using pygame
- Event-based audio announcements for deployments and alerts
- Voice command bindings (VOICE, TTS, AUDIO) in IRC bot
- VoiceEngine class for coordinating all voice components
- Configurable voice settings (voice, rate, volume, model size)
- Queue-based speech synthesis for multiple TTS requests
- Real-time voice transcription with multiple Whisper model sizes
- Example voice bot implementation in docs/examples/voice-bot-example.py
- Unit tests for voice system components

### Planned
- PowerShell DSC configurations
- Kubernetes Helm charts and Kustomize overlays
- Web IDE with Monaco Editor
- Script library and addon manager
- System management dashboard
- CMDB and asset tracking
- Observability dashboards
- CI/CD pipeline templates
- GitOps configurations
- Disaster recovery automation
- Chaos engineering experiments
