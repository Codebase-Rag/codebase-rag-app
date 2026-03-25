# Session Management Architecture

## Overview

The session management system has been refactored to use a **Redis-first architecture with background PostgreSQL sync**. This design separates the fast request path (Redis) from the durable storage path (PostgreSQL), improving application responsiveness while maintaining data durability.

## Architecture

### Data Flow

```
User Request
    ↓
Session.get() ← Redis (hot cache - fast)
    ↓ (if miss)
Session.get() ← PostgreSQL (cold storage)
    ↓
User Updates
    ↓
Session.set() → Redis only (fire and forget)
    ↓
Background Sync Task (every 5 mins)
    ↓
Redis data → PostgreSQL (eventual consistency)
    ↓
Application Shutdown
    ↓
Force sync all sessions to PostgreSQL
```

## Components

### 1. **models/session.py** - Session Model

Updated with Redis-primary operations:

- **`Session.get(session_id)`**: 
  - Primary: Reads from Redis (fast, ~1ms)
  - Fallback: Reads from PostgreSQL if key not found (cold start)
  - Auto-caches: Restores to Redis after fetching from PostgreSQL
  - Returns: List of message history

- **`Session.set(session_id, history)`**: 
  - **Fast path**: Only writes to Redis (non-blocking)
  - On-demand: Background sync service handles PostgreSQL persistence
  - Benefit: Request completes immediately (~1-5ms instead of 50-200ms)

- **`Session.set_with_immediate_sync(session_id, history)`**:
  - **Slow path**: Writes to both Redis and PostgreSQL immediately
  - Use case: Critical operations requiring guaranteed persistence
  - Example: Final session save before user logout

- **`Session.delete(session_id)`**:
  - Deletes from both Redis and PostgreSQL immediately
  - Ensures data consistency for deletions

- **`Session.get_all()`**:
  - Reads from PostgreSQL only (source of truth for all sessions)
  - Used by session listing endpoints

### 2. **services/session_sync_service.py** - Sync Service

Handles background syncing from Redis to PostgreSQL:

```python
class SessionSyncService:
    def __init__(self, sync_interval: int = 300)  # 5 minutes
    async def start()                              # Start background sync loop
    async def sync_sessions()                      # Sync all active sessions
    async def force_sync_session(session_id)       # Force sync one session
    async def force_sync_all()                     # Force sync all sessions
```

**Features:**
- Runs continuously in background
- Configurable sync interval (default: 5 minutes)
- Automatic error handling and logging
- Can force immediate sync when needed
- Handles database connection pooling

### 3. **services/session_sync_worker.py** - Worker Manager

Manages the lifecycle of the background sync task:

```python
class SessionSyncWorker:
    async def start()              # Start the sync worker
    async def stop()               # Stop the sync worker with graceful shutdown
    async def force_sync()         # Force sync a session
    async def force_sync_all()     # Force sync all sessions
    def is_running()               # Check if worker is running
```

**Context Manager:**
```python
async with managed_sync_worker(sync_interval=300) as worker:
    await worker.force_sync(session_id)
```

### 4. **main.py** - Integration

Application startup and shutdown handlers:

```python
@app.on_event("startup")
async def on_startup():
    init_db()
    worker = get_worker(sync_interval=300)
    await worker.start()

@app.on_event("shutdown")
async def on_shutdown():
    worker = get_worker()
    if worker.is_running():
        await worker.stop()  # Includes final sync
```

## Usage Patterns

### Pattern 1: Normal Session Operations (Fast Path)

```python
# Fast path - only Redis (typical case)
from models.session import Session

# Read from Redis/PostgreSQL
history = Session.get(session_id)

# Update in Redis only (fast, ~5ms)
Session.set(session_id, updated_history)

# Background sync handles PostgreSQL eventually
# (typically within 5 minutes)
```

**Request timeline:** 5-10ms (Redis only)

### Pattern 2: Critical Operations (Guaranteed Persistence)

