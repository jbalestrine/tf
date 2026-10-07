"""Test wake word detection."""

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
if not (_VOICE_AUTOMATION / "wake_word.py").is_file():
    pytest.skip(
        "Legacy voice automation source is not included in this checkout.",
        allow_module_level=True,
    )

# Direct imports from file path since bot-engine has dashes
import importlib.util
import sys

def load_module_from_path(module_name, file_path):
    """Load a module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Load wake_word module
wake_word_module = load_module_from_path(
    "wake_word", str(_VOICE_AUTOMATION / "wake_word.py")
)
WakeWordDetector = wake_word_module.WakeWordDetector


class TestWakeWordDetector:
    """Tests for WakeWordDetector."""
    
    def test_initialization(self):
        """Test wake word detector initialization."""
        detector = WakeWordDetector(
            wake_words=["hey chief", "okay chief"],
            engine="simple",
            sensitivity=0.5
        )
        
        assert detector is not None
        assert len(detector.wake_words) == 2
        assert "hey chief" in detector.wake_words
        assert detector.sensitivity == 0.5
    
    def test_detect_in_text(self):
        """Test detecting wake word in text."""
        detector = WakeWordDetector(
            wake_words=["hey chief"],
            engine="simple"
        )
        
        # Should detect
        assert detector.detect_in_text("Hey chief, what's up?")
        assert detector.detect_in_text("hey CHIEF please help")
        
        # Should not detect
        assert not detector.detect_in_text("Hello there")
        assert not detector.detect_in_text("chief alone")
    
    def test_add_wake_word(self):
        """Test adding a wake word."""
        detector = WakeWordDetector(
            wake_words=["hey chief"],
            engine="simple"
        )
        
        detector.add_wake_word("okay chief")
        
        assert "okay chief" in detector.wake_words
        assert len(detector.wake_words) == 2
    
    def test_remove_wake_word(self):
        """Test removing a wake word."""
        detector = WakeWordDetector(
            wake_words=["hey chief", "okay chief"],
            engine="simple"
        )
        
        detector.remove_wake_word("okay chief")
        
        assert "okay chief" not in detector.wake_words
        assert len(detector.wake_words) == 1
    
    def test_case_insensitive(self):
        """Test case insensitive wake word detection."""
        detector = WakeWordDetector(
            wake_words=["Hey MasterChief"],
            engine="simple"
        )
        
        assert detector.detect_in_text("hey masterchief")
        assert detector.detect_in_text("HEY MASTERCHIEF")
        assert detector.detect_in_text("Hey Masterchief")


if __name__ == '__main__':
    # Run tests
    test = TestWakeWordDetector()
    test.test_initialization()
    print("✓ test_initialization passed")
    test.test_detect_in_text()
    print("✓ test_detect_in_text passed")
    test.test_add_wake_word()
    print("✓ test_add_wake_word passed")
    test.test_remove_wake_word()
    print("✓ test_remove_wake_word passed")
    test.test_case_insensitive()
    print("✓ test_case_insensitive passed")
    print("\n✅ All tests passed!")
