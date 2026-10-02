"""Log collection from multiple sources."""
import logging
import asyncio
from typing import List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Represents a log entry."""
    timestamp: str
    level: str
    source: str
    message: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "metadata": self.metadata
        }
    
    def to_json(self):
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class LogCollector:
    """Collects logs from multiple sources."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.handlers: List[Callable] = []
        self.collecting = False
        self.collection_task = None
    
    def add_handler(self, handler: Callable):
        """Add a log handler."""
        self.handlers.append(handler)
        logger.info(f"Added log handler: {handler.__name__}")
    
    def remove_handler(self, handler: Callable):
        """Remove a log handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.info(f"Removed log handler: {handler.__name__}")
    
    async def collect_log(self, log_entry: LogEntry):
        """
        Collect a log entry and distribute to handlers.
        
        Args:
            log_entry: LogEntry to collect
        """
        # Send to all handlers
        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(log_entry)
                else:
                    handler(log_entry)
            except Exception as e:
                logger.error(f"Error in log handler: {e}")
        
        # Publish to event bus if available
        if self.event_bus:
            from core.event_bus import Event
            event = Event(
                type="log.entry",
                source=log_entry.source,
                data=log_entry.to_dict()
            )
            await self.event_bus.publish(event)
    
    async def start_collecting(self):
        """Start collecting logs."""
        if self.collecting:
            logger.warning("Log collector already running")
            return
        
        self.collecting = True
        logger.info("Started log collection")
    
    async def stop_collecting(self):
        """Stop collecting logs."""
        self.collecting = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped log collection")
    
    def create_log_entry(
        self,
        level: str,
        source: str,
        message: str,
        metadata: Optional[dict] = None
    ) -> LogEntry:
        """Create a log entry."""
        return LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            source=source,
            message=message,
            metadata=metadata or {}
        )
