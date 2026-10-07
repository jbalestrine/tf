"""
Unit tests for Echo Chat Bot.
"""

import os
import sys
import tempfile
import unittest
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from echo.chat_bot import (
    EchoChatBot,
    TrainingDataStore,
    ResponseQuality,
    ChatMessage,
    TrainingExample
)


class TestTrainingDataStore(unittest.TestCase):
    """Test training data storage."""
    
    def test_init(self):
        """Test initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            self.assertTrue(os.path.exists(tmpdir))
            self.assertEqual(store.patterns, {})
    
    def test_add_example(self):
        """Test adding training example."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            
            example = TrainingExample(
                user_message="test message",
                bot_response="test response",
                quality=ResponseQuality.EXCELLENT
            )
            
            success = store.add_example(example)
            self.assertTrue(success)
            
            # Verify file was created
            examples_file = os.path.join(tmpdir, "training_examples.jsonl")
            self.assertTrue(os.path.exists(examples_file))
    
    def test_get_examples(self):
        """Test retrieving examples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            
            # Add some examples
            for i in range(3):
                example = TrainingExample(
                    user_message=f"message {i}",
                    bot_response=f"response {i}",
                    quality=ResponseQuality.GOOD
                )
                store.add_example(example)
            
            # Retrieve examples
            examples = store.get_examples(limit=10)
            self.assertEqual(len(examples), 3)
            self.assertTrue(all(isinstance(e, TrainingExample) for e in examples))
    
    def test_save_load_patterns(self):
        """Test saving and loading patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            
            patterns = {
                "hello": "Hi there!",
                "bye": "Goodbye!"
            }
            
            success = store.save_patterns(patterns)
            self.assertTrue(success)
            
            # Load patterns
            loaded_patterns = store._load_patterns()
            self.assertEqual(loaded_patterns, patterns)
    
    def test_get_stats(self):
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            
            # Add examples with different qualities
            qualities = [
                ResponseQuality.EXCELLENT,
                ResponseQuality.GOOD,
                ResponseQuality.ACCEPTABLE
            ]
            
            for quality in qualities:
                example = TrainingExample(
                    user_message="test",
                    bot_response="response",
                    quality=quality
                )
                store.add_example(example)
            
            stats = store.get_stats()
            self.assertEqual(stats['total_examples'], 3)
            self.assertEqual(stats['quality_distribution']['excellent'], 1)
            self.assertEqual(stats['quality_distribution']['good'], 1)
            self.assertEqual(stats['quality_distribution']['acceptable'], 1)


