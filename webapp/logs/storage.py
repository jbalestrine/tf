"""Log storage and persistence."""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from .collector import LogEntry

logger = logging.getLogger(__name__)


class LogStorage:
    """Stores logs for retrieval and search."""
    
    def __init__(self, redis_client=None, max_logs: int = 10000):
        self.redis = redis_client
        self.max_logs = max_logs
        self.memory_logs: List[LogEntry] = []
    
    async def store(self, log_entry: LogEntry):
        """
        Store a log entry.
        
        Args:
            log_entry: LogEntry to store
        """
        # Store in memory
        self.memory_logs.append(log_entry)
        
        # Trim if exceeds max
        if len(self.memory_logs) > self.max_logs:
            self.memory_logs = self.memory_logs[-self.max_logs:]
        
        # Store in Redis if available
        if self.redis:
            try:
                key = f"logs:{log_entry.timestamp}"
                self.redis.setex(key, 86400, log_entry.to_json())  # 24 hour TTL
            except Exception as e:
                logger.error(f"Error storing log in Redis: {e}")
    
    async def get_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[LogEntry]:
        """
        Retrieve logs with optional filtering.
        
        Args:
            limit: Maximum number of logs to return
            level: Filter by log level
            source: Filter by source
            since: Filter logs since this datetime
        
        Returns:
            List of LogEntry objects
        """
        logs = self.memory_logs.copy()
        
        # Apply filters
        if level:
            logs = [log for log in logs if log.level == level]
        
        if source:
            logs = [log for log in logs if log.source == source]
        
        if since:
            since_str = since.isoformat()
            logs = [log for log in logs if log.timestamp >= since_str]
        
        # Return last N logs
        return logs[-limit:]
    
    async def search_logs(self, query: str, limit: int = 100) -> List[LogEntry]:
        """
        Search logs by message content.
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching LogEntry objects
        """
        matching = [
            log for log in self.memory_logs
            if query.lower() in log.message.lower()
        ]
        return matching[-limit:]
    
    async def clear_old_logs(self, days: int = 7):
        """
        Clear logs older than specified days.
        
        Args:
            days: Number of days to keep
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        self.memory_logs = [
            log for log in self.memory_logs
            if log.timestamp >= cutoff_str
        ]
        
        logger.info(f"Cleared logs older than {days} days")
    
    def get_stats(self) -> dict:
        """Get log storage statistics."""
        return {
            "total_logs": len(self.memory_logs),
            "max_logs": self.max_logs,
            "oldest_log": self.memory_logs[0].timestamp if self.memory_logs else None,
            "newest_log": self.memory_logs[-1].timestamp if self.memory_logs else None
        }
