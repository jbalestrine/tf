import os
import json

# Define our directory boundaries
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(ROOT_DIR, "data", "echo_memories.jsonl")

# Extensions we want Mistral to analyze and learn from
TARGET_EXTENSIONS = {'.py', '.ps1'}

# Folders we must completely skip to avoid garbage collection bloat
IGNORE_FOLDERS = {'venv', '.venv', '__pycache__', '.git', 'site-packages', 'data'}

def build_code_dataset():
    print(f"🔍 Crawling MasterChief platform structure at: {ROOT_DIR}")
    memory_entries = []
    
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        # Filter folders inline to prevent traversal drift
        dirnames[:] = [d for d in dirnames if d not in IGNORE_FOLDERS]
        
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in TARGET_EXTENSIONS:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        code_content = f.read().strip()
                    
                    if not code_content:
                        continue
                        
                    # Structure the code files as training memory inputs
                    memory_object = {
                        "prompt": f"Analyze the platform workspace file structure for code pattern learning. File name reference target: {rel_path}",
                        "completion": f"File layout source code content:\n```python\n{code_content}\n```"
                    }
                    memory_entries.append(memory_object)
                    print(f"   ✅ Parsed source parameters from: {rel_path}")
                    
                except Exception as e:
                    print(f"   ❌ Skipped file parse error on {rel_path}: {e}")

    # Write out to your platform's active echo_memories data layer file
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in memory_entries:
            f.write(json.dumps(entry) + "\n")
            
    print(f"\n💾 Dataset mapping success! Generated {len(memory_entries)} source code records.")
    print(f"   Target Memory Location -> {OUTPUT_FILE}")

if __name__ == '__main__':
    build_code_dataset()
