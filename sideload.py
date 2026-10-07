import os
import base64
from flask import Blueprint, jsonify, request

# Create a master blueprint to hook directly into MasterChief's main.py router
ide_sideload_bp = Blueprint('ide_sideload', __name__)

# The specific workspace directories your MasterChief platform relies on
WHITELISTED_TRACKING_DIRS = [
    "blueprints",
    "managers",
    "core/cli/commands",
    "scripts/devops/deployment",
    "scripts/devops/infrastructure",
    "scripts/devops/security"
]

def build_dynamic_node(display_name, absolute_path, root_workspace):
    """Recursively walks directories to map code files for the Web UI."""
    node = {"name": display_name, "type": "dir", "children": []}

    try:
        for entry in os.scandir(absolute_path):
            if entry.is_dir() and not entry.name.startswith((".", "__pycache__")):
                node["children"].append(build_dynamic_node(entry.name, entry.path, root_workspace))
            elif entry.is_file():
                # Only bundle files your IDE can read/execute safely
                if entry.name.endswith((".py", ".ps1", ".sh", ".json", ".yaml", ".yml")):
                    rel_path = os.path.relpath(entry.path, root_workspace)
                    # base64 encode the path to safely pass it via window links without escaping issues
                    b64_path = base64.b64encode(rel_path.encode('utf-8')).decode('utf-8')

                    node["children"].append({
                        "name": entry.name,
                        "type": "file",
                        "rel_path": rel_path,
                        "b64_path": b64_path,
                        "size": entry.stat().st_size
                    })
    except Exception as e:
        pass
    return node

@ide_sideload_bp.route('/api/ide/master_tree', methods=['GET'])
def get_sideloaded_workspace_tree():
    """Generates the master file architecture manifest including all core and orphan nodes."""
    root_workspace = os.getcwd()
    master_tree = {
        "name": "MasterChief Integrated UI Core",
        "type": "dir",
        "children": []
    }

  # 1. HARVEST TRACKED DEV DIRECTORIES
    for folder in WHITELISTED_TRACKING_DIRS:
        abs_folder_path = os.path.join(root_workspace, folder)
        if os.path.exists(abs_folder_path):
            master_tree["children"].append(build_dynamic_node(folder, abs_folder_path, root_workspace))

    # 2. HARVEST ROOT ORPHANS (Intentionally capturing all utility plumbings like _full_audit.py)
    orphan_cluster = {
        "name": "Orphaned System Plumbings & Diagnostics",
        "type": "dir",
        "children": []
    }

    for filename in os.listdir(root_workspace):
        abs_file_path = os.path.join(root_workspace, filename)
        # Capture loose maintenance tools, refactoring blocks, and automation utilities on the root folder
        if os.path.isfile(abs_file_path) and filename.startswith("_") and filename.endswith((".py", ".ps1", ".sh", ".txt")):
            rel_path = filename
            b64_path = base64.b64encode(rel_path.encode('utf-8')).decode('utf-8')

            orphan_cluster["children"].append({
                "name": filename,
                "type": "file",
                "rel_path": rel_path,
                "b64_path": b64_path,
                "size": os.path.getsize(abs_file_path)
            })

    # Wrap the loose files neatly into the core sidebar layout
    if orphan_cluster["children"]:
        master_tree["children"].append(orphan_cluster)

    return jsonify(master_tree)
