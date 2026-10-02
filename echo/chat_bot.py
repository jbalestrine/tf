"""Compatibility wrapper for the Echo chat bot module.

The project historically imported `echo.chat_bot`, but the implementation currently
lives in `echo.chat_botx` during the refactor. This shim preserves the public API
expected by the rest of the app without reverting the modular refactor.
"""

from .chat_botx import *  # noqa: F401,F403
