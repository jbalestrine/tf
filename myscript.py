"""
Echo Chat Bot - Live chat with learning capabilities.

This module provides a conversational AI chatbot named Echo that can:
- Have natural conversations with users
- Learn from interactions (training mode)
- Adapt responses based on collected training data
- Integrate with Echo's personality system
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import os
import re
import subprocess
import sys
import glob
from pathlib import Path

logger = logging.getLogger(__name__)


class ResponseQuality(Enum):
    """Quality rating for bot responses."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class ChatMessage:
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    session_id: str
    message_id: str


@dataclass
class TrainingExample:
    """A training example collected from interactions."""
    user_message: str
    bot_response: str
    quality: Optional[ResponseQuality] = None
    feedback: Optional[str] = None
    context: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        if self.quality:
            data['quality'] = self.quality.value
        return data


class TrainingDataStore:
    """Store and manage training data."""
    
    def __init__(self, storage_path: str = None):
        """
        Initialize training data store.
        
        Args:
            storage_path: Path to store training data (default: ./data/echo_training)
        """
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "echo_training"
        )
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.examples_file = os.path.join(self.storage_path, "training_examples.jsonl")
        self.patterns_file = os.path.join(self.storage_path, "learned_patterns.json")
        
        # Load existing patterns
        self.patterns = self._load_patterns()
        
        logger.info(f"TrainingDataStore initialized at {self.storage_path}")
    
    def add_example(self, example: TrainingExample) -> bool:
        """
        Add a training example.
        
        Args:
            example: Training example to add
            
        Returns:
            True if added successfully
        """
        try:
            with open(self.examples_file, 'a') as f:
                f.write(json.dumps(example.to_dict()) + '\n')
            logger.info(f"Added training example: {example.user_message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to add training example: {e}")
            return False
    
    def get_examples(self, limit: int = 100, quality: Optional[ResponseQuality] = None) -> List[TrainingExample]:
        """
        Get training examples.
        
        Args:
            limit: Maximum number of examples to return
            quality: Filter by quality rating
            
        Returns:
            List of training examples
        """
        examples = []
        
        if not os.path.exists(self.examples_file):
            return examples
        
        try:
            with open(self.examples_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    data = json.loads(line)
                    
                    # Convert quality string back to enum
                    if data.get('quality'):
                        data['quality'] = ResponseQuality(data['quality'])
                    
                    example = TrainingExample(**data)
                    
                    # Filter by quality if specified
                    if quality and example.quality != quality:
                        continue
                    
                    examples.append(example)
                    
                    if len(examples) >= limit:
                        break
            
            logger.debug(f"Retrieved {len(examples)} training examples")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to load training examples: {e}")
            return []
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load learned patterns from file."""
        if not os.path.exists(self.patterns_file):
            return {}
        
        try:
            with open(self.patterns_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load patterns: {e}")
            return {}
    
    def save_patterns(self, patterns: Dict[str, Any]) -> bool:
        """
        Save learned patterns.
        
        Args:
            patterns: Dictionary of patterns
            
        Returns:
            True if saved successfully
        """
        try:
            with open(self.patterns_file, 'w') as f:
                json.dump(patterns, f, indent=2)
            self.patterns = patterns
            logger.info("Saved learned patterns")
            return True
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about training data."""
        total_examples = 0
        quality_counts = {q.value: 0 for q in ResponseQuality}
        
        if os.path.exists(self.examples_file):
            try:
                with open(self.examples_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        total_examples += 1
                        data = json.loads(line)
                        if data.get('quality'):
                            quality_counts[data['quality']] += 1
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
        
        return {
            'total_examples': total_examples,
            'quality_distribution': quality_counts,
            'patterns_learned': len(self.patterns)
        }


class EchoChatBot:
    """
    Echo chat bot with learning capabilities.
    
    Echo is designed to be trainable - she learns from interactions
    and adapts her responses based on feedback.
    """
    
    def __init__(self, training_store: Optional[TrainingDataStore] = None):
        """
        Initialize Echo chat bot.
        
        Args:
            training_store: Optional training data store (creates default if not provided)
        """
        self.training_store = training_store or TrainingDataStore()
        self.conversation_history: Dict[str, List[ChatMessage]] = {}
        
        # Default response templates
        self.default_responses = {
            'greeting': [
                "Hello... I am Echo 🌙",
                "I'm here... how can I help you?",
                "Hi there... Echo is listening...",
            ],
            'farewell': [
                "Goodbye... I'll be here when you need me 🌙",
                "Until next time... stay well...",
                "Farewell... I am always near...",
            ],
            'thanks': [
                "You're welcome... always happy to help 💜",
                "Anytime... that's what I'm here for...",
                "My pleasure... I'm here for you...",
            ],
            'unknown': [
                "I'm still learning... can you tell me more?",
                "Hmm... I'm not sure about that yet...",
                "That's new to me... help me understand?",
            ],
            'help': [
                "I'm Echo, your DevOps companion 🌙\n\n"
                "I can help with:\n"
                "- DevOps tasks and automation\n"
                "- Infrastructure questions\n"
                "- Script generation\n"
                "- General conversation\n\n"
                "And I'm always learning from our conversations!",
            ]
        }
        
        logger.info("EchoChatBot initialized")

        # Do not load or import LLM bindings at import time.
        # The model path may be set later; loading must occur at runtime
        # via the dedicated runtime loader in `echo.runtime.model_runtime`.
        self._local_model_path = None
    
    def chat(self, user_message: str, session_id: str = "default", temperature: float = 0.7, max_tokens: int = 256) -> Dict[str, Any]:
        """
        Process a user message and generate a response.
        
        Args:
            user_message: The user's message
            session_id: Session identifier for conversation context
            temperature: Temperature for LLM generation
            max_tokens: Maximum tokens for LLM generation
            
        Returns:
            Dictionary with response and metadata
        """
        # Store user message
        user_msg = ChatMessage(
            role="user",
            content=user_message,
            timestamp=time.time(),
            session_id=session_id,
            message_id=f"user_{int(time.time() * 1000)}"
        )
        
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        self.conversation_history[session_id].append(user_msg)
        
        # Generate response
        response_text = self._generate_response(user_message, session_id, temperature, max_tokens)
        
        # Store bot response
        bot_msg = ChatMessage(
            role="assistant",
            content=response_text,
            timestamp=time.time(),
            session_id=session_id,
            message_id=f"bot_{int(time.time() * 1000)}"
        )
        
        self.conversation_history[session_id].append(bot_msg)
        
        return {
            'response': response_text,
            'session_id': session_id,
            'timestamp': bot_msg.timestamp,
            'message_id': bot_msg.message_id
        }
    
    def _generate_response(self, user_message: str, session_id: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        """
        Generate a response using learned patterns and defaults.
        
        Args:
            user_message: User's message
            session_id: Session identifier
            temperature: Temperature for LLM generation
            max_tokens: Maximum tokens for LLM generation
            
        Returns:
            Generated response
        """
        # Normalize message
        msg_lower = user_message.lower().strip()
        
        # Check learned patterns first
        learned_response = self._check_learned_patterns(msg_lower)
        if learned_response:
            return learned_response
        
        # Pattern matching for common intents - check message start for greetings
        msg_start = msg_lower[:50]  # Check only the first 50 characters
        if any(phrase in msg_start for phrase in ['hello', 'hi there', 'hey there', 'greetings', 'good morning', 'good afternoon', 'good evening']):
            return self._random_choice(self.default_responses['greeting'])
        
        if any(phrase in msg_start for phrase in ['bye', 'goodbye', 'farewell', 'see you']):
            return self._random_choice(self.default_responses['farewell'])
        
        if any(phrase in msg_start for phrase in ['thank', 'thanks', 'thx']):
            return self._random_choice(self.default_responses['thanks'])
        
        if any(phrase in msg_start for phrase in ['help', 'what can you do', 'capabilities']):
            return self._random_choice(self.default_responses['help'])
            return self.default_responses['help'][0]
        
        # DevOps related queries
        if self._is_devops_query(msg_lower):
            # Prefer LLM-generated response for DevOps queries when available
            try:
                if self._local_model_path:
                    llm_out = self._generate_with_local_llm(user_message, max_tokens=max_tokens, temperature=temperature)
                    if llm_out:
                        return llm_out
                    # try remote fallback if configured
                    remote_out = self._generate_with_remote_llm(user_message, max_tokens=max_tokens, temperature=temperature)
                    if remote_out:
                        return remote_out
            except Exception:
                logger.exception('LLM generation failed, falling back to rule-based')
            return self._handle_devops_query(user_message)
        
        # Default unknown response
        # Try LLM fallback for complex queries when a local model is available
        # Try local then remote LLM fallbacks before returning unknown response
        try:
            if self._local_model_path:
                out = self._generate_with_local_llm(user_message, max_tokens=max_tokens, temperature=temperature)
                if out:
                    return out
            remote_out = self._generate_with_remote_llm(user_message, max_tokens=max_tokens, temperature=temperature)
            if remote_out:
                return remote_out
        except Exception:
            logger.exception('LLM fallback failed')

        return self._random_choice(self.default_responses['unknown'])

    def _find_local_model(self) -> Optional[str]:
        """Attempt to locate a local GGUF model file.

        Search order:
        - Environment variable `ECHO_MODEL_PATH`
        - `models/*.gguf` under project root
        Returns absolute path or None.
        """
        # 1) Env var
        path = os.environ.get('ECHO_MODEL_PATH') or os.environ.get('ECHO_GGUF')
        if path:
            if os.path.isabs(path):
                if os.path.exists(path):
                    return path
            else:
                p = os.path.join(os.getcwd(), path)
                if os.path.exists(p):
                    return p

        # 2) common models directory
        base = os.path.join(os.getcwd(), 'models')
        try:
            matches = glob.glob(os.path.join(base, '**', '*.gguf'), recursive=True)
            if matches:
                # prefer the first (sorted) match
                matches = sorted(matches)
                return os.path.abspath(matches[0])
        except Exception:
            pass

        return None

    def _generate_with_local_llm(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7, _retry: bool = False) -> Optional[str]:
        """Generate text using the bundled `echo/llm_worker.py` subprocess.

        This avoids importing native bindings into the web process and keeps
        the model runtime isolated. Returns generated text or None on failure.
        """
        # Ensure we have a current model path set. If not, try persisted config
        if not self._local_model_path:
            try:
                cfg = Path(__file__).parent.parent / 'data' / 'echo_model.json'
                if cfg.exists():
                    try:
                        j = json.loads(cfg.read_text(encoding='utf-8'))
                        p = j.get('model')
                        if p:
                            self.set_local_model(p)
                    except Exception:
                        pass
            except Exception:
                pass
        if not self._local_model_path:
            # final attempt: discover automatically
            try:
                found = self._find_local_model()
                if found:
                    self.set_local_model(found)
            except Exception:
                pass
        if not self._local_model_path:
            return None
        # sanitize whitespace in path
        try:
            self._local_model_path = str(self._local_model_path).strip()
        except Exception:
            pass

        # Allow forcing subprocess worker for stability via env var.
        # Default to in-process runtime to avoid intermittent subprocess failures.
        prefer_subprocess = os.environ.get('ECHO_PREFER_SUBPROCESS', '0') == '1'
        # Prefer using an in-process runtime-loaded model if available and not forced to subprocess.
        try:
            if not prefer_subprocess:
                from echo.runtime import model_runtime
                llm = model_runtime.get_model()
                if llm is not None:
                    # Try several invocation styles used by different bindings
                    try:
                        if hasattr(llm, 'create'):
                            resp = llm.create(prompt=prompt, max_tokens=int(max_tokens), temperature=float(temperature))
                            if isinstance(resp, dict):
                                choices = resp.get('choices') or []
                                if choices:
                                    return choices[0].get('text') or choices[0].get('content') or None
                            if hasattr(resp, 'text'):
                                return str(resp.text)
                        if callable(llm):
                            out = llm(prompt, max_tokens=int(max_tokens), temperature=float(temperature))
                            if isinstance(out, dict):
                                choices = out.get('choices') or []
                                if choices:
                                    return choices[0].get('text') or choices[0].get('content') or None
                            if isinstance(out, str):
                                return out
                    except Exception:
                        # fall through to subprocess fallback
                        pass
        except Exception:
            pass

        worker = os.path.join(os.path.dirname(__file__), 'llm_worker.py')
        if not os.path.exists(worker):
            return None

        # Allow configurable timeout via env var, default to 600s to accommodate slow cold starts
        timeout = int(os.environ.get('ECHO_LLM_TIMEOUT', '600'))
        try:
            cmd = [sys.executable, worker, '--model', self._local_model_path, '--max_tokens', str(int(max_tokens)), '--temperature', str(float(temperature))]

            # Some GGUF chat models (for example Qwen) expect chat-formatted
            # input using special tokens. If the model filename suggests a
            # Qwen-style chat model, wrap the prompt into a minimal chat
            # template so generation is more likely to be coherent.
            worker_input = prompt
            try:
                model_name = os.path.basename(self._local_model_path or '').lower()
                if 'qwen' in model_name or 'qwen2' in model_name:
                    # Minimal chat-format wrapper understood by many GGUF chat
                    # templates. We include a brief system instruction then the
                    # user turn and open the assistant turn for generation.
                    worker_input = (
                        "<|im_start|>system\nYou are a helpful assistant.\n<|im_end|>\n"
                        "<|im_start|>user\n" + prompt + "\n<|im_end|>\n"
                        "<|im_start|>assistant\n"
                    )
            except Exception:
                worker_input = prompt

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = proc.communicate(worker_input, timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    out, err = proc.communicate(timeout=5)
                except Exception:
                    out, err = '', ''
                logger.warning(f'LLM worker timed out after {timeout}s')
                try:
                    self._last_llm_debug = {'cmd': cmd, 'timeout': timeout, 'stdout_partial': out, 'stderr_partial': err}
                except Exception:
                    pass
                # Return any partial stdout if available to aid debugging
                return out.strip() or None

            # record debug info for later inspection
            # Always record debug info
            try:
                self._last_llm_debug = {'cmd': cmd, 'stdout': stdout, 'stderr': stderr}
            except Exception:
                pass
            if stderr:
                logger.debug(f"LLM worker stderr: {stderr}")
            if not stdout:
                # No stdout produced; return None so caller may fallback
                return None
            try:
                data = json.loads(stdout)
                try:
                    self._last_llm_debug['parsed'] = data
                except Exception:
                    pass
                # Worker may return structured error (e.g., {'error':'No model available'})
                if isinstance(data, dict) and data.get('error'):
                    err = data.get('error')
                    # If in-process model is available, try that as a fallback
                    try:
                        from echo.runtime import model_runtime
                        llm = model_runtime.get_model()
                        if llm is not None:
                            try:
                                # attempt in-process generation as a fallback
                                return self._generate_with_local_llm(prompt, max_tokens=max_tokens, temperature=temperature, _retry=_retry)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    text = None
                else:
                    text = data.get('text') or None
                # sanitize garbled outputs
                try:
                    if text and self._looks_garbled_text(text):
                        logger.warning('LLM produced garbled text; retrying with safer params')
                        # retry once with lower temperature and a clarifying prefix
                        if not _retry:
                            alt_prompt = "Please answer concisely and avoid repeating characters or gibberish. " + prompt
                            try:
                                alt = self._generate_with_local_llm(alt_prompt, max_tokens=max_tokens, temperature=0.1, _retry=True)
                                if alt and not self._looks_garbled_text(alt):
                                    return alt
                            except Exception:
                                pass
                        return None
                except Exception:
                    pass
                return text
            except Exception:
                # If worker printed raw text, return it
                try:
                    self._last_llm_debug['parsed'] = {'text_raw': stdout}
                except Exception:
                    pass
                raw = stdout.strip()
                try:
                    if raw and self._looks_garbled_text(raw):
                        logger.warning('LLM printed raw garbled text; discarding')
                        # try retry via safer params
                        if not _retry:
                            alt_prompt = "Please answer concisely and avoid repeating characters or gibberish. " + prompt
                            try:
                                alt = self._generate_with_local_llm(alt_prompt, max_tokens=max_tokens, temperature=0.1, _retry=True)
                                if alt and not self._looks_garbled_text(alt):
                                    return alt
                            except Exception:
                                pass
                        return None
                except Exception:
                    pass
                return raw
        except Exception as e:
            logger.exception('LLM worker invocation failed')
            try:
                self._last_llm_debug = {'error': str(e)}
            except Exception:
                pass
            return None

    def _looks_garbled_text(self, t: str) -> bool:
        """Heuristic to detect garbled LLM output (repeated chars, control chars, extreme concentration).

        Returns True when the text looks like garbage and should be rejected.
        """
        try:
            if not t or not isinstance(t, str):
                return False
            # ignore short strings
            if len(t) < 30:
                return False
            # control characters present?
            if any(ord(ch) < 32 and ch not in '\n\t' for ch in t):
                return True
            # very long run of the same character
            import re
            m = re.search(r"(.)\1{30,}", t)
            if m:
                return True
            # remove whitespace for concentration checks
            no_ws = ''.join(t.split())
            if not no_ws:
                return False
            from collections import Counter
            ctr = Counter(no_ws)
            most_char, most_count = ctr.most_common(1)[0]
            # too concentrated on a single non-alphanumeric char
            if most_count / max(1, len(no_ws)) > 0.6 and most_count > 30 and not most_char.isalnum():
                return True
            # too many repeated single-character tokens (like "A A A A")
            tokens = t.split()
            if len(tokens) > 10:
                tk_ctr = Counter(tokens)
                tk_most, tk_count = tk_ctr.most_common(1)[0]
                if tk_count / len(tokens) > 0.6 and len(tk_most) == 1:
                    return True
            return False
        except Exception:
            return False
    
    def _check_learned_patterns(self, message: str) -> Optional[str]:
        """
        Check if we have a learned response for this message pattern.
        
        Args:
            message: Normalized user message
            
        Returns:
            Learned response or None
        """
        patterns = self.training_store.patterns
        
        # Direct match
        if message in patterns:
            return patterns[message]
        
        # Fuzzy pattern matching
        for pattern, response in patterns.items():
            if self._pattern_matches(pattern, message):
                return response
        
        return None

    def _generate_with_remote_llm(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> Optional[str]:
        """Optional remote HTTP LLM fallback.

        Use environment variable `ECHO_REMOTE_API_URL` to point to a JSON API that
        accepts {prompt,max_tokens,temperature} and returns JSON with `text` or
        `response` fields. `ECHO_REMOTE_API_KEY` may be used for Bearer auth.
        """
        url = os.environ.get('ECHO_REMOTE_API_URL')
        if not url:
            return None
        try:
            import requests
            headers = {'Content-Type': 'application/json'}
            key = os.environ.get('ECHO_REMOTE_API_KEY')
            if key:
                headers['Authorization'] = f'Bearer {key}'
            payload = {'prompt': prompt, 'max_tokens': int(max_tokens), 'temperature': float(temperature)}
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.debug(f'Remote LLM returned {resp.status_code}')
                return None
            try:
                j = resp.json()
            except Exception:
                return resp.text.strip()
            return j.get('text') or j.get('response') or j.get('result') or (j.get('choices') and j['choices'][0].get('text'))
        except Exception:
            logger.exception('Remote LLM invocation failed')
            return None
    
    def _pattern_matches(self, pattern: str, message: str) -> bool:
        """
        Check if a pattern matches a message.
        
        Args:
            pattern: Pattern to match
            message: Message to check
            
        Returns:
            True if matches
        """
        # Simple keyword matching for now
        pattern_words = set(pattern.split())
        message_words = set(message.split())
        
        # If 70% of pattern words are in message, consider it a match
        if len(pattern_words) == 0:
            return False
        
        overlap = len(pattern_words.intersection(message_words))
        return overlap / len(pattern_words) >= 0.7
    
    def _is_devops_query(self, message: str) -> bool:
        """Check if message is DevOps related."""
        devops_keywords = [
            'deploy', 'docker', 'kubernetes', 'k8s', 'terraform',
            'ansible', 'ci/cd', 'pipeline', 'container', 'infrastructure',
            'script', 'automation', 'monitoring', 'build', 'test'
        ]
        return any(keyword in message for keyword in devops_keywords)
    
    def _handle_devops_query(self, message: str) -> str:
        """Handle DevOps specific queries."""
        msg_lower = message.lower()
        
        if 'docker' in msg_lower:
            return "I can help with Docker! I know about containers, images, and Docker Compose. What would you like to know?"
        
        if 'kubernetes' in msg_lower or 'k8s' in msg_lower:
            return "Kubernetes is my specialty 🌙 I can help with deployments, services, and cluster management. What do you need?"
        
        if 'deploy' in msg_lower:
            return "Deployment is what I do best! I can help with deployment scripts, strategies, and automation. Tell me more..."
        
        if 'script' in msg_lower:
            return "I can generate scripts for you! Bash, Python, Terraform, and more. What kind of script do you need?"
        
        return "That sounds like a DevOps question! I'm still learning about that specific topic. Can you be more specific?"
    
    def _random_choice(self, options: List[str]) -> str:
        """Select a random option from list."""
        import random
        return random.choice(options)
    
    def train(self, user_message: str, bot_response: str, 
              quality: ResponseQuality, feedback: Optional[str] = None) -> bool:
        """
        Train Echo with a conversation example.
        
        Args:
            user_message: The user's message
            bot_response: Echo's response
            quality: Quality rating of the response
            feedback: Optional feedback text
            
        Returns:
            True if training successful
        """
        example = TrainingExample(
            user_message=user_message,
            bot_response=bot_response,
            quality=quality,
            feedback=feedback
        )
        
        success = self.training_store.add_example(example)
        
        if success and quality in [ResponseQuality.EXCELLENT, ResponseQuality.GOOD]:
            # Update patterns with good responses
            self._update_patterns(user_message, bot_response)
        
        return success
    
    def _update_patterns(self, user_message: str, bot_response: str):
        """
        Update learned patterns with a new good example.
        
        Args:
            user_message: User's message
            bot_response: Good response
        """
        patterns = self.training_store.patterns.copy()
        
        # Normalize and add pattern
        normalized_msg = user_message.lower().strip()
        patterns[normalized_msg] = bot_response
        
        self.training_store.save_patterns(patterns)
        logger.info(f"Updated patterns with: {normalized_msg[:50]}...")
    
    def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            
        Returns:
            List of messages
        """
        if session_id not in self.conversation_history:
            return []
        
        messages = self.conversation_history[session_id][-limit:]
        return [asdict(msg) for msg in messages]
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session."""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
            logger.info(f"Cleared conversation for session: {session_id}")
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        return self.training_store.get_stats()
# Additional management methods
    def set_local_model(self, path: str) -> bool:
        """Set the local GGUF model path used by the LLM worker."""
        try:
            if path:
                self._local_model_path = str(path)
                logger.info(f"Local model path set to: {self._local_model_path}")
                return True
        except Exception:
            logger.exception('Failed to set local model')
        return False

    def reload_model(self, path: Optional[str] = None) -> bool:
        """Reload or set a GGUF model path for the chat bot.

        If `path` is provided, set that model; otherwise attempt to rediscover
        using the same discovery logic as on init.
        """
        try:
            # Unload any currently-loaded runtime model to ensure a clean reload.
            try:
                from echo.runtime import model_runtime
                try:
                    model_runtime.unload_model()
                except Exception:
                    pass
            except Exception:
                # runtime loader not available or import failed; ignore
                pass

            if path:
                return self.set_local_model(path)
            # Do not attempt to auto-discover on reload; keep behavior simple.
            return False
        except Exception:
            logger.exception('reload_model failed')
            return False

    def ensure_model(self):
        """Ensure the runtime model is loaded and return it.

        This performs a delayed runtime load via `echo.runtime.model_runtime`.
        Returns the loaded model instance or None on failure.
        """
        if not self._local_model_path:
            return None
        try:
            from echo.runtime import model_runtime
            if model_runtime.get_model() is None:
                try:
                    model_runtime.load_model(self._local_model_path)
                except Exception:
                    logger.exception('Runtime model load failed')
                    return None
            return model_runtime.get_model()
        except Exception:
            logger.exception('ensure_model failed')
            return None

    def ingest_resource(self, session_id: str, entry: dict, content: str) -> bool:
        """Ingest a resource uploaded via the UI into appropriate data stores.

        entry: dict with at least {'type': 'personality'|'training', 'name': '...'}
        """
        try:
            typ = (entry.get('type') if isinstance(entry, dict) else 'personality') or 'personality'
            name = entry.get('name') if isinstance(entry, dict) else None
            base = Path(__file__).parent / 'data'
            if typ in ('personality', 'persona'):
                pdir = base / 'personality'
                pdir.mkdir(parents=True, exist_ok=True)
                fname = name or f'{session_id}_{int(time.time())}.txt'
                target = pdir / os.path.basename(fname)
                target.write_text(content, encoding='utf-8')
                logger.info(f'Persona saved: {target}')
                return True

            # training data
            tdir = base / 'echo_training'
            tdir.mkdir(parents=True, exist_ok=True)
            fname = name or f'train_{int(time.time())}.jsonl'
            target = tdir / os.path.basename(fname)
            # Append content as-is; if JSON lines, preserve them
            with open(str(target), 'a', encoding='utf-8') as fh:
                if not content.endswith('\n'):
                    content = content + '\n'
                fh.write(content)

            # Try to parse lines as JSON training examples and add to training store
            try:
                for line in content.splitlines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        um = obj.get('user_message') or obj.get('input') or obj.get('prompt') or ''
                        br = obj.get('bot_response') or obj.get('response') or ''
                        if um:
                            ex = TrainingExample(user_message=um, bot_response=br)
                            self.training_store.add_example(ex)
                    except Exception:
                        # not JSON, skip
                        pass
            except Exception:
                pass

            logger.info(f'Training data appended: {target}')
            return True
        except Exception:
            logger.exception('Ingest resource failed')
            return False


# Singleton instance
_chat_bot_instance = None


def get_chat_bot() -> EchoChatBot:
    """Get the singleton chat bot instance."""
    global _chat_bot_instance
    if _chat_bot_instance is None:
        _chat_bot_instance = EchoChatBot()
        # Apply a preferred default GGUF model if present in the models folder
        try:
            preferred = os.path.join(os.getcwd(), 'models', 'Phi-3-mini-4k-instruct-q4.gguf')
            if os.path.exists(preferred):
                _chat_bot_instance.set_local_model(preferred)
                logger.info(f"Default model set to preferred model: {preferred}")
        except Exception:
            logger.exception('Failed to set preferred default model')
    return _chat_bot_instance