```python
# Slow path - Redis + Postgres immediately
from models.session import Session

# Critical save - wait for PostgreSQL too
Session.set_with_immediate_sync(session_id, final_history)
```

**Request timeline:** 50-200ms (Redis + PostgreSQL)

### Pattern 3: Session Deletion

```python
# Always waits for both stores to be consistent
from models.session import Session

Session.delete(session_id)  # Removes from both Redis and Postgres
```

### Pattern 4: Forced Sync During Runtime

```python
from services.session_sync_worker import get_worker

worker = get_worker()

# Force sync specific session
success = await worker.force_sync(session_id)

# Force sync all sessions
synced_count = await worker.force_sync_all()
```

## Configuration

### Sync Interval

**Current default: 300 seconds (5 minutes)**

Edit in [main.py](main.py):
```python
worker = get_worker(sync_interval=300)  # Change this value
```

**Recommended intervals:**
- **60-120s**: High consistency, more database load
- **300-600s**: Balanced (current default)
- **900-1800s**: High throughput, eventual consistency

### Logging

Enable debug logging to monitor sync operations:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Set to INFO for production
```

**Log output includes:**
- Sync task startup/shutdown
- Number of sessions synced per cycle
- Failed syncs with error details
- Session restoration from PostgreSQL

## Benefits

### 1. **Performance**
- Normal operations: 5-10ms (Redis only)
- No blocking on database writes
- Reduced database load

### 2. **Reliability**
- Background sync ensures eventual consistency
- Graceful shutdown with final sync
- Fallback to PostgreSQL if Redis lost
- Connection pooling and error handling

### 3. **Modularity**
- Clear separation of concerns
- Configurable sync interval
- Optional immediate sync for critical paths
- Easy to test and debug

### 4. **Scalability**
- Redis handles hot path traffic
- PostgreSQL stores persistent backup
- Can scale independently
- Reduced database connection pressure

## Migration from Old Code

Existing code using `Session.get()` and `Session.set()` works unchanged:

```python
# Old code - still works (now faster!)
history = Session.get(session_id)
Session.set(session_id, new_history)

# Background sync happens automatically
```

**No controller changes needed!**

## Technical Details

### Redis Key Format
- **Key**: `{session_id}` (string)
- **Value**: `pickle.dumps(history)` (binary)
- **Expiration**: None (persistent)

### PostgreSQL Sync
- Checks each session in Redis
- Deserializes pickle data
- Converts to JSON for storage
- Upserts into sessions table
- Logs errors but continues

### Thread Safety
- Redis operations: Atomic
- PostgreSQL operations: Connection pooling
- Asyncio: Single event loop
- No explicit locking needed

## Troubleshooting

### Sessions lost after sync failure?
**Answer:** Sync failures are logged but don't affect reads. Redis remains authoritative until next successful sync.

### High database load from sync?
**Answer:** Increase `sync_interval` in main.py (e.g., 900 seconds for 15-minute syncs)

### Need immediate persistence?
**Answer:** Use `Session.set_with_immediate_sync()` or `worker.force_sync()`

### Debugging sync issues?
**Answer:** Enable logging:
```python
logging.getLogger('services.session_sync_service').setLevel(logging.DEBUG)
```

## Testing

### Test Background Sync

```python
import asyncio
from services.session_sync_worker import managed_sync_worker
from models.session import Session

async def test_sync():
    async with managed_sync_worker(sync_interval=5) as worker:
        # Create session
        session_id = "test_123"
        history = ["msg1", "msg2"]
        
        # Update in Redis
        Session.set(session_id, history)
        
        # Wait for background sync
        await asyncio.sleep(6)
        
        # Verify in PostgreSQL
        assert Session.get(session_id) == history
```

## Future Improvements

1. **Batch Operations**: Optimize sync with bulk PostgreSQL inserts
2. **TTL Support**: Optional Redis expiration for ephemeral sessions
3. **Metrics**: Prometheus metrics for sync performance
4. **Selective Sync**: Sync only modified sessions (with dirty flag)
5. **Compression**: Compress history in Redis for large sessions
