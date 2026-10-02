"""Real-time log streaming."""
import logging
import asyncio
from typing import Set, Callable
from .collector import LogEntry

logger = logging.getLogger(__name__)


class LogStreamer:
    """Streams logs to connected clients in real-time."""
    
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.streams: Set[str] = set()  # Active stream IDs
        self.filters = {}  # stream_id -> filter_func
    
    async def stream_log(self, log_entry: LogEntry):
        """
        Stream a log entry to connected clients.
        
        Args:
            log_entry: LogEntry to stream
        """
        if not self.socketio:
            return
        
        try:
            # Broadcast to all clients in logs room
            self.socketio.emit(
                'log_entry',
                log_entry.to_dict(),
                room='logs'
            )
        except Exception as e:
            logger.error(f"Error streaming log: {e}")
    
    def create_stream(self, stream_id: str, filter_func: Callable = None):
        """
        Create a new log stream.
        
        Args:
            stream_id: Unique stream identifier
            filter_func: Optional function to filter logs
        """
        self.streams.add(stream_id)
        if filter_func:
            self.filters[stream_id] = filter_func
        logger.info(f"Created log stream: {stream_id}")
    
    def close_stream(self, stream_id: str):
        """Close a log stream."""
        self.streams.discard(stream_id)
        if stream_id in self.filters:
            del self.filters[stream_id]
        logger.info(f"Closed log stream: {stream_id}")
    
    def get_active_streams(self) -> Set[str]:
        """Get list of active stream IDs."""
        return self.streams.copy()
    
    async def stream_filtered(self, log_entry: LogEntry, stream_id: str):
        """Stream log entry to a specific filtered stream."""
        if stream_id not in self.streams:
            return
        
        # Apply filter if exists
        if stream_id in self.filters:
            filter_func = self.filters[stream_id]
            if not filter_func(log_entry):
                return
        
        # Stream to specific room/channel
        if self.socketio:
            self.socketio.emit(
                'log_entry',
                log_entry.to_dict(),
                room=stream_id
            )
