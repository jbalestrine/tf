"""Test response builder."""

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
_REQUIRED_MODULES = ("response_builder.py", "intent_parser.py", "action_executor.py")
if not all((_VOICE_AUTOMATION / module).is_file() for module in _REQUIRED_MODULES):
    pytest.skip(
        "Legacy voice automation source is not included in this checkout.",
        allow_module_level=True,
    )

from chatops.irc.bot_engine.voice.automation.response_builder import ResponseBuilder
from chatops.irc.bot_engine.voice.automation.intent_parser import Intent
from chatops.irc.bot_engine.voice.automation.action_executor import ActionResult


class TestResponseBuilder:
    """Tests for ResponseBuilder."""
    
    def test_initialization(self):
        """Test response builder initialization."""
        builder = ResponseBuilder()
        
        assert builder is not None
        assert len(builder.templates) > 0
    
    def test_build_success_response(self):
        """Test building success response."""
        builder = ResponseBuilder()
        
        intent = Intent(
            name="create_script",
            entities={"description": "test"},
            confidence=0.9,
            original_text="create a test script"
        )
        
        result = ActionResult(
            success=True,
            message="Script created",
            data={"name": "test.sh", "details": "Created successfully"}
        )
        
        response = builder.build(intent, result)
        
        assert "test.sh" in response
        assert len(response) > 0
    
    def test_build_error_response(self):
        """Test building error response."""
        builder = ResponseBuilder()
        
        intent = Intent(
            name="run_script",
            entities={"name": "test.sh"},
            confidence=0.9,
            original_text="run test script"
        )
        
        result = ActionResult(
            success=False,
            message="Script failed",
            data={"name": "test.sh", "error": "File not found"}
        )
        
        response = builder.build(intent, result)
        
        assert "failed" in response.lower() or "error" in response.lower()
    
    def test_build_cancelled_response(self):
        """Test building cancelled response."""
        builder = ResponseBuilder()
        
        intent = Intent(
            name="delete_script",
            entities={"name": "test.sh"},
            confidence=0.9,
            original_text="delete test script",
            requires_confirmation=True
        )
        
        result = ActionResult(
            success=True,
            message="Cancelled",
            data={},
            cancelled=True
        )
        
        response = builder.build(intent, result)
        
        assert "cancel" in response.lower()
    
    def test_build_error_response_direct(self):
        """Test building error response directly."""
        builder = ResponseBuilder()
        
        response = builder.build_error_response("Something went wrong")
        
        assert "error" in response.lower()
        assert "Something went wrong" in response
    
    def test_build_confirmation_prompt(self):
        """Test building confirmation prompt."""
        builder = ResponseBuilder()
        
        intent = Intent(
            name="deploy",
            entities={"environment": "production"},
            confidence=0.9,
            original_text="deploy to production",
            requires_confirmation=True
        )
        
        prompt = builder.build_confirmation_prompt(intent)
        
        assert "deploy" in prompt.lower()
        assert "production" in prompt.lower()
        assert "?" in prompt or "yes" in prompt.lower() or "no" in prompt.lower()
    
    def test_handle_missing_data(self):
        """Test handling missing template data."""
        builder = ResponseBuilder()
        
        intent = Intent(
            name="create_script",
            entities={},
            confidence=0.9,
            original_text="create a script"
        )
        
        result = ActionResult(
            success=True,
            message="Created",
            data={}  # Missing expected fields
        )
        
        # Should not crash
        response = builder.build(intent, result)
        assert len(response) > 0
