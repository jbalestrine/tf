# MasterChief Enterprise DevOps Platform - Quick Start Guide

## Installation

### One-command setup from source

From the parent directory, run the command for your shell. It clones the repo, installs the base app and CLI, then starts the web app on the local machine.

PowerShell:

```powershell
git clone https://github.com/jbalestrine/masterchief.git; if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }; Set-Location masterchief; Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\MasterchiefRun.ps1 -Port 8080
```

Linux/macOS:

```bash
git clone https://github.com/jbalestrine/masterchief.git && cd masterchief && bash scripts/start.sh
```

If already cloned, run `.\MasterchiefRun.ps1 -Port 8080` in PowerShell or `bash scripts/start.sh` in a POSIX shell. The Windows source runner binds to `0.0.0.0:8080` by default; open `http://localhost:8080/` on the host or use the host's IP on a reachable network. Authenticated users receive GOD access, so limit network access to trusted clients. Cloud operations use the user's supplied provider credentials and are limited by those credentials' IAM permissions. The POSIX starter runs `run.py`; use the URL printed by its startup output.

For exact Windows, line-by-line setup instructions, optional dependency guidance, and the matching local launch command, see the [primary README](README.md#fresh-setup).

The About page checks the latest version in `jbalestrine/masterchief`. Because that repository is private, set `GITHUB_TOKEN` to a read-only repository token in the app's environment if you want the version check to succeed; the token is sent only from the server to GitHub and is not returned to the browser. `GITHUB_REPO` can override the repository identifier.

The Observability Center is at `/observability`. To connect existing services, set the following in the server environment (or `.env`) and restart MasterChief:

```dotenv
PROMETHEUS_URL=http://prometheus.example:9090
GRAFANA_URL=http://grafana.example:3000
LOKI_URL=http://loki.example:3100
# Optional read-only bearer tokens; never put secrets in browser code:
# PROMETHEUS_TOKEN=
# GRAFANA_API_TOKEN=
# LOKI_TOKEN=
# METRICS_TOKEN=
```

MasterChief exposes HTTP counters and latency histograms at `/metrics`, restricted to loopback unless `METRICS_TOKEN` is configured. Point Prometheus at that endpoint using [observability/prometheus-scrape-example.yml](observability/prometheus-scrape-example.yml). Grafana dashboards and alert rules are supplied under `observability/`; Loki log queries need a configured log shipper. No monitoring services are installed or started automatically.

The base install does not download local AI models. To install all optional integrations, run:

```bash
python -m pip install -r requirements-optional.txt
```

To install only selected groups from the repository root, use extras such as `python -m pip install -e ".[ai]"`, `python -m pip install -e ".[audio]"`, or `python -m pip install -e ".[cloud]"`. For development and tests, install `requirements-dev.txt` instead of adding test tools to a production environment.

### From PyPI

```bash
python -m pip install --upgrade masterchief
masterchief --help
```

### Run the CLI from source

```bash
python -m core.cli.main --help
python -m core.cli.main status
python -m core.cli.main module list
```

## Quick Examples

### Initialize a Project

```bash
python -m core.cli.main init --name myproject --path ./myproject
cd myproject
```

### List Available Modules

```bash
python -m core.cli.main module list
```

### Deploy Infrastructure

```bash
python -m core.cli.main deploy --plan
python -m core.cli.main deploy --auto-approve
```

### Interactive Mode

```bash
python -m core.cli.main interactive
```

## Core Components

### 1. Module Loader
Dynamic plugin system with hot-reload capabilities located in `core/module_loader/`

### 2. Configuration Engine
Hierarchical configuration management in `core/config_engine/`

### 3. Event Bus
Pub/sub messaging system in `core/event_bus/`

### 4. CLI Tool
Command-line interface in `core/cli/`

## Infrastructure Modules

### Terraform (Azure)
- **Networking**: VNets, subnets, NSGs (`modules/terraform/azure/networking/`)
- **Compute**: AKS clusters (`modules/terraform/azure/compute/`)
- **Storage**: Storage accounts (templates ready)
- **Database**: SQL, Cosmos DB (templates ready)

### Ansible
- **Common**: Baseline server configuration
- **Security**: Hardening and compliance
- **Monitoring**: Agent installation

### Kubernetes
- **Manifests**: Namespace, RBAC configurations
- **Helm Charts**: Application deployment
- **Kustomize**: Environment overlays

### PowerShell DSC
- **WebServerConfig**: IIS configuration

## ChatOps

### IRC Bot Engine
Python-based bot with TCL-inspired bindings:

```python
bot.bind("pub", "-|-", "!deploy", deploy_handler)
bot.bind("msg", "-|-", "!status", status_handler)
```

See `docs/examples/irc-bot-example.py` for complete example.

## Documentation

- **Architecture**: `docs/architecture/README.md`
- **Runbooks**: `docs/runbooks/README.md`
- **ADRs**: `docs/adrs/`
- **Examples**: `docs/examples/`

## Configuration

Configuration files use hierarchical loading:

1. **Global**: `config/global/config.yaml`
2. **Environment**: `config/environments/{env}.yaml`
3. **Module**: Module-specific configs

Example:
```yaml
# config/environments/prod.yaml
environment: prod
debug: false
azure:
  subscription_id: "${env:AZURE_SUBSCRIPTION_ID}"
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/unit/ -v

# With coverage
pytest --cov=core --cov=modules
```

### Code Quality

```bash
# Formatting
black core/ modules/

# Linting
flake8 core/ modules/

# Type checking
mypy core/
```

## Project Structure

```
masterchief/
├── core/                   # Core platform
│   ├── module_loader/     # Module system
│   ├── config_engine/     # Configuration
│   ├── event_bus/         # Event messaging
│   └── cli/               # CLI tool
├── modules/               # Infrastructure modules
│   ├── terraform/         # Terraform templates
│   ├── ansible/           # Ansible playbooks
│   ├── kubernetes/        # K8s manifests
│   └── powershell-dsc/    # DSC configs
├── chatops/               # IRC bot
├── observability/         # Monitoring
├── config/                # Configuration
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## Next Steps

1. Read the [Architecture Documentation](docs/architecture/README.md)
2. Try the [Azure Deployment Example](docs/examples/azure-deployment.md)
3. Explore [Runbooks](docs/runbooks/README.md)
4. Review [ADRs](docs/adrs/) for design decisions

## Support

- **Issues**: [GitHub Issues](https://github.com/jbalestrine/masterchief/issues)
- **Documentation**: [Wiki](https://github.com/jbalestrine/masterchief/wiki)

## License

MIT License - See [LICENSE](LICENSE) file for details.
