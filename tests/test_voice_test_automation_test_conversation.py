"""Test conversation manager."""

import time
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
if not (_VOICE_AUTOMATION / "conversation.py").is_file():
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

# Load conversation module
conversation_module = load_module_from_path(
    "conversation", str(_VOICE_AUTOMATION / "conversation.py")
)
ConversationManager = conversation_module.ConversationManager
ConversationTurn = conversation_module.ConversationTurn


class TestConversationManager:
    """Tests for ConversationManager."""
    
    def test_initialization(self):
        """Test conversation manager initialization."""
        manager = ConversationManager(context_window=5, timeout=20)
        
        assert manager.context_window == 5
        assert manager.timeout == 20
        assert len(manager.turns) == 0
        assert manager.last_activity is None
    
    def test_add_turn(self):
        """Test adding a conversation turn."""
        manager = ConversationManager()
        
        manager.add_turn("hello", "hi there")
        
        assert len(manager.turns) == 1
        assert manager.turns[0].user == "hello"
        assert manager.turns[0].bot == "hi there"
        assert manager.last_activity is not None
    
    def test_context_window_trimming(self):
        """Test that old turns are trimmed."""
        manager = ConversationManager(context_window=3)
        
        for i in range(5):
            manager.add_turn(f"user {i}", f"bot {i}")
        
        assert len(manager.turns) == 3
        assert manager.turns[0].user == "user 2"
        assert manager.turns[-1].user == "user 4"
    
    def test_context_summary(self):
        """Test context summary generation."""
        manager = ConversationManager()
        
        manager.add_turn("create a script", "script created")
        manager.add_turn("run it", "script running")
        
        context = manager.context
        summary = context.summary
        
        assert "create a script" in summary or "User:" in summary
        assert len(summary) > 0
    
    def test_is_expired(self):
        """Test conversation expiration."""
        manager = ConversationManager(timeout=1)
        
        assert manager.is_expired()  # No activity yet
        
        manager.add_turn("hello", "hi")
        assert not manager.is_expired()
        
        time.sleep(1.5)
        assert manager.is_expired()
    
    def test_clear(self):
        """Test clearing conversation."""
        manager = ConversationManager()
        
        manager.add_turn("hello", "hi")
        manager.clear()
        
        assert len(manager.turns) == 0
        assert manager.last_activity is None
    
    def test_should_end_conversation(self):
        """Test detecting end conversation phrases."""
        manager = ConversationManager()
        
        assert manager.should_end_conversation("that's all")
        assert manager.should_end_conversation("thanks, that is all")
        assert manager.should_end_conversation("goodbye")
        assert manager.should_end_conversation("stop listening")
        
        assert not manager.should_end_conversation("continue")
        assert not manager.should_end_conversation("what's the status")
    
    def test_get_history(self):
        """Test getting conversation history."""
        manager = ConversationManager()
        
        for i in range(5):
            manager.add_turn(f"user {i}", f"bot {i}")
        
        history = manager.get_history(n=3)
        
        assert len(history) == 3
        assert history[0].user == "user 2"
        assert history[-1].user == "user 4"
    
    def test_time_remaining(self):
        """Test time remaining calculation."""
        manager = ConversationManager(timeout=10)
        
        assert manager.time_remaining() == 0.0  # Not started
        
        manager.add_turn("hello", "hi")
        remaining = manager.time_remaining()
        
        assert 9 <= remaining <= 10


if __name__ == '__main__':
    # Run tests
    test = TestConversationManager()
    test.test_initialization()
    print("✓ test_initialization passed")
    test.test_add_turn()
    print("✓ test_add_turn passed")
    test.test_context_window_trimming()
    print("✓ test_context_window_trimming passed")
    test.test_context_summary()
    print("✓ test_context_summary passed")
    test.test_is_expired()
    print("✓ test_is_expired passed")
    test.test_clear()
    print("✓ test_clear passed")
    test.test_should_end_conversation()
    print("✓ test_should_end_conversation passed")
    test.test_get_history()
    print("✓ test_get_history passed")
    test.test_time_remaining()
    print("✓ test_time_remaining passed")
    print("\n✅ All tests passed!")
