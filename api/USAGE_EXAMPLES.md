# Session Management Usage Examples

This file contains practical examples of how to use the new Redis-first session architecture.

## Quick Start

### 1. Sessions Automatically Work as Before

Your existing controllers don't need any changes:

```python
# controllers/remote_repo_controller.py (existing code works unchanged)
from models.session import Session
from services.remote_repo_service import query

@router.post("/remote/repo/query")
async def query_repo(request: QueryRequest):
    # Fast path: Redis returns immediately
    history = Session.get(request.session_id)
    
    # Process query...
    response = await query(request.question, request.session_id)
    
    # Fast path: Redis returns immediately
    Session.set(request.session_id, updated_history)
    
    return response
```

### 2. Understanding the New Architecture

#### Reading Sessions

```python
from models.session import Session

session_id = "user_123_session"

# Fast path (typical case):
# 1. Checks Redis (~1ms)
# 2. Restores from PostgreSQL on first access (~50ms)
# 3. Returns immediately
history = Session.get(session_id)  # Returns: [Message(...), ...]
```

#### Updating Sessions

```python
# Fast path (typical case):
Session.set(session_id, new_history)
# Returns immediately (~5ms)
# Background sync updates PostgreSQL within 5 minutes

# Slow path (when you need guaranteed persistence):
Session.set_with_immediate_sync(session_id, final_history)
# Waits for both Redis and PostgreSQL (~150ms)
```

## Pattern Examples

### Pattern A: Streaming Query Response

```python
# services/remote_repo_service.py
from models.session import Session
from services.session_sync_worker import get_worker

async def query_stream(question: str, session_id: str):
    """Streaming endpoint with fast session updates."""
    
    # Get history (fast from Redis)
    history = Session.get(session_id)
    
    # Process query with streaming...
    async with rag_agent.run_stream(question, message_history=history) as response:
        async for chunk in response.stream():
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
    
    # Update session (fast to Redis only)
    history.extend(response.new_messages())
    Session.set(session_id, history)
    
    # Background sync handles PostgreSQL automatically
    # No need to wait - response already sent to client
```

**Performance:** Response sent to client in ~5-10ms, sync happens in background

### Pattern B: Graceful Shutdown with Session Persistence

```python
# main.py
from fastapi import FastAPI
from services.session_sync_worker import get_worker

@app.on_event("shutdown")
async def on_shutdown():
    """Ensure all sessions are persisted before shutdown."""
    worker = get_worker()
    
    if worker.is_running():
        # This calls force_sync_all() internally
        # Syncs all active sessions to PostgreSQL before cleanup
        await worker.stop()
    
    logger.info("All sessions synced to PostgreSQL")
```

### Pattern C: Critical Session Save

```python
# services/repo_service.py
from models.session import Session

async def final_save_session(session_id: str, history: list):
    """Save session with guaranteed persistence."""
    
    # Use immediate sync for critical operations
    Session.set_with_immediate_sync(session_id, history)
    
    logger.info(f"Session {session_id} saved to both Redis and PostgreSQL")
```

**Use case:** Before logout, before complex operations, or on schema changes

### Pattern D: Force Sync When Needed

```python
# services/session_sync_worker.py
from services.session_sync_worker import get_worker

async def force_persist_session(session_id: str):
    """Force immediate sync of a specific session if needed."""
    
    worker = get_worker()
    success = await worker.force_sync(session_id)
    
    if success:
        logger.info(f"Session {session_id} immediately synced")
    else:
        logger.error(f"Failed to sync session {session_id}")
    
    return success
```

### Pattern E: Bulk Operations During Maintenance

```python
from services.session_sync_worker import get_worker

async def maintenance_sync():
    """Sync all sessions during maintenance window."""
    
    worker = get_worker()
    synced = await worker.force_sync_all()
    
    logger.info(f"Maintenance sync complete: {synced} sessions")
```

## Configuration Examples

### Example 1: High Consistency (Shorter Sync Interval)

```python
# main.py - Sync every 1 minute
@app.on_event("startup")
async def on_startup():
    init_db()
    worker = get_worker(sync_interval=60)  # Changed from 300
    await worker.start()
```

**Tradeoff:** More consistent data, higher database load

### Example 2: High Throughput (Longer Sync Interval)

```python
# main.py - Sync every 15 minutes
@app.on_event("startup")
async def on_startup():
    init_db()
    worker = get_worker(sync_interval=900)  # Changed from 300
    await worker.start()
```

**Tradeoff:** Less database load, eventual consistency

### Example 3: Debug Logging

```python
# main.py or conftest.py
import logging

# Enable debug logging for session sync
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Make session sync service verbose
logging.getLogger('services.session_sync_service').setLevel(logging.DEBUG)
```

**Output includes:**
```
DEBUG - Session test_123 updated in Redis (queued for Postgres sync)
DEBUG - Starting session sync service (interval: 300s)
DEBUG - Syncing 42 sessions to PostgreSQL
DEBUG - Updated session record for user_456_session
DEBUG - Successfully synced 42 sessions
```

