# MasterChief DevOps Scripts Library

Comprehensive collection of production-ready DevOps automation scripts organized by category.

## Directory Structure

```
scripts/devops/
├── deployment/      - Application and service deployment scripts
├── infrastructure/  - Infrastructure provisioning and management
├── cicd/           - CI/CD pipeline automation
├── monitoring/     - Health checks and monitoring
├── security/       - Security scanning and compliance
├── database/       - Database operations and management
└── utils/          - Utility and helper scripts
```

## Deployment Scripts

### deploy-app.sh
Generic application deployment with validation and rollback support.

**Usage:**
```bash
./deploy-app.sh --app myapp --env prod --version 1.2.3
./deploy-app.sh --app myapp --env staging --dry-run
```

**Options:**
- `--app APP_NAME` - Application name (required)
- `--env ENVIRONMENT` - Target environment: dev, staging, prod (required)
- `--version VERSION` - Application version (default: latest)
- `--dry-run` - Preview changes without applying
- `--help` - Show usage information

### deploy-docker.sh
Docker container deployment and management.

**Usage:**
```bash
./deploy-docker.sh --image nginx:latest --name web-server
```

### rollback.sh
Rollback a deployment to the previous version.

**Usage:**
```bash
./rollback.sh --app myapp --env prod
```

## Infrastructure Scripts

### provision-vm.sh
Provision virtual machines on cloud providers (Azure, AWS, GCP).

**Usage:**
```bash
./provision-vm.sh --provider azure --name my-vm
```

## CI/CD Scripts

### build-docker.sh
Build Docker images with proper tagging.

**Usage:**
```bash
./build-docker.sh --tag myapp:1.0.0 --file Dockerfile
```

## Monitoring Scripts

### check-health.sh
Health endpoint checker for services.

**Usage:**
```bash
./check-health.sh --url https://api.example.com/health --timeout 30
```

## Security Scripts

### scan-vulnerabilities.sh
Scan for CVE vulnerabilities in applications and dependencies.

**Usage:**
```bash
./scan-vulnerabilities.sh --target ./src
```

## Database Scripts

### backup-database.sh
Create database backups with timestamp.

**Usage:**
```bash
./backup-database.sh --db production_db --output /backups
```

## Utility Scripts

### cleanup-resources.sh
Clean up unused resources and artifacts.

**Usage:**
```bash
./cleanup-resources.sh --type containers --dry-run
./cleanup-resources.sh --type images
```

## Common Features

All scripts include:

- ✅ Error handling with `set -euo pipefail`
- ✅ Help documentation via `--help` flag
- ✅ Dry-run mode for safe testing
- ✅ Colored logging output
- ✅ Proper exit codes
- ✅ Input validation

## Integration

These scripts can be:

1. **Executed directly** from the command line
2. **Invoked via CLI** using `masterchief script run <name>`
3. **Generated/customized** using the Script Wizard
4. **Automated** in CI/CD pipelines
5. **Managed** through the Mission Control Dashboard

## Extension

To add new scripts:

1. Place script in appropriate category directory
2. Follow the template structure (shebang, help, error handling)
3. Make executable: `chmod +x script.sh`
4. Update this README with documentation
5. Register with CLI if needed

## Examples

```bash
# Deploy application with dry-run
cd deployment
./deploy-app.sh --app myapi --env staging --version 2.1.0 --dry-run

# Build and health check
cd cicd
./build-docker.sh --tag myapi:2.1.0
cd ../monitoring
./check-health.sh --url http://localhost:8080/health

# Database backup
cd database
./backup-database.sh --db mydb --output /backups/$(date +%Y%m%d)

# Security scan
cd security
./scan-vulnerabilities.sh --target /app/src
```

## See Also

- [Platform Documentation](../../docs/)
- [Script Wizard](../../platform/script_wizard/)
- [CLI Reference](../../core/cli/)
