"""REST API endpoints for logs."""
from flask import Blueprint, jsonify, request
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

logs_bp = Blueprint('logs', __name__)

# Global log storage instance (will be initialized by app)
_log_storage = None


def init_logs_api(log_storage):
    """Initialize logs API with storage instance."""
    global _log_storage
    _log_storage = log_storage


@logs_bp.route('/logs', methods=['GET'])
async def get_logs():
    """
    Get logs with optional filtering.
    
    Query params:
        - limit: Maximum number of logs (default: 100)
        - level: Filter by log level
        - source: Filter by source
        - since: Filter logs since timestamp (ISO format)
    """
    if not _log_storage:
        return jsonify({'error': 'Log storage not initialized'}), 500
    
    limit = request.args.get('limit', 100, type=int)
    level = request.args.get('level')
    source = request.args.get('source')
    since_str = request.args.get('since')
    
    since = None
    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            return jsonify({'error': 'Invalid since timestamp'}), 400
    
    logs = await _log_storage.get_logs(
        limit=limit,
        level=level,
        source=source,
        since=since
    )
    
    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'count': len(logs)
    })


@logs_bp.route('/logs/search', methods=['GET'])
async def search_logs():
    """
    Search logs by message content.
    
    Query params:
        - q: Search query
        - limit: Maximum results (default: 100)
    """
    if not _log_storage:
        return jsonify({'error': 'Log storage not initialized'}), 500
    
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    limit = request.args.get('limit', 100, type=int)
    
    logs = await _log_storage.search_logs(query, limit)
    
    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'count': len(logs),
        'query': query
    })


@logs_bp.route('/logs/stats', methods=['GET'])
def get_log_stats():
    """Get log storage statistics."""
    if not _log_storage:
        return jsonify({'error': 'Log storage not initialized'}), 500
    
    stats = _log_storage.get_stats()
    return jsonify(stats)


@logs_bp.route('/logs/levels', methods=['GET'])
def get_log_levels():
    """Get available log levels."""
    return jsonify({
        'levels': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    })


@logs_bp.route('/logs/sources', methods=['GET'])
async def get_log_sources():
    """Get list of log sources."""
    if not _log_storage:
        return jsonify({'error': 'Log storage not initialized'}), 500
    
    # Get all logs and extract unique sources
    logs = await _log_storage.get_logs(limit=10000)
    sources = list(set(log.source for log in logs))
    
    return jsonify({
        'sources': sorted(sources)
    })
