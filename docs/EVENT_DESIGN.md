# Event System Design

Design considerations for event-driven architecture in HEAL pattern fix workflows.

## Requirements

- **Thread-safe**: Multiple pattern workers may run concurrently
- **Structured events**: Type-safe event objects with validation
- **Low CVE risk**: Prefer stdlib or well-audited libraries
- **Simple**: Avoid unnecessary complexity for monitoring/progress use cases

## Recommended Approach: stdlib Queue + dataclasses

**Why:**
- Zero external dependencies
- Zero CVEs (part of Python stdlib)
- Thread-safe by default
- Simple structured events with type hints
- No async complexity needed for subprocess monitoring

**Example:**

```python
from dataclasses import dataclass
from queue import Queue
from typing import Dict, Optional

@dataclass
class PhaseCompleteEvent:
    """Event emitted when a pattern fix phase completes."""
    pattern_id: str
    phase: str  # "baseline", "optimization", "validation", etc.
    success: bool
    metrics: Dict[str, float]
    error: Optional[str] = None

@dataclass
class ProgressEvent:
    """Event emitted during long-running operations."""
    pattern_id: str
    operation: str  # "evaluation", "optimization_iteration", etc.
    current: int
    total: int
    elapsed_seconds: float

# Create thread-safe event queue
progress_queue = Queue()

# Producer (pattern fix thread)
progress_queue.put(PhaseCompleteEvent(
    pattern_id="AUTHENTICATION_SECURITY",
    phase="baseline",
    success=True,
    metrics={"answer_correctness": 0.92, "faithfulness": 0.85}
))

progress_queue.put(ProgressEvent(
    pattern_id="AUTHENTICATION_SECURITY",
    operation="evaluation",
    current=3,
    total=5,
    elapsed_seconds=180.5
))

# Consumer (monitoring/UI thread)
while True:
    event = progress_queue.get()
    
    if isinstance(event, PhaseCompleteEvent):
        print(f"{event.pattern_id} - {event.phase}: {'✅' if event.success else '❌'}")
        for metric, value in event.metrics.items():
            print(f"  {metric}: {value:.2f}")
    
    elif isinstance(event, ProgressEvent):
        pct = (event.current / event.total) * 100
        print(f"{event.pattern_id} - {event.operation}: {pct:.0f}% ({event.current}/{event.total})")
```

## Alternative Options

### Option 1: asyncio (stdlib, zero CVEs)

**When to use:**
- Already doing async I/O (network, database)
- Need to coordinate multiple async operations
- Want structured concurrency

**Pros:**
- Part of Python core since 3.4
- No separate CVEs (would be Python CVEs)
- Most actively maintained async framework

**Cons:**
- Overkill for simple subprocess monitoring
- Mixing threads + asyncio adds complexity
- Steeper learning curve

**Example:**

```python
import asyncio
from dataclasses import dataclass

@dataclass
class Event:
    type: str
    pattern_id: str
    data: dict

async def event_loop(queue: asyncio.Queue):
    while True:
        event = await queue.get()
        await handle_event(event)

# For threading integration:
# asyncio.run_coroutine_threadsafe(coro, loop)
```

### Option 2: Trio (zero CVEs, security-focused)

**When to use:**
- Want better async ergonomics than asyncio
- Security is paramount (structured concurrency prevents bugs)
- Writing library code that others will use

**Pros:**
- Zero CVEs as of 2026-04-15
- Security-focused design from day one
- Structured concurrency (harder to write bugs)
- Small, well-audited codebase

**Cons:**
- External dependency
- Smaller ecosystem than asyncio
- Not needed for simple subprocess monitoring

**Example:**

```python
import trio
from dataclasses import dataclass

@dataclass
class Event:
    pattern_id: str
    phase: str

async def worker(send_channel):
    async with send_channel:
        await send_channel.send(Event("AUTH", "baseline"))

async def consumer(receive_channel):
    async with receive_channel:
        async for event in receive_channel:
            print(f"Got: {event.pattern_id}")

async def main():
    async with trio.open_nursery() as nursery:
        send_channel, receive_channel = trio.open_memory_channel(100)
        nursery.start_soon(worker, send_channel)
        nursery.start_soon(consumer, receive_channel)

trio.run(main)
```

### Option 3: blinker (1 low-severity CVE in 2023, patched)

**When to use:**
- Need signal/slot (pub/sub) pattern
- Multiple subscribers to same event
- Flask-style event dispatching

**Pros:**
- Thread-safe
- Used by Flask (battle-tested)
- Simple signal/slot pattern
- Weak references prevent memory leaks

**Cons:**
- External dependency
- Had CVE-2023-40590 (DOS via cyclic references, fixed in 1.6.3)
- More complex than needed for simple monitoring

