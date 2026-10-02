#!/usr/bin/env python3
"""
MasterChief CLI - Command-line interface for the MasterChief DevOps platform
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directories to path for imports
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from core.config.manager import ConfigManager
from core.logging.logger import initialize_logger, get_platform_logger


def setup_logging(verbose=False):
    """Initialize platform logging"""
    log_level = "DEBUG" if verbose else "INFO"
    initialize_logger(log_level=log_level)
    return get_platform_logger().get_logger("cli")


def list_modules(args):
    """List all available modules"""
    logger = setup_logging(args.verbose)
    
    try:
        # Import module loader
        from core.module_loader import ModuleLoader
        
        loader = ModuleLoader()
        modules = loader.list_modules()
        
        if args.type:
            modules = [m for m in modules if m.get('type') == args.type]
        
        print(f"\nFound {len(modules)} modules:\n")
        
        for module in modules:
            print(f"  • {module['name']} (v{module['version']})")
            print(f"    Type: {module['type']}")
            print(f"    Description: {module['description']}")
            print()
        
        return 0
    except Exception as e:
        logger.error(f"Error listing modules: {e}")
        return 1


def show_config(args):
    """Show configuration for an environment"""
    logger = setup_logging(args.verbose)
    
    try:
        config_mgr = ConfigManager()
        config_mgr.load_global_config()
        config_mgr.load_environment(args.environment)
        
        config = config_mgr.get_config(args.environment)
        
        print(f"\nConfiguration for environment: {args.environment}\n")
        print(json.dumps(config, indent=2))
        
        return 0
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return 1


def validate_module(args):
    """Validate a module"""
    logger = setup_logging(args.verbose)
    
    try:
        module_path = Path(args.module_path)
        
        if not module_path.exists():
            logger.error(f"Module path not found: {module_path}")
            return 1
        
        # Check for required files based on module type
        required_files = {
            'terraform': ['main.tf', 'variables.tf', 'outputs.tf', 'versions.tf', 'module.yaml'],
            'ansible': ['module.yaml'],
            'powershell-dsc': ['module.yaml']
        }
        
        manifest_file = module_path / 'module.yaml'
        if not manifest_file.exists():
            logger.error("Module manifest (module.yaml) not found")
            return 1
        
        # Load and validate manifest
        import yaml
        with open(manifest_file, 'r') as f:
            manifest = yaml.safe_load(f)
        
        module_type = manifest.get('type')
        logger.info(f"Validating {module_type} module: {manifest.get('name')}")
        
        # Check required files
        if module_type in required_files:
            missing_files = []
            for file in required_files[module_type]:
                if not (module_path / file).exists():
                    missing_files.append(file)
            
            if missing_files:
                logger.error(f"Missing required files: {', '.join(missing_files)}")
                return 1
        
        logger.info("✓ Module validation passed")
        return 0
        
    except Exception as e:
        logger.error(f"Error validating module: {e}")
        return 1


def init_module(args):
    """Initialize a new module from template"""
    logger = setup_logging(args.verbose)
    
    try:
        module_type = args.type
        module_name = args.name
        
        # Create module directory
        module_dir = Path(f"modules/{module_type}/{module_name}")
        module_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating {module_type} module: {module_name}")
        
        # Copy template files
        template_dir = Path(f"modules/templates/{module_type}")
        if template_dir.exists():
            import shutil
            for item in template_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, module_dir / item.name)
            logger.info(f"✓ Copied template files")
        
        # Create basic module.yaml
        manifest = {
            'name': module_name,
            'version': '1.0.0',
            'type': module_type,
            'description': f'{module_name} module',
            'author': 'MasterChief Platform',
            'dependencies': [],
            'inputs': {},
            'outputs': {},
            'metadata': {}
        }
        
        import yaml
        with open(module_dir / 'module.yaml', 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)
        
        logger.info(f"✓ Module created at: {module_dir}")
        logger.info("Edit the module files to implement your configuration")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error initializing module: {e}")
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='MasterChief DevOps Automation Platform CLI'
    )
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List modules command
    list_parser = subparsers.add_parser('list', help='List available modules')
    list_parser.add_argument('--type', choices=['terraform', 'ansible', 'powershell-dsc'],
                            help='Filter by module type')
    list_parser.set_defaults(func=list_modules)
    
    # Show config command
    config_parser = subparsers.add_parser('config', help='Show environment configuration')
    config_parser.add_argument('environment', help='Environment name (dev, staging, prod)')
    config_parser.set_defaults(func=show_config)
    
    # Validate module command
    validate_parser = subparsers.add_parser('validate', help='Validate a module')
    validate_parser.add_argument('module_path', help='Path to module directory')
    validate_parser.set_defaults(func=validate_module)
    
    # Init module command
    init_parser = subparsers.add_parser('init', help='Initialize a new module')
    init_parser.add_argument('type', choices=['terraform', 'ansible', 'powershell-dsc'],
                            help='Module type')
    init_parser.add_argument('name', help='Module name')
    init_parser.set_defaults(func=init_module)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
