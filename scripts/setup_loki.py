"""Install, start and wire up a standalone loki for MasterChief (optional, no Docker).

Run from the Core Scripts page / Observability page, or:
    python scripts/setup_loki.py [setup|install|start|stop|status|uninstall]
"""

from observability_stack import main

if __name__ == "__main__":
    main("loki")
