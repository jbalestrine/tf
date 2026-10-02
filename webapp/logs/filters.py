"""Log filtering and search utilities."""
import re
from typing import Callable, List
from .collector import LogEntry


class LogFilter:
    """Filters logs based on various criteria."""
    
    @staticmethod
    def by_level(level: str) -> Callable[[LogEntry], bool]:
        """Create a filter for log level."""
        def filter_func(log: LogEntry) -> bool:
            return log.level == level
        return filter_func
    
    @staticmethod
    def by_source(source: str) -> Callable[[LogEntry], bool]:
        """Create a filter for log source."""
        def filter_func(log: LogEntry) -> bool:
            return log.source == source
        return filter_func
    
    @staticmethod
    def by_pattern(pattern: str) -> Callable[[LogEntry], bool]:
        """Create a filter for regex pattern matching."""
        regex = re.compile(pattern, re.IGNORECASE)
        
        def filter_func(log: LogEntry) -> bool:
            return bool(regex.search(log.message))
        return filter_func
    
    @staticmethod
    def by_levels(levels: List[str]) -> Callable[[LogEntry], bool]:
        """Create a filter for multiple log levels."""
        level_set = set(levels)
        
        def filter_func(log: LogEntry) -> bool:
            return log.level in level_set
        return filter_func
    
    @staticmethod
    def exclude_sources(sources: List[str]) -> Callable[[LogEntry], bool]:
        """Create a filter to exclude specific sources."""
        source_set = set(sources)
        
        def filter_func(log: LogEntry) -> bool:
            return log.source not in source_set
        return filter_func
    
    @staticmethod
    def combine_filters(*filters: Callable[[LogEntry], bool]) -> Callable[[LogEntry], bool]:
        """Combine multiple filters with AND logic."""
        def filter_func(log: LogEntry) -> bool:
            return all(f(log) for f in filters)
        return filter_func
    
    @staticmethod
    def any_filter(*filters: Callable[[LogEntry], bool]) -> Callable[[LogEntry], bool]:
        """Combine multiple filters with OR logic."""
        def filter_func(log: LogEntry) -> bool:
            return any(f(log) for f in filters)
        return filter_func
    
    @staticmethod
    def has_metadata_key(key: str) -> Callable[[LogEntry], bool]:
        """Create a filter for logs with specific metadata key."""
        def filter_func(log: LogEntry) -> bool:
            return key in log.metadata
        return filter_func
    
    @staticmethod
    def metadata_equals(key: str, value: any) -> Callable[[LogEntry], bool]:
        """Create a filter for logs with specific metadata value."""
        def filter_func(log: LogEntry) -> bool:
            return log.metadata.get(key) == value
        return filter_func
