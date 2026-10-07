#!/usr/bin/env python3
"""
MasterChief Import Wizard - Function-Based Feature Register
Crawls the workspace directory, analyzes Python scripts via AST, 
and maps them into data/modules.json as optional toggleable entities.
"""

import ast
import json
import os
from pathlib import Path


class FeatureASTParser(ast.NodeVisitor):
    """Parses a Python file to inventory entry points and find DevOps hooks."""
    def __init__(self, file_path: Path, base_path: Path):
        self.file_path = file_path
        self.module_dot_path = file_path.stem
        self.metadata = {
            "module": self.module_dot_path,
            "description": "Custom standalone optional feature.",
            "exposed_functions": [],
            "exposed_classes": [],
            "devops_phase_hints": []
        }

    def parse(self):
        try:
            content = self.file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(self.file_path))
            
            # Extract high-level module docstring if it exists
            docstring = ast.get_docstring(tree)
            if docstring:
                self.metadata["description"] = docstring.split('\n')[0]
                
            self.visit(tree)
        except Exception:
            pass # Gracefully handle files mid-refactor
        return self.metadata

    def visit_FunctionDef(self, node):
        """Identifies top-level function blueprints."""
        # Filter internal helpers starting with underscores
        if not node.name.startswith('_'):
            self.metadata["exposed_functions"].append(node.name)
            
            # Map semantic keywords to target platform workloads
            keywords = ["deploy", "build", "pipeline", "webhook", "kafka", "pika", "auth", "voice"]
            for kw in keywords:
                if kw in node.name.lower():
                    self.metadata["devops_phase_hints"].append(kw)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Inventories core tracking structures and definitions."""
        if not node.name.startswith('_'):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
            self.metadata["exposed_classes"].append({
                "class_name": node.name,
                "methods": methods
            })
        self.generic_visit(node)


def build_optional_features_manifest(repo_root: str = "."):
    base_path = Path(repo_root).resolve()
    config_db = base_path / "data" / "modules.json"
    
    # Establish dynamic backup baseline for your configuration registry
    if config_db.exists():
        try:
            with open(config_db, "r", encoding="utf-8") as f:
                features_registry = json.load(f)
        except json.JSONDecodeError:
            features_registry = {}
    else:
        features_registry = {}

    print(f"[*] Running MasterChief Feature Import Wizard over: {base_path}")
    
    # Discover standalone python modules matching glob compilation parameters
    py_files = [
        f for f in base_path.glob("*.py")
        if f.name not in ("setup.py", "conftest.py", "main.py", "main backup.py", "feature_wizard.py")
        and not f.name.startswith("_")
    ]

    registered_count = 0
    for file_path in py_files:
        parser = FeatureASTParser(file_path, base_path)
        parsed_meta = parser.parse()
        
        feature_key = f"optional_{file_path.stem}"
        
        # Preserve user state checkboxes (enabled/disabled toggles) if already registered
        if feature_key in features_registry:
            # Sync functional signature updates without overwriting target operational states
            features_registry[feature_key]["exposed_functions"] = parsed_meta["exposed_functions"]
            features_registry[feature_key]["exposed_classes"] = parsed_meta["exposed_classes"]
            continue

        # Inject unified contract configuration matching your MODULES_TEMPLATE expectations
        features_registry[feature_key] = {
            "enabled": False,  # Default to False so it remains strictly an out-of-band optional choice
            "type": "optional_feature",
            "source_file": file_path.name,
            "description": parsed_meta["description"],
            "db_path": f"data/{file_path.stem}_state.json",
            "exposed_functions": parsed_meta["exposed_functions"],
            "exposed_classes": parsed_meta["exposed_classes"],
            "tags": list(set(parsed_meta["devops_phase_hints"]))
        }
        registered_count += 1

    # Save to disk
    config_db.parent.mkdir(parents=True, exist_ok=True)
    with open(config_db, "w", encoding="utf-8") as f:
        json.dump(features_registry, f, indent=4)

    print(f"[+] Scan successful. Registered {registered_count} scripts as optional dashboard features.")


if __name__ == "__main__":
    build_optional_features_manifest()
