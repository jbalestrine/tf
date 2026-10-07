"""
MasterChief Enterprise DevOps Platform
A comprehensive, modular enterprise DevOps automation platform.

v4.0.0 — October 2026
"""
import glob
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# ---------------------------------------------------------------------------
# data_files — ship the web GUI (main.py + HTML/CSS/JS) so that
# `masterchief serve` works right after `pip install masterchief`.
# Installed to  {sys.prefix}/share/masterchief/  (pip/wheel standard).
# ---------------------------------------------------------------------------
_webapp_files = (
    ["main.py"]
    + [f for f in glob.glob("*.html") if "backup" not in f.casefold()]
    + ["config.yml"]
    # ALL root-level Python modules (main.py imports sys_diagnostics at
    # runtime; others are feature scripts / demos users may invoke)
    + [f for f in glob.glob("*.py")
       if f not in (
           "setup.py", "conftest.py", "main.py", "main backup.py",
           "main_hub.py", "dynamic_worker.py", "bot_simulation.py",
           "index_workspace.py", "myscript.py", "test_model.py",
           "test_roku_builder.py",
       )
       and not f.startswith("_")]
)
_static_files = (
    glob.glob("static/*.css")
    + glob.glob("static/*.js")
    + glob.glob("static/*.svg")
    + glob.glob("static/*.png")
    + glob.glob("static/*.ico")
)

data_files = [
    ("share/masterchief", _webapp_files),
    ("share/masterchief/static", _static_files),
    ("share/masterchief/commands", glob.glob("commands/*.txt")),
]

# ---------------------------------------------------------------------------
# Package discovery — include every real project package, exclude runtime
# artefacts and third-party / non-Python directories.
# ---------------------------------------------------------------------------
packages = find_packages(
    include=[
        # Core platform + all packages
        "core*",
        "echo*",
        "platform*",
        "blueprints*",
        "features*",
        "utils*",
        # Modules & plugins
        "addons*",
        "chatops*",
        "config*",
        "managers*",
        "models*",
        "modules*",
        "observability*",
        "plugins*",
        "routes*",
        "scripts*",
        "security*",
        # Tools & wizards
        "tf_wizard*",
        "setup_wizard*",
        "tools*",
        "gui*",
        "renderers*",
        "resilience*",
        # Web UI templates & static
        "templates*",
        "static*",
        # Application packages
        "masterchief*",
        "webapp*",
        "pipelines*",
        "assets*",
        "examples*",
        "roku*",
    ],
    exclude=[
        # Never ship these
        "*.tests*",
        "tests*",
        "data*",
        "php*",
        "node_modules*",
        "irc_flask_superapp_final*",
        "generated_code*",
        "build_backup*",
        "dist_backup*",
        "remote_masterchief*",
    ],
)

