"""Load the flattened legacy voice modules as one package for unit tests."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType


_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "chatops"
_PACKAGE = "_masterchief_voice_automation_tests"
_MODULE_FILES = {
    "intent_parser": "irc_bot-engine_voice_automation_intent_parser.py",
    "wake_word": "irc_bot-engine_voice_automation_wake_word.py",
    "conversation": "irc_bot-engine_voice_automation_conversation.py",
    "command_processor": "irc_bot-engine_voice_automation_command_processor.py",
    "action_executor": "irc_bot-engine_voice_automation_action_executor.py",
    "response_builder": "irc_bot-engine_voice_automation_response_builder.py",
    "feedback": "irc_bot-engine_voice_automation_feedback.py",
}
_LOAD_ORDER = tuple(_MODULE_FILES)


def load_voice_automation_modules():
    package = sys.modules.get(_PACKAGE)
    if package is None:
        package = ModuleType(_PACKAGE)
        package.__path__ = []
        sys.modules[_PACKAGE] = package

    modules = {}
    for name in _LOAD_ORDER:
        qualified_name = f"{_PACKAGE}.{name}"
        module = sys.modules.get(qualified_name)
        if module is None:
            source_path = _SOURCE_ROOT / _MODULE_FILES[name]
            if not source_path.is_file():
                raise FileNotFoundError(f"Voice automation module is missing: {source_path}")
            spec = spec_from_file_location(qualified_name, source_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Unable to load voice automation module: {source_path}")
            module = module_from_spec(spec)
            sys.modules[qualified_name] = module
            spec.loader.exec_module(module)
        setattr(package, name, module)
        modules[name] = module
    return modules