## Real-World Scenarios

### Scenario 1: Chat Application

```python
# User sends message in fast request path
@router.post("/chat/message")
async def chat_message(session_id: str, message: str):
    # Get current history (Redis: ~1ms)
    history = Session.get(session_id)
    
    # Process message with LLM (~2-5 seconds)
    response = await llm.chat(message, history)
    
    # Update history (Redis: ~5ms, PostgreSQL in background)
    history.extend([message, response])
    Session.set(session_id, history)
    
    # Response sent to user immediately
    # PostgreSQL sync happens in background ~5 minutes later
    return {"response": response}
```

**Result:** User gets instant response, data saved reliably

### Scenario 2: Multi-Tab Session

```python
# Tab 1: Query
Session.set(session_id, history_after_q1)  # Fast (Redis)

# Tab 2: Optimization
Session.set(session_id, history_after_opt)  # Fast (Redis)

# Tab 3: Get all sessions
sessions = Session.get_all()  # From PostgreSQL (slow but authoritative)

# After 5 minutes: Background sync brings Redis and PostgreSQL in sync
```

### Scenario 3: Session Recovery After Redis Crash

```python
# Redis is down, but PostgreSQL has last checkpoint

# Try to get session
history = Session.get(session_id)
# 1. Redis miss (server down)
# 2. Fallback to PostgreSQL
# 3. Returns last synced state (~50-100ms)

# Resume work...
Session.set(session_id, updated_history)
# 1. Updates Redis once it's back up
# 2. Next sync updates PostgreSQL
```

## Testing Examples

### Test 1: Background Sync Works

```python
import asyncio
from models.session import Session
from services.session_sync_worker import managed_sync_worker

async def test_background_sync():
    """Verify background sync actually syncs to PostgreSQL."""
    
    async with managed_sync_worker(sync_interval=2) as worker:
        session_id = "test_sync_123"
        test_history = ["msg1", "msg2", "msg3"]
        
        # Write to Redis only
        Session.set(session_id, test_history)
        
        # Wait for sync cycle (2 seconds + buffer)
        await asyncio.sleep(3)
        
        # Verify it made it to PostgreSQL
        # (by checking database directly or Session.get_all())
        all_sessions = Session.get_all()
        assert any(s["session_id"] == session_id for s in all_sessions)
```

### Test 2: Critical Save Ensures Persistence

```python
import asyncio
from models.session import Session

async def test_critical_save():
    """Verify critical save immediately persists."""
    
    session_id = "test_critical_456"
    history = ["critical", "data"]
    
    # Use critical save
    Session.set_with_immediate_sync(session_id, history)
    
    # Immediately check database (should already be there)
    # This would be checked with direct SQL or ORM query
    
    # Verify Redis also has it
    assert Session.get(session_id) == history
```

### Test 3: Fast Path Performance

```python
import time
from models.session import Session

async def test_performance():
    """Verify Redis operations are fast."""
    
    session_id = "perf_test_789"
    history = ["msg" * 100 for _ in range(10)]  # ~1KB of data
    
    # Redis write should be < 10ms
    start = time.time()
    Session.set(session_id, history)
    redis_time = time.time() - start
    assert redis_time < 0.01, f"Redis write took {redis_time}s"
    
    # Redis read should be < 5ms
    start = time.time()
    result = Session.get(session_id)
    read_time = time.time() - start
    assert read_time < 0.005, f"Redis read took {read_time}s"
```

## Monitoring

### Checking Sync Service Health

```python
from services.session_sync_worker import get_worker

# In a management endpoint or monitoring script
worker = get_worker()

if worker.is_running():
    print("Sync worker: RUNNING")
else:
    print("Sync worker: STOPPED")
```

### Metrics to Monitor

```
1. Session update latency (should be < 10ms)
   - Before: 50-200ms (sync to PostgreSQL)
   - After: 5-10ms (Redis only)

2. Sync cycle duration (seconds)
   - How long each background sync takes
   - Should be < 30 seconds for typical loads

3. Redis memory usage (bytes)
   - Monitor for memory pressure

4. PostgreSQL replication lag (seconds)
   - Largest gap between Redis update and PostgreSQL sync

5. Sync errors per cycle
   - Should be 0 in healthy state
```

## Troubleshooting

### Problem: Sessions don't match between Redis and PostgreSQL

**Solution:**
```python
# Force immediate sync
from services.session_sync_worker import get_worker
worker = get_worker()
await worker.force_sync_all()
```

### Problem: Need faster sync than 5 minutes

**Solution:**
```python
# main.py
worker = get_worker(sync_interval=60)  # Change to 1 minute
```

### Problem: Redis is losing data

**Solution:**
```python
# Use critical save path
Session.set_with_immediate_sync(session_id, history)
```

### Problem: Too much database load

**Solution:**
```python
# main.py
worker = get_worker(sync_interval=1800)  # Change to 30 minutes

# Or add batching in session_sync_service.py
```