setup(
    name="masterchief",
    version="4.0.0",
    author="MasterChief Team",
    description="Enterprise DevOps Automation Platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jbalestrine/masterchief",
    packages=packages,
    py_modules=[
        "masterchief_entry",
        "auth_config",
        "auth_module",
        "azure_integration",
        "github_integration",
        "app_management",
        "image_worker",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    python_requires=">=3.10",
    install_requires=[
        # -- Web Framework (hard required) --
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
        "Flask-Login>=0.6.0",
        "Flask-SocketIO>=5.0.0",
        "werkzeug>=3.0.0",
        "python-socketio>=5.0.0",
        "python-engineio>=4.0.0",
        # -- System & Utility --
        "psutil>=5.9.0",
        "requests>=2.31.0",
        "PyYAML>=6.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        # -- Security & Auth --
        "cryptography>=46.0.5",
        "cffi>=2.0.0",
        "PyJWT>=2.8.0",
        "authlib>=1.3.0",
        "jsonschema>=4.17.0",
        "pydantic>=2.5.0",
        "bcrypt>=4.0.0",
        "python-jose>=3.3.0",
        # -- Background Scheduling --
        "apscheduler>=3.10.0",
        "sqlalchemy>=2.0.0",
        # -- Source Control --
        "gitpython>=3.1.0",
        "git-filter-repo>=2.47.0",
        # -- IRC Bridge --
        "irc>=20.0.0",
        # -- Production WSGI --
        "gunicorn>=21.0.0",
        # -- HTTP Client --
        "httpx>=0.25.0",
        # -- Image Processing --
        "Pillow>=10.0.0",
        # -- Metrics & Observability --
        "prometheus-client>=0.19.0",
    ],
    extras_require={
        "cloud": [
            "azure-identity>=1.15.0",
            "azure-mgmt-resource>=23.0.0",
            "azure-mgmt-compute>=30.0.0",
            "azure-mgmt-storage>=21.0.0",
            "azure-core>=1.29.0",
            "azure-devops>=7.1.0b4",
            "boto3>=1.34.0",
            "kubernetes>=28.0.0",
            "docker>=7.0.0",
            "hvac>=2.0.0",
            "paramiko>=3.4.0",
            "python-gitlab>=4.0.0",
            "PyGithub>=2.1.0",
        ],
        "ansible": [
            "ansible>=9.0.0",
        ],
        "ai": [
            "torch>=2.0.0",
            "torchaudio>=2.0.0",
            "torchvision>=0.15.0",
            "transformers>=4.35.0",
            "diffusers>=0.21.0",
            "accelerate>=0.25.0",
            "peft>=0.6.0",
            "safetensors>=0.4.0",
            "sentence-transformers>=2.2.0",
            "faiss-cpu>=1.7.4",
            "huggingface-hub>=0.19.0",
            "tokenizers>=0.15.0",
            "llama-cpp-python>=0.2.0; python_version < '3.14'",
            "gguf>=0.1.0",
            "numpy>=1.24.0",
            "scipy>=1.10.0",
            "scikit-learn>=1.3.0",
        ],
        "audio": [
            "pyttsx3>=2.90",
            "openai-whisper>=20231117",
            "sounddevice>=0.4.6",
            "soundfile>=0.12.1",
            "librosa>=0.10.0",
            "pygame>=2.5.0",
            "webrtcvad>=2.0.10",
            "openwakeword>=0.5.0",
            "TTS>=0.22.0",
        ],
        "async": [
            "aiokafka>=0.10.0",
            "pika>=1.3.0",
            "aiohttp>=3.9.0",
            "eventlet>=0.33.0",
        ],
        "database": [
            "redis>=5.0.0",
            "psycopg2-binary>=2.9.0",
            "asyncpg>=0.29.0",
            "aiomysql>=0.2.0",
            "aiosqlite>=0.19.0",
            "motor>=3.3.0",
            "alembic>=1.13.0",
            "influxdb-client>=1.38.0",
        ],
        "extras": [
            "watchdog>=3.0.0",
            "ollama>=0.1.0",
            "croniter>=1.3.0",
            "ruff>=0.1.0",
            "statsd>=4.0.1",
            "celery>=5.3.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.0.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
            "isort>=5.12.0",
            "pylint>=3.0.0",
            "types-PyYAML>=6.0.0",
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=2.0.0",
            "ipython>=8.18.0",
            "pre-commit>=3.6.0",
            "build>=1.2.2",
            "twine>=6.0.0",
        ],
        "all": [
            "azure-identity>=1.15.0",
            "azure-mgmt-resource>=23.0.0",
            "azure-mgmt-compute>=30.0.0",
            "azure-mgmt-storage>=21.0.0",
            "azure-core>=1.29.0",
            "azure-devops>=7.1.0b4",
            "boto3>=1.34.0",
            "kubernetes>=28.0.0",
            "docker>=7.0.0",
            "hvac>=2.0.0",
            "paramiko>=3.4.0",
            "python-gitlab>=4.0.0",
            "PyGithub>=2.1.0",
            "ansible>=9.0.0",
            "torch>=2.0.0",
            "torchaudio>=2.0.0",
            "torchvision>=0.15.0",
            "transformers>=4.35.0",
            "diffusers>=0.21.0",
            "accelerate>=0.25.0",
            "peft>=0.6.0",
            "safetensors>=0.4.0",
            "sentence-transformers>=2.2.0",
            "faiss-cpu>=1.7.4",
            "huggingface-hub>=0.19.0",
            "tokenizers>=0.15.0",
            "llama-cpp-python>=0.2.0; python_version < '3.14'",
            "gguf>=0.1.0",
            "numpy>=1.24.0",
            "scipy>=1.10.0",
            "scikit-learn>=1.3.0",
            "pyttsx3>=2.90",
            "openai-whisper>=20231117",
            "sounddevice>=0.4.6",
            "soundfile>=0.12.1",
            "librosa>=0.10.0",
            "pygame>=2.5.0",
            "webrtcvad>=2.0.10",
            "openwakeword>=0.5.0",
            "TTS>=0.22.0",
            "aiokafka>=0.10.0",
            "pika>=1.3.0",
            "aiohttp>=3.9.0",
            "eventlet>=0.33.0",
            "redis>=5.0.0",
            "psycopg2-binary>=2.9.0",
            "asyncpg>=0.29.0",
            "aiomysql>=0.2.0",
            "aiosqlite>=0.19.0",
            "motor>=3.3.0",
            "alembic>=1.13.0",
            "influxdb-client>=1.38.0",
            "watchdog>=3.0.0",
            "ollama>=0.1.0",
            "croniter>=1.3.0",
            "ruff>=0.1.0",
            "statsd>=4.0.1",
            "celery>=5.3.0",
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.0.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
            "isort>=5.12.0",
            "pylint>=3.0.0",
            "types-PyYAML>=6.0.0",
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=2.0.0",
            "ipython>=8.18.0",
            "pre-commit>=3.6.0",
            "build>=1.2.2",
            "twine>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "masterchief=masterchief_entry:main",
            "tf-wizard=tf_wizard.app:main",
        ],
    },
    include_package_data=True,
    package_data={
        # Catch-all: ship every non-.py data file found inside any package
        "": [
            "*.html", "*.css", "*.js", "*.json", "*.yaml", "*.yml",
            "*.tf", "*.j2", "*.sh", "*.ps1", "*.brs", "*.xml",
            "*.md", "*.txt", "*.cfg", "*.conf", "*.template", "*.list",
            "*.png", "*.jpg", "*.svg", "*.ico",
        ],
    },
    data_files=data_files,
)
