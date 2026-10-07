"""
Integration tests for Echo Chat API endpoints.
"""

import os
import sys
import unittest
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import after path is set
from main import app


class TestEchoAPI(unittest.TestCase):
    """Test Echo chat API endpoints."""
    
    def setUp(self):
        """Set up test client."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_echo_chat_page_loads(self):
        """Test that Echo chat page loads successfully."""
        response = self.client.get('/echo-chat')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Echo Starlite - Chat', response.data)
        self.assertIn(b'Training Stats', response.data)

    def test_chatserv_page_and_public_room_state_load(self):
        page = self.client.get('/chatserv')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Echo ChatServ', page.data)

        state = self.client.get('/api/chatserv/state?channel=%23lobby')
        self.assertEqual(state.status_code, 200)
        self.assertIn('Welcome to MasterChief Echo ChatServ', state.get_json()['motd'])

    def test_gguf_model_listing_uses_success_response_contract(self):
        response = self.client.get('/api/echo/models')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['ok'])
        self.assertIsInstance(data['models'], list)

    def test_gguf_selection_requires_rbac_admin(self):
        response = self.client.post(
            '/api/echo/select_model',
            json={'model': 'example.gguf'},
            headers={'Origin': 'http://localhost'},
        )
        self.assertEqual(response.status_code, 403)
    
    def test_echo_chat_api(self):
        """Test Echo chat API endpoint."""
        response = self.client.post('/api/echo/chat',
                                     json={'message': 'Hello', 'session_id': 'test'})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('response', data)
        self.assertIn('session_id', data)
        self.assertIn('timestamp', data)
        self.assertIn('message_id', data)
        self.assertEqual(data['session_id'], 'test')

    def test_echo_chat_followup_stays_on_topic(self):
        """Short follow-up should remain anchored to active session topic."""
        sid = 'followup_topic_test'
        r1 = self.client.post('/api/echo/chat',
                              json={'message': 'I need help designing a deployment pipeline', 'session_id': sid})
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.post('/api/echo/chat',
                              json={'message': 'and what about rollback?', 'session_id': sid, 'debug': True})
        self.assertEqual(r2.status_code, 200)
        d2 = json.loads(r2.data)
        self.assertIn('response', d2)
        # Ensure this is not a generic unknown fallback.
        self.assertNotIn("I'm still learning", d2['response'])
        self.assertNotIn("That's new to me", d2['response'])
        # Debug contract helps IDE/coding-check integrations understand the route taken.
        self.assertIn('_path', d2)

    def test_echo_chat_debug_contract(self):
        """Debug mode returns stable trace metadata for integration diagnostics."""
        response = self.client.post('/api/echo/chat',
                                    json={'message': 'hello', 'session_id': 'debug_contract', 'debug': True})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('response', data)
        self.assertIn('_path', data)
        self.assertIn('_session_has_topic', data)
    
    def test_echo_chat_api_no_message(self):
        """Test Echo chat API with no message."""
        response = self.client.post('/api/echo/chat',
                                     json={'session_id': 'test'})
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_echo_stats_api(self):
        """Test Echo stats API endpoint."""
        response = self.client.get('/api/echo/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('total_examples', data)
        self.assertIn('quality_distribution', data)
        self.assertIn('patterns_learned', data)
    
    def test_echo_train_api(self):
        """Test Echo training API endpoint."""
        response = self.client.post('/api/echo/train',
                                     json={
                                         'user_message': 'test question',
                                         'bot_response': 'test answer',
                                         'quality': 'excellent'
                                     })
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('success', data)
        self.assertTrue(data['success'])
    
    def test_echo_history_api(self):
        """Test Echo history API endpoint."""
        # First, send a message
        self.client.post('/api/echo/chat',
                         json={'message': 'Test message', 'session_id': 'history_test'})
        
        # Then get history
        response = self.client.get('/api/echo/history?session_id=history_test')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('history', data)
        self.assertIsInstance(data['history'], list)
    
    def test_echo_search_api(self):
        """Test Echo search API endpoint."""
        response = self.client.get('/api/echo/search?q=test')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIsInstance(data['results'], list)
    
    def test_echo_search_api_no_query(self):
        """Test Echo search API with no query parameter."""
        response = self.client.get('/api/echo/search')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_echo_integrations_defaults(self):
        """Echo integrations should expose stable default policy shape."""
        response = self.client.get('/api/echo/integrations')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('ok'))
        self.assertIn('config', data)
        self.assertIn('effective', data)
        self.assertIn('chat', data['effective'])
        self.assertIn('web_ide', data['effective'])
        self.assertIn('training', data['effective'])
        self.assertIn('modules', data['effective'])

    def test_echo_integrations_module_toggle(self):
        """Per-module toggle should be writable and reflected in effective projection."""
        set_resp = self.client.post('/api/echo/integrations',
                                    json={'module': 'rbac', 'enabled': True})
        self.assertEqual(set_resp.status_code, 200)
        set_data = json.loads(set_resp.data)
        self.assertTrue(set_data.get('ok'))

        get_resp = self.client.get('/api/echo/integrations')
        self.assertEqual(get_resp.status_code, 200)
        get_data = json.loads(get_resp.data)
        self.assertTrue(get_data.get('effective', {}).get('modules', {}).get('rbac', False))

    def test_echo_integrations_core_scopes_protected_by_default(self):
        """chat/web_ide/training stay enabled by default lock policy."""
        response = self.client.post('/api/echo/integrations',
                                    json={'auto': {'chat': False, 'web_ide': False, 'training': False}})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('ok'))
        self.assertTrue(data.get('effective', {}).get('chat'))
        self.assertTrue(data.get('effective', {}).get('web_ide'))
        self.assertTrue(data.get('effective', {}).get('training'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