class TestEchoChatBot(unittest.TestCase):
    """Test Echo chat bot."""
    
    def test_init(self):
        """Test initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            self.assertIsNotNone(bot.training_store)
            self.assertIsInstance(bot.conversation_history, dict)
    
    def test_basic_chat(self):
        """Test basic chat functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            response = bot.chat("Hello", session_id="test")
            
            self.assertIn('response', response)
            self.assertIn('session_id', response)
            self.assertIn('timestamp', response)
            self.assertIn('message_id', response)
            self.assertEqual(response['session_id'], "test")

    def test_workspace_help_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)

            response = bot.chat("!help", session_id="code_help")

            self.assertIn("!library find", response['response'])
            self.assertIn("!write", response['response'])
            self.assertIn("does not execute", response['response'])

    def test_write_command_uses_local_project_examples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            examples = root / 'data' / 'scripts'
            examples.mkdir(parents=True)
            (examples / 'example.py').write_text('print("reference marker")', encoding='utf-8')
            store = TrainingDataStore(storage_path=str(root / 'training'))
            bot = EchoChatBot(training_store=store)
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            from unittest.mock import patch

            with patch.object(bot, '_generate_with_local_llm', return_value='generated script') as local_model, \
                    patch.object(bot, '_generate_with_ollama', return_value=None) as ollama:
                response = bot.chat('!write python print a greeting', session_id='code_write')

            self.assertEqual(response['response'], 'generated script')
            self.assertIn('reference marker', local_model.call_args.args[0])
            ollama.assert_not_called()

    def test_library_command_finds_user_script_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts = root / 'data' / 'scripts'
            scripts.mkdir(parents=True)
            (scripts / 'orphan_backup.py').write_text('print("backup")', encoding='utf-8')
            store = TrainingDataStore(storage_path=str(root / 'training'))
            bot = EchoChatBot(training_store=store)
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            response = bot.chat('!library find orphan backup', session_id='code_library')

            self.assertIn('data/scripts/orphan_backup.py', response['response'])

    def test_write_command_does_not_send_examples_to_remote_ollama(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)

            from unittest.mock import patch

            with patch.dict(os.environ, {'ECHO_OLLAMA_URL': 'https://example.invalid/api/generate'}), \
                    patch.object(bot, '_generate_with_local_llm', return_value=None), \
                    patch.object(bot, '_generate_with_ollama') as ollama:
                response = bot.chat('!write python create a utility', session_id='code_private')

            self.assertIn('not sent to remote models', response['response'])
            ollama.assert_not_called()
    
    def test_greeting_detection(self):
        """Test greeting detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            response = bot.chat("hello", session_id="test")
            # Just verify we get a response (not checking exact content)
            self.assertIsNotNone(response['response'])
            self.assertTrue(len(response['response']) > 0)
    
    def test_devops_detection(self):
        """Test DevOps query detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            response = bot.chat("Tell me about Docker", session_id="test")
            self.assertIn('docker', response['response'].lower())
    
    def test_train_bot(self):
        """Test training the bot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            success = bot.train(
                user_message="test question",
                bot_response="test answer",
                quality=ResponseQuality.EXCELLENT,
                feedback="good"
            )
            
            self.assertTrue(success)
            
            # Check stats
            stats = bot.get_training_stats()
            self.assertEqual(stats['total_examples'], 1)
            self.assertEqual(stats['patterns_learned'], 1)
    
    def test_learned_pattern(self):
        """Test that bot uses learned patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            # Train the bot
            question = "how to build docker image"
            answer = "Use docker build command"
            
            bot.train(
                user_message=question,
                bot_response=answer,
                quality=ResponseQuality.EXCELLENT
            )
            
            # Ask the same question
            response = bot.chat(question, session_id="test")
            self.assertEqual(response['response'], answer)
    
    def test_conversation_history(self):
        """Test conversation history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            session_id = "history_test"
            
            # Have a conversation
            bot.chat("Hello", session_id=session_id)
            bot.chat("How are you?", session_id=session_id)
            bot.chat("Goodbye", session_id=session_id)
            
            # Get history
            history = bot.get_conversation_history(session_id)
            
            # Should have 6 messages (3 user + 3 bot)
            self.assertEqual(len(history), 6)
            
            # Check alternating roles
            self.assertEqual(history[0]['role'], 'user')
            self.assertEqual(history[1]['role'], 'assistant')
            self.assertEqual(history[2]['role'], 'user')
            self.assertEqual(history[3]['role'], 'assistant')
    
    def test_clear_conversation(self):
        """Test clearing conversation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            session_id = "clear_test"
            
            # Have a conversation
            bot.chat("Hello", session_id=session_id)
            bot.chat("Test", session_id=session_id)
            
            # Clear it
            bot.clear_conversation(session_id)
            
            # History should be empty
            history = bot.get_conversation_history(session_id)
            self.assertEqual(len(history), 0)
    
    def test_session_isolation(self):
        """Test that sessions are isolated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TrainingDataStore(storage_path=tmpdir)
            bot = EchoChatBot(training_store=store)
            
            # Different sessions
            bot.chat("Message 1", session_id="session1")
            bot.chat("Message 2", session_id="session2")
            
            history1 = bot.get_conversation_history("session1")
            history2 = bot.get_conversation_history("session2")
            
            # Each session should only have its own messages
            self.assertEqual(len(history1), 2)  # 1 user + 1 bot
            self.assertEqual(len(history2), 2)  # 1 user + 1 bot
            self.assertEqual(history1[0]['content'], "Message 1")
            self.assertEqual(history2[0]['content'], "Message 2")


class TestChatMessage(unittest.TestCase):
    """Test ChatMessage data class."""
    
    def test_create_message(self):
        """Test creating a message."""
        msg = ChatMessage(
            role="user",
            content="test message",
            timestamp=1234567890.0,
            session_id="test",
            message_id="msg_123"
        )
        
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "test message")
        self.assertEqual(msg.timestamp, 1234567890.0)
        self.assertEqual(msg.session_id, "test")
        self.assertEqual(msg.message_id, "msg_123")


class TestTrainingExample(unittest.TestCase):
    """Test TrainingExample data class."""
    
    def test_create_example(self):
        """Test creating a training example."""
        example = TrainingExample(
            user_message="test question",
            bot_response="test answer",
            quality=ResponseQuality.GOOD,
            feedback="helpful"
        )
        
        self.assertEqual(example.user_message, "test question")
        self.assertEqual(example.bot_response, "test answer")
        self.assertEqual(example.quality, ResponseQuality.GOOD)
        self.assertEqual(example.feedback, "helpful")
        self.assertIsNotNone(example.timestamp)
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        example = TrainingExample(
            user_message="question",
            bot_response="answer",
            quality=ResponseQuality.EXCELLENT
        )
        
        data = example.to_dict()
        
        self.assertEqual(data['user_message'], "question")
        self.assertEqual(data['bot_response'], "answer")
        self.assertEqual(data['quality'], "excellent")
        self.assertIn('timestamp', data)


class TestResponseQuality(unittest.TestCase):
    """Test ResponseQuality enum."""
    
    def test_quality_values(self):
        """Test quality enum values."""
        self.assertEqual(ResponseQuality.EXCELLENT.value, "excellent")
        self.assertEqual(ResponseQuality.GOOD.value, "good")
        self.assertEqual(ResponseQuality.ACCEPTABLE.value, "acceptable")
        self.assertEqual(ResponseQuality.POOR.value, "poor")


if __name__ == '__main__':
    unittest.main(verbosity=2)
