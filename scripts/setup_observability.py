"""Install, start and wire up Prometheus, Loki and Grafana in one go (optional, no Docker).

    python scripts/setup_observability.py [setup|install|start|stop|status|uninstall]
"""

from observability_stack import main

if __name__ == "__main__":
    main("all")
