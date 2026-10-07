"""Test intent parser."""

from pathlib import Path

import pytest

_VOICE_AUTOMATION = (
    Path(__file__).resolve().parents[1]
    / "chatops"
    / "irc"
    / "bot-engine"
    / "voice"
    / "automation"
)
if not (_VOICE_AUTOMATION / "intent_parser.py").is_file():
    pytest.skip(
        "Legacy voice automation source is not included in this checkout.",
        allow_module_level=True,
    )

import importlib.util
import sys

def load_module_from_path(module_name, file_path):
    """Load a module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Load intent_parser module
intent_parser_module = load_module_from_path(
    "intent_parser", str(_VOICE_AUTOMATION / "intent_parser.py")
)
IntentParser = intent_parser_module.IntentParser
Intent = intent_parser_module.Intent


class TestIntentParser:
    """Tests for IntentParser."""
    
    def test_parse_create_script(self):
        """Test parsing create script intent."""
        parser = IntentParser()
        
        intent = parser.parse("create a script to backup the database")
        
        assert intent.name == "create_script"
        assert "description" in intent.entities
        assert "backup the database" in intent.entities["description"]
        assert intent.confidence > 0.5
    
    def test_parse_run_script(self):
        """Test parsing run script intent."""
        parser = IntentParser()
        
        intent = parser.parse("run script backup_db")
        
        assert intent.name == "run_script"
        assert intent.entities.get("name") == "backup_db"
    
    def test_parse_list_scripts(self):
        """Test parsing list scripts intent."""
        parser = IntentParser()
        
        intent = parser.parse("list all scripts")
        
        assert intent.name == "list_scripts"
    
    def test_parse_system_status(self):
        """Test parsing system status intent."""
        parser = IntentParser()
        
        intent = parser.parse("what's the system status?")
        
        assert intent.name == "system_status"
    
    def test_parse_deploy(self):
        """Test parsing deploy intent."""
        parser = IntentParser()
        
        intent = parser.parse("deploy to production")
        
        assert intent.name == "deploy"
        assert intent.entities.get("environment") == "production"
        assert intent.requires_confirmation
    
    def test_parse_stop_listening(self):
        """Test parsing stop listening intent."""
        parser = IntentParser()
        
        intent = parser.parse("that's all")
        
        assert intent.name == "stop_listening"
    
    def test_parse_help(self):
        """Test parsing help intent."""
        parser = IntentParser()
        
        intent = parser.parse("what can you do?")
        
        assert intent.name == "help"
    
    def test_parse_unknown(self):
        """Test parsing unknown intent."""
        parser = IntentParser()
        
        intent = parser.parse("foobar baz qux")
        
        assert intent.name == "unknown"
        assert intent.confidence == 0.0
    
    def test_intent_description(self):
        """Test intent description property."""
        intent = Intent(
            name="create_script",
            entities={"description": "test script"},
            confidence=0.9,
            original_text="create a script to test",
            requires_confirmation=False
        )
        
        assert "test script" in intent.description


if __name__ == '__main__':
    # Run tests
    test = TestIntentParser()
    test.test_parse_create_script()
    print("✓ test_parse_create_script passed")
    test.test_parse_run_script()
    print("✓ test_parse_run_script passed")
    test.test_parse_list_scripts()
    print("✓ test_parse_list_scripts passed")
    test.test_parse_system_status()
    print("✓ test_parse_system_status passed")
    test.test_parse_deploy()
    print("✓ test_parse_deploy passed")
    test.test_parse_stop_listening()
    print("✓ test_parse_stop_listening passed")
    test.test_parse_help()
    print("✓ test_parse_help passed")
    test.test_parse_unknown()
    print("✓ test_parse_unknown passed")
    test.test_intent_description()
    print("✓ test_intent_description passed")
    print("\n✅ All tests passed!")
