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
from managers.echo_change_approvals import EchoChangeApprovalManager


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
            self.assertIn("!makeascript", response['response'])
            self.assertIn("!write", response['response'])
            self.assertIn("OS/runtime", response['response'])
            self.assertIn("powershell create a read-only report", response['response'])
            self.assertIn("does not train model weights", response['response'])

    def test_plain_help_does_not_override_a_specific_help_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bot = EchoChatBot(training_store=TrainingDataStore(storage_path=tmpdir))

            plain_help = bot.chat("help", session_id="plain_help")
            self.assertIn("infrastructure, automation, scripts", plain_help["response"])
            self.assertIn("does not train model weights", plain_help["response"])
            self.assertNotIn("help", plain_help["response"].casefold())

            from unittest.mock import patch

            with patch.object(bot, "_handle_devops_query", return_value="pipeline-specific answer") as handler:
                specific_help = bot.chat(
                    "help me troubleshoot a CI pipeline",
                    session_id="specific_help",
                )

            self.assertEqual(specific_help["response"], "pipeline-specific answer")
            handler.assert_called_once()

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

    def test_makeascript_indexes_requested_languages_and_uses_content_references(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library = root / 'legacy'
            library.mkdir()
            sources = {
                'example.php': '<?php function validateHubSpokeTopology() { return true; }',
                'module.psm1': 'function Get-HubSpokeTopology { return $true }',
                'page.html': '<!doctype html><html><body>topology dashboard</body></html>',
                'client.js': 'function renderTopologyDashboard() { return true; }',
                'layout.xml': '<?xml version="1.0"?><Topology><Hub /></Topology>',
                'settings.json': '{"topology": "hub-spoke"}',
                'network.tf': 'resource "example_network" "hub" {}',
                'channel.brs': 'sub Main()\n  print "channel"\nend sub',
                'check.bat': '@echo off\nsetlocal\n',
                'check.cmd': '@echo off\nsetlocal\n',
                'check.fish': 'function check_topology\nend\n',
                'settings.yaml': 'topology:\n  name: hub-spoke\n',
                'settings.yml': 'topology:\n  name: hub-spoke\n',
                'page.j2': '<h1>{{ title }}</h1>',
                'check.py': 'def validate_topology():\n    return True',
                'check.sh': '#!/bin/bash\necho topology',
            }
            for name, content in sources.items():
                (library / name).write_text(content, encoding='utf-8')

            store = TrainingDataStore(storage_path=str(root / 'training'))
            bot = EchoChatBot(training_store=store)
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            for extension in (
                '.php', '.psm1', '.html', '.js', '.xml', '.json', '.tf', '.py',
                '.sh', '.brs', '.bat', '.cmd', '.fish', '.yaml', '.yml', '.j2',
            ):
                self.assertEqual(bot._reference_index[extension]['count'], 1)

            from unittest.mock import patch

            with patch.object(bot, '_generate_with_local_llm', return_value='generated PHP') as local_model:
                response = bot.chat(
                    '!makeascript php validate the hub spoke topology',
                    session_id='make_php',
                )

            self.assertEqual(response['response'], 'generated PHP')
            prompt = local_model.call_args.args[0]
            self.assertIn('validateHubSpokeTopology', prompt)
            self.assertIn('Example: legacy/example.php', prompt)
            self.assertIn('how to run it', prompt)

    def test_reference_index_covers_nested_repo_scripts_and_refreshes_new_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files = {
                'scripts/team/nested/inventory.py': 'def inventory(): return "nested"',
                'Scripts/legacy/roku_player.brs': 'sub Main()\n  print "roku"\nend sub',
                'build/generated_task.py': 'def generated_task(): return True',
                'data/terraform_enterprise/main.tf': 'resource "example" "hub" {}',
                'data/echo_training/reference_tool.py': 'def train_echo(): return "reference"',
                'data/personality/personaEcho.json': '{"dialogue_style": "persona-only"}',
                'data/sessions.json': '{"private-session-content": true}',
                'data/conversations/private.py': 'def private_conversation(): pass',
                'venv/Scripts/site_package.py': 'def third_party(): pass',
            }
            for relative_path, content in files.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')

            bot = EchoChatBot(
                training_store=TrainingDataStore(storage_path=str(root / 'training'))
            )
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            indexed_files = {
                path
                for language_data in bot._reference_index.values()
                for path in language_data['files']
            }
            self.assertIn('scripts/team/nested/inventory.py', indexed_files)
            self.assertIn('scripts/legacy/roku_player.brs', indexed_files)
            self.assertIn('build/generated_task.py', indexed_files)
            self.assertIn('data/terraform_enterprise/main.tf', indexed_files)
            self.assertIn('data/echo_training/reference_tool.py', indexed_files)
            self.assertNotIn('data/personality/personaEcho.json', indexed_files)
            self.assertNotIn('data/sessions.json', indexed_files)
            self.assertNotIn('data/conversations/private.py', indexed_files)
            self.assertNotIn('venv/Scripts/site_package.py', indexed_files)

            newly_added = root / 'scripts' / 'newly_added' / 'just_added.fish'
            newly_added.parent.mkdir(parents=True)
            newly_added.write_text('function just_added\nend\n', encoding='utf-8')
            response = bot.chat('!library find just added', session_id='dynamic_reference')
            self.assertIn('scripts/newly_added/just_added.fish', response['response'])

    def test_app_change_order_asks_for_missing_details_then_previews_before_editing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            reference_dir = root / 'templates'
            reference_dir.mkdir()
            (reference_dir / 'navigation.js').write_text(
                'function renderNavigation() { return "reference marker"; }\n',
                encoding='utf-8',
            )
            manager = EchoChangeApprovalManager(root / 'data' / 'approvals.sqlite3', root)
            bot = EchoChatBot(training_store=TrainingDataStore(storage_path=str(root / 'training')))
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            from unittest.mock import patch

            with patch.object(bot, '_persist_change_intake'), \
                    patch.object(bot, '_set_conversation_focus'), \
                    patch.object(bot, '_load_session_meta', return_value={}):
                clarification = bot.chat(
                    'Add a link that loads a page',
                    session_id='focused-app-change',
                    workspace_user_id='admin-1',
                    change_manager=manager,
                )
                self.assertIn('target URL or in-app path', clarification['response'])
                self.assertIn('new module/add-on or an existing app page', clarification['response'])
                self.assertIn('button or text link', clarification['response'])
                self.assertIn('language/stack', clarification['response'])

                proposal_json = (
                    '{"summary":"Add a navigation page link","files":['
                    '{"path":"addons/navigation_link.py","content":"def navigation_link():\\n    return \'/movies\'\\n"}]}'
                )
                with patch.object(bot, '_generate_with_local_llm', return_value=proposal_json) as local_model:
                    drafted = bot.chat(
                        'target=/movies; label=Movies; placement=header; control=button; '
                        'scope=existing app feature; language=JavaScript',
                        session_id='focused-app-change',
                        workspace_user_id='admin-1',
                        change_manager=manager,
                    )

            self.assertIn('Proposal ready', drafted['response'])
            self.assertIn('!confirmed', drafted['response'])
            self.assertIn('reference marker', local_model.call_args.args[0])
            self.assertFalse((root / 'addons' / 'navigation_link.py').exists())
            applied = manager.confirm_pending('focused-app-change', 'admin-1')
            self.assertEqual(applied['files'], ['addons/navigation_link.py'])
            self.assertTrue((root / 'addons' / 'navigation_link.py').is_file())

    def test_context_prompt_keeps_saved_focus_and_does_not_duplicate_current_turn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bot = EchoChatBot(training_store=TrainingDataStore(storage_path=tmpdir))
            bot.conversation_history['focus-session'] = [
                ChatMessage(
                    role='user',
                    content='Add a navigation link to the movies page',
                    timestamp=1.0,
                    session_id='focus-session',
                    message_id='user-1',
                ),
                ChatMessage(
                    role='user',
                    content='It should be a button',
                    timestamp=2.0,
                    session_id='focus-session',
                    message_id='user-2',
                ),
            ]

            from unittest.mock import patch

            with patch.object(
                bot,
                '_load_session_meta',
                return_value={
                    'echo_focus': {
                        'topic': 'Add a navigation link to the movies page',
                        'stage': 'clarifying',
                        'details': {'control': 'button'},
                    }
                },
            ):
                prompt = bot._build_context_prompt('focus-session', 'It should be a button')

            assert 'Active conversation focus (clarifying)' in prompt
            assert 'Known requirements' in prompt
            assert prompt.count('User: It should be a button') == 1

    def test_library_command_finds_user_script_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts = root / 'data' / 'scripts'
            scripts.mkdir(parents=True)
            (scripts / 'orphan_backup.py').write_text('print("backup")', encoding='utf-8')
            extracted = root / 'data' / 'uploads' / 'extracted'
            extracted.mkdir(parents=True)
            (extracted / 'legacy_irc_bot.php').write_text('<?php echo "irc";', encoding='utf-8')
            store = TrainingDataStore(storage_path=str(root / 'training'))
            bot = EchoChatBot(training_store=store)
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            response = bot.chat('!library find orphan backup', session_id='code_library')
            old_prototype = bot.chat('!library find legacy irc bot', session_id='code_library')

            self.assertIn('data/scripts/orphan_backup.py', response['response'])
            self.assertIn('data/uploads/extracted/legacy_irc_bot.php', old_prototype['response'])

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
    
    def test_natural_script_request_gets_questions_then_generates_from_local_examples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            examples = root / 'chatops'
            examples.mkdir()
            (examples / 'scan_example.py').write_text(
                'def scan_project():\n    return "local script reference"\n',
                encoding='utf-8',
            )
            bot = EchoChatBot(training_store=TrainingDataStore(storage_path=str(root / 'training')))
            bot._workspace_root = root
            bot._refresh_language_reference_index(force=True)

            from unittest.mock import patch

            with patch.object(bot, '_load_session_meta', return_value={}), \
                    patch.object(bot, '_persist_script_intake'), \
                    patch.object(bot, '_set_conversation_focus'):
                clarification = bot.chat('I want a script', session_id='natural-script')
                self.assertIn('what the script should accomplish', clarification['response'])
                self.assertIn('language/runtime', clarification['response'])

                with patch.object(bot, '_generate_with_local_llm', return_value='```python\nprint("ready")\n```') as local_model:
                    draft = bot.chat(
                        'Python; scan the project for duplicate script names and ignore build output',
                        session_id='natural-script',
                    )

            self.assertIn('print("ready")', draft['response'])
            self.assertIn('local script reference', local_model.call_args.args[0])

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
