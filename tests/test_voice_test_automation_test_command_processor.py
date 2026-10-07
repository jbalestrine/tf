"""Test command processor."""

from pathlib import Path

import pytest

_VOICE_AUTOMATION = (
    Path(__file__).resolve().parents[1]
    / "chatops"
    / "irc"
    / "bot_engine"
    / "voice"
    / "automation"
)
if not (_VOICE_AUTOMATION / "command_processor.py").is_file():
    pytest.skip(
        "Legacy voice automation source is not included in this checkout.",
        allow_module_level=True,
    )

from chatops.irc.bot_engine.voice.automation.command_processor import CommandProcessor


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
