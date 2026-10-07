"""Tests for the command processor."""

import pytest

from tests.voice_automation_loader import load_voice_automation_modules

CommandProcessor = load_voice_automation_modules()["command_processor"].CommandProcessor


@pytest.fixture(autouse=True)
def disable_optional_ollama_network_probe(monkeypatch):
    monkeypatch.setattr(CommandProcessor, "_check_ollama", lambda self: None)


class TestCommandProcessor:
    """Tests for CommandProcessor."""
    
    def test_initialization(self):
        """Test command processor initialization."""
        processor = CommandProcessor(model="mistral")
        
        assert processor is not None
        assert processor.model == "mistral"
        assert processor.intent_parser is not None
    
    def test_parse_without_llm(self):
        """Test parsing without LLM (pattern matching fallback)."""
        processor = CommandProcessor()
        processor.use_llm = False
        
        intent = processor.parse("create a script to test something")
        
        assert intent is not None
        assert intent.name in processor.INTENTS
    
    def test_parse_create_script(self):
        """Test parsing create script command."""
        processor = CommandProcessor()
        processor.use_llm = False
        
        intent = processor.parse("create a script to backup database")
        
        assert intent.name == "create_script"
        assert "description" in intent.entities
    
    def test_parse_run_script(self):
        """Test parsing run script command."""
        processor = CommandProcessor()
        processor.use_llm = False
        
        intent = processor.parse("run backup_script")
        
        assert intent.name == "run_script"
        assert intent.entities.get("name") == "backup_script"
    
    def test_parse_system_status(self):
        """Test parsing system status command."""
        processor = CommandProcessor()
        processor.use_llm = False
        
        intent = processor.parse("what's the system status")
        
        assert intent.name == "system_status"
    
    def test_parse_with_context(self):
        """Test parsing with conversation context."""
        processor = CommandProcessor()
        processor.use_llm = False
        
        # Context shouldn't break parsing
        intent = processor.parse("list scripts", context=None)
        
        assert intent.name == "list_scripts"
