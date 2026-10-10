# Module Manager Addon Wizard

installs libraries

Everything for this feature lives in this folder. Nothing here needs to be added to `main.py`.

| To change | Edit |
|-----------|------|
| What the page looks like | `templates/index.html` |
| Routes, API and logic | `__init__.py` |
| Name, menu entry, default on/off | `feature.json` |
| Turn it on or off | Code Manager -> Features (stored in `data/feature_flags.json`) |

URL: `/ext/python_addon_manager/`. Restart the app after changing Python files or the on/off switch.
Remove it by deleting this folder; nothing else references it.