**Example:**

```python
from blinker import signal
from dataclasses import dataclass

@dataclass
class PatternEvent:
    pattern_id: str
    phase: str
    success: bool

pattern_complete = signal('pattern-complete')

@pattern_complete.connect
def on_complete(sender, **kwargs):
    event = kwargs['event']
    print(f"Pattern {event.pattern_id} {event.phase}: {event.success}")

# Emit event
pattern_complete.send('system', event=PatternEvent("AUTH", "baseline", True))
```

## Mixing Threads + Asyncio (if needed)

If you need to coordinate between thread-based workers and async event handlers:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from dataclasses import dataclass

@dataclass
class Event:
    pattern_id: str
    data: dict

# Thread-safe queue for cross-thread communication
thread_events = Queue()

# Asyncio event handler
async def async_event_handler():
    while True:
        # Poll thread queue (non-blocking)
        if not thread_events.empty():
            event = thread_events.get()
            await process_async(event)
        await asyncio.sleep(0.1)

# Worker threads
def pattern_worker(pattern_id):
    # Do work...
    thread_events.put(Event(pattern_id, {"status": "done"}))

# Main
async def main():
    # Start thread workers
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.submit(pattern_worker, "AUTH")
        
        # Run async event handler
        await async_event_handler()

asyncio.run(main())
```

## Libraries to Avoid

**eventlet / gevent:**
- Multiple SSL/TLS CVEs over the years
- Monkey-patching stdlib causes security issues
- Hard to reason about in concurrent scenarios

**Twisted:**
- Mature but 15+ CVEs historically (though actively patched)
- Heavy framework for simple use cases
- Better alternatives exist now

## Decision Matrix

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Subprocess progress monitoring | `queue.Queue` + dataclasses | Simple, stdlib, thread-safe |
| Multiple concurrent I/O operations | `asyncio` | Stdlib, well-supported |
| Security-critical async work | `trio` | Zero CVEs, structured concurrency |
| Pub/sub with multiple subscribers | `blinker` (carefully) | Signal/slot pattern, but has CVE history |
| Simple inter-thread communication | `queue.Queue` | Simplest, safest option |

## Recommendation for HEAL

For the pattern fix workflow monitoring use case:

**Use `queue.Queue` + `dataclasses`**

```python
from dataclasses import dataclass
from queue import Queue
from typing import Dict, List, Optional

@dataclass
class PatternFixEvent:
    """Base class for all pattern fix events."""
    pattern_id: str
    timestamp: float

@dataclass
class PhaseStartEvent(PatternFixEvent):
    """Emitted when a phase starts."""
    phase: str  # "baseline", "optimization", "validation", "stability", "cla"

@dataclass
class PhaseCompleteEvent(PatternFixEvent):
    """Emitted when a phase completes."""
    phase: str
    success: bool
    duration_seconds: float
    metrics: Dict[str, float]
    reason: Optional[str] = None

@dataclass
class IterationEvent(PatternFixEvent):
    """Emitted during optimization iterations."""
    iteration: int
    max_iterations: int
    metrics: Dict[str, float]
    improved: bool

@dataclass
class EvaluationProgressEvent(PatternFixEvent):
    """Emitted during long-running evaluations."""
    run_number: int
    total_runs: int
    elapsed_seconds: float

# Global event queue for monitoring
progress_events = Queue()

# Pattern worker emits events
progress_events.put(PhaseStartEvent("AUTH", time.time(), "baseline"))
progress_events.put(EvaluationProgressEvent("AUTH", time.time(), 1, 5, 120.5))
progress_events.put(PhaseCompleteEvent(
    "AUTH", time.time(), "baseline", True, 600.0,
    {"answer_correctness": 0.92, "faithfulness": 0.85}
))

# Monitoring thread consumes events
def monitor_progress():
    while True:
        event = progress_events.get()
        
        if isinstance(event, PhaseStartEvent):
            print(f"🔄 {event.pattern_id} starting {event.phase}")
        
        elif isinstance(event, PhaseCompleteEvent):
            emoji = "✅" if event.success else "❌"
            print(f"{emoji} {event.pattern_id} {event.phase} complete")
            print(f"   Duration: {event.duration_seconds/60:.1f} min")
            for k, v in event.metrics.items():
                print(f"   {k}: {v:.2f}")
        
        elif isinstance(event, EvaluationProgressEvent):
            pct = (event.run_number / event.total_runs) * 100
            print(f"   Run {event.run_number}/{event.total_runs} ({pct:.0f}%)")
```

**Why this works:**
- Thread-safe communication between pattern workers and monitoring
- Structured, type-safe events
- Zero external dependencies
- Zero CVE risk
- Simple to understand and maintain
- Easy to extend with new event types
