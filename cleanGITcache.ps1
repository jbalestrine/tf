# =========================================================================
# DEVOPS BLUEPRINT: LOCAL WORKSPACE TRACKING RESCUE
# Use case: When environment updates (venv/build/models) flood the IDE
#           with thousands of phantom, untracked changes.
# =========================================================================

# 1. ALWAYS CREATE A PHYSICAL ZIP ARCHIVE OF THE SOURCE FOLDER FIRST!
#    Ex: Compress-Archive -Path ".\masterchief" -DestinationPath "~\Desktop\Backup.zip"

# 2. Update .gitignore at the project root to include the culprits:
#    venv/
#    build/
#    models/

# 3. Flush Git's virtual tracking index memory cleanly (WITHOUT deleting local files)
git rm -r --cached .

# 4. Re-index the directory using the newly applied .gitignore filters
git add .

# 5. Refresh and verify the clean visual state of the sidebar
git status
