# HEAL Library API Design

Design for refactoring HEAL from disparate scripts into a reusable library API.

## Goals

1. **Reusable across projects**: Import HEAL as a library, not run scripts
2. **Event-driven**: Observable progress, pluggable handlers
3. **Modular**: Use only what you need (diagnostics, pattern fixing, etc.)
4. **Type-safe**: Full type hints, Pydantic models
5. **Testable**: Mock-friendly, dependency injection

## Current State (Problems)

```python
# Current: Run scripts, parse logs, hope for the best
subprocess.run(["python", "src/heal/runners/run_pattern_fix_poc.py", "PATTERN"])

# Current: Scattered functionality across scripts
# - run_pattern_fix_poc.py
# - run_all_pattern_fixes.sh
# - okp_mcp_agent.py (does too much)
```

## Target State (Library API)

```python
from heal import PatternFixer, DiagnosticEngine, EventBus
from heal.events import PhaseCompleteEvent

# Simple API
fixer = PatternFixer(
    pattern_id="AUTHENTICATION_SECURITY",
    config_path="config.yaml",
    event_bus=EventBus()
)

# Subscribe to events
@fixer.on(PhaseCompleteEvent)
def on_phase_complete(event):
    print(f"Phase {event.phase}: {event.success}")

# Run synchronously or async
result = fixer.run(max_iterations=10)

# Or run multiple patterns concurrently
from heal import BatchRunner

runner = BatchRunner(patterns_dir="config/patterns/")
results = runner.run_all(max_workers=4)
```

## Architecture

### Core Components

```
heal/
├── core/
│   ├── __init__.py
│   ├── events.py          # Event system (Queue-based)
│   ├── models.py          # Pydantic data models
│   ├── config.py          # Configuration management
│   └── exceptions.py      # Custom exceptions
├── diagnostics/
│   ├── __init__.py
│   ├── engine.py          # DiagnosticEngine class
│   ├── metrics.py         # Metric calculation
│   └── evaluator.py       # Evaluation orchestration
├── fixing/
│   ├── __init__.py
│   ├── pattern_fixer.py   # PatternFixer class
│   ├── optimizer.py       # Retrieval optimization
│   └── validator.py       # Answer validation
├── agents/
│   ├── __init__.py
│   ├── llm_advisor.py     # LLM-powered suggestions
│   ├── solr_expert.py     # Solr diagnostics
│   └── linux_expert.py    # Linux MCP integration
├── runners/
│   ├── __init__.py
│   ├── batch.py           # BatchRunner for multiple patterns
│   └── cli.py             # CLI entry points (thin wrappers)
└── utils/
    ├── __init__.py
    ├── git.py             # Git operations
    └── solr.py            # Solr helpers
```

## API Design

### 1. Event System (Building on EVENT_DESIGN.md)

```python
# heal/core/events.py
from dataclasses import dataclass
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Type
import time

@dataclass
class Event:
    """Base event class."""
    pattern_id: str
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

@dataclass
class PhaseStartEvent(Event):
    phase: str

@dataclass
class PhaseCompleteEvent(Event):
    phase: str
    success: bool
    duration_seconds: float
    metrics: Dict[str, float]
    reason: Optional[str] = None

@dataclass
class IterationEvent(Event):
    iteration: int
    max_iterations: int
    metrics: Dict[str, float]

@dataclass
class ProgressEvent(Event):
    operation: str
    current: int
    total: int
    message: str

class EventBus:
    """Thread-safe event bus using stdlib Queue."""
    
    def __init__(self):
        self._queue = Queue()
        self._handlers: Dict[Type[Event], List[Callable]] = {}
    
    def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers."""
        self._queue.put(event)
        
        # Call synchronous handlers immediately
        event_type = type(event)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Handler error: {e}")
    
    def subscribe(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def get(self, block=True, timeout=None) -> Event:
        """Get next event from queue (for async consumers)."""
        return self._queue.get(block=block, timeout=timeout)
    
    def empty(self) -> bool:
        """Check if event queue is empty."""
        return self._queue.empty()
```

### 2. Configuration Management

```python
# heal/core/config.py
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

class HealConfig(BaseModel):
    """HEAL configuration."""
    
    # Repository paths
    eval_root: Path
    okp_mcp_root: Path
    lscore_deploy_root: Path
    
    # Pattern fix settings
    max_iterations: int = 10
    answer_threshold: float = 0.90
    stability_runs: int = 5
    
    # LLM settings
    enable_llm_advisor: bool = True
    llm_model: str = "claude-sonnet-4-6"
    
    # Git settings
    auto_create_branch: bool = True
    auto_cleanup_branch: bool = True
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def from_yaml(cls, path: Path) -> 'HealConfig':
        """Load config from YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> 'HealConfig':
        """Load config from environment variables."""
        import os
        return cls(
            eval_root=Path(os.getenv('HEAL_EVAL_ROOT', '.')),
            okp_mcp_root=Path(os.getenv('HEAL_OKP_MCP_ROOT', '../okp-mcp')),
            lscore_deploy_root=Path(os.getenv('HEAL_LSCORE_DEPLOY_ROOT', '../lscore-deploy')),
        )
```

### 3. Core Models

```python
# heal/core/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

class DiagnosticResult(BaseModel):
    """Result from diagnostic evaluation."""
    ticket_id: str
    answer_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    url_f1: Optional[float] = None
    context_relevance: Optional[float] = None
    context_precision: Optional[float] = None
    
    is_passing: bool = False
    is_retrieval_problem: bool = False
    is_answer_problem: bool = False
    
    high_variance_metrics: List[str] = []
    num_runs: int = 1

class PhaseResult(BaseModel):
    """Result from a fix loop phase."""
    phase_name: str
    success: bool
    iterations: int = 0
    duration_seconds: float = 0.0
    metrics: Dict[str, float] = {}
    reason: str = ""

class PatternFixResult(BaseModel):
    """Complete pattern fix result."""
    pattern_id: str
    success: bool
    duration_seconds: float
    
    baseline: Optional[PhaseResult] = None
    optimization: Optional[PhaseResult] = None
    validation: Optional[PhaseResult] = None
    stability: Optional[PhaseResult] = None
    
    branch_name: Optional[str] = None
    diagnostics_dir: Optional[Path] = None
    
    class Config:
        arbitrary_types_allowed = True
```

### 4. DiagnosticEngine API

```python
# heal/diagnostics/engine.py
from pathlib import Path
from typing import Optional
from heal.core.config import HealConfig
from heal.core.events import EventBus, ProgressEvent
from heal.core.models import DiagnosticResult

class DiagnosticEngine:
    """Diagnose ticket issues and classify problem types."""
    
    def __init__(self, config: HealConfig, event_bus: Optional[EventBus] = None):
        self.config = config
        self.event_bus = event_bus or EventBus()
    
    def diagnose(
        self,
        ticket_id: str,
        runs: int = 1,
        retrieval_only: bool = False
    ) -> DiagnosticResult:
        """
        Diagnose a ticket to identify issues.
        
        Args:
            ticket_id: Ticket to diagnose
            runs: Number of evaluation runs for stability
            retrieval_only: Skip LLM response generation (faster)
        
        Returns:
            DiagnosticResult with metrics and problem classification
        """
        self.event_bus.emit(ProgressEvent(
            pattern_id=ticket_id,
            operation="diagnosis",
            current=0,
            total=runs,
            message=f"Starting diagnosis with {runs} runs"
        ))
        
        # Run evaluation
        results = self._run_evaluation(ticket_id, runs, retrieval_only)
        
        # Calculate metrics
        diagnostic = self._analyze_results(results)
        
        self.event_bus.emit(ProgressEvent(
            pattern_id=ticket_id,
            operation="diagnosis",
            current=runs,
            total=runs,
            message="Diagnosis complete"
        ))
        
        return diagnostic
    
    def _run_evaluation(self, ticket_id: str, runs: int, retrieval_only: bool):
        """Run lightspeed-eval."""
        # Implementation...
        pass
    
    def _analyze_results(self, results) -> DiagnosticResult:
        """Analyze results and classify problem."""
        # Implementation...
        pass
```

### 5. PatternFixer API

```python
# heal/fixing/pattern_fixer.py
from pathlib import Path
from typing import Callable, Optional, Type
from heal.core.config import HealConfig
from heal.core.events import Event, EventBus, PhaseCompleteEvent
from heal.core.models import PatternFixResult
from heal.diagnostics.engine import DiagnosticEngine

class PatternFixer:
    """Fix a pattern by optimizing retrieval and validating answers."""
    
    def __init__(
        self,
        pattern_id: str,
        config: HealConfig,
        event_bus: Optional[EventBus] = None
    ):
        self.pattern_id = pattern_id
        self.config = config
        self.event_bus = event_bus or EventBus()
        
        # Initialize components
        self.diagnostic = DiagnosticEngine(config, self.event_bus)
    
    def run(
        self,
        max_iterations: Optional[int] = None,
        answer_threshold: Optional[float] = None,
        stability_runs: Optional[int] = None
    ) -> PatternFixResult:
        """
        Run complete fix loop.
        
        Args:
            max_iterations: Override config max iterations
            answer_threshold: Override config answer threshold
            stability_runs: Override config stability runs
        
        Returns:
            PatternFixResult with complete status
        """
        # Use config defaults if not provided
        max_iterations = max_iterations or self.config.max_iterations
        answer_threshold = answer_threshold or self.config.answer_threshold
        stability_runs = stability_runs or self.config.stability_runs
        
        result = PatternFixResult(
            pattern_id=self.pattern_id,
            success=False,
            duration_seconds=0.0
        )
        
        # Run phases...
        result.baseline = self._run_baseline(stability_runs)
        result.optimization = self._run_optimization(max_iterations)
        result.validation = self._run_validation(answer_threshold, stability_runs)
        
        return result
    
    def on(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """Subscribe to events (convenience method)."""
        self.event_bus.subscribe(event_type, handler)
    
    def _run_baseline(self, runs: int):
        """Run baseline evaluation."""
        # Implementation...
        pass
    
    def _run_optimization(self, max_iterations: int):
        """Run retrieval optimization."""
        # Implementation...
        pass
    
    def _run_validation(self, threshold: float, runs: int):
        """Run answer validation."""
        # Implementation...
        pass
```

### 6. BatchRunner API

```python
# heal/runners/batch.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional
from heal.core.config import HealConfig
from heal.core.events import EventBus, PhaseCompleteEvent
from heal.core.models import PatternFixResult
from heal.fixing.pattern_fixer import PatternFixer

class BatchRunner:
    """Run pattern fixes in parallel."""
    
    def __init__(
        self,
        patterns_dir: Path,
        config: HealConfig,
        event_bus: Optional[EventBus] = None,
        skip_patterns: Optional[List[str]] = None
    ):
        self.patterns_dir = patterns_dir
        self.config = config
        self.event_bus = event_bus or EventBus()
        self.skip_patterns = skip_patterns or [
            "UNGROUPED",
            "CONTAINER_UNSUPPORTED_CONFIG"
        ]
    
    def run_all(
        self,
        max_workers: int = 1,
        max_iterations: Optional[int] = None,
        answer_threshold: Optional[float] = None
    ) -> Dict[str, PatternFixResult]:
        """
        Run all patterns in parallel.
        
        Args:
            max_workers: Number of parallel workers (default: 1 = sequential)
            max_iterations: Override config max iterations
            answer_threshold: Override config answer threshold
        
        Returns:
            Dict mapping pattern_id to PatternFixResult
        """
        # Find all patterns
        patterns = self._discover_patterns()
        
        results = {}
        
        if max_workers == 1:
            # Sequential execution
            for pattern_id in patterns:
                results[pattern_id] = self._run_pattern(
                    pattern_id, max_iterations, answer_threshold
                )
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        self._run_pattern, pattern_id, max_iterations, answer_threshold
                    ): pattern_id
                    for pattern_id in patterns
                }
                
                for future in as_completed(futures):
                    pattern_id = futures[future]
                    try:
                        results[pattern_id] = future.result()
                    except Exception as e:
                        print(f"Pattern {pattern_id} failed: {e}")
                        results[pattern_id] = PatternFixResult(
                            pattern_id=pattern_id,
                            success=False,
                            duration_seconds=0.0
                        )
        
        return results
    
    def _discover_patterns(self) -> List[str]:
        """Find all pattern files."""
        patterns = []
        for path in self.patterns_dir.glob("*.yaml"):
            pattern_id = path.stem
            
            # Skip patterns
            if pattern_id.endswith("_SME_REVIEW"):
                continue
            if pattern_id in self.skip_patterns:
                continue
            
            patterns.append(pattern_id)
        
        return sorted(patterns)
    
    def _run_pattern(
        self,
        pattern_id: str,
        max_iterations: Optional[int],
        answer_threshold: Optional[float]
    ) -> PatternFixResult:
        """Run a single pattern."""
        fixer = PatternFixer(pattern_id, self.config, self.event_bus)
        return fixer.run(max_iterations, answer_threshold)
```

## Usage Examples

### Example 1: Simple Pattern Fix

```python
from heal import PatternFixer, HealConfig
from heal.events import PhaseCompleteEvent

# Load config
config = HealConfig.from_yaml("config.yaml")

# Create fixer
fixer = PatternFixer(
    pattern_id="AUTHENTICATION_SECURITY",
    config=config
)

# Subscribe to events
@fixer.on(PhaseCompleteEvent)
def log_phase(event):
    print(f"{event.phase}: {'✅' if event.success else '❌'}")

# Run
result = fixer.run()
print(f"Success: {result.success}")
```

### Example 2: Batch Processing with Progress Monitoring

```python
from heal import BatchRunner, HealConfig, EventBus
from heal.events import PhaseCompleteEvent, ProgressEvent
from pathlib import Path

# Shared event bus for all patterns
event_bus = EventBus()

# Monitor progress in background thread
import threading

def monitor_progress():
    while True:
        event = event_bus.get()
        
        if isinstance(event, ProgressEvent):
            print(f"[{event.pattern_id}] {event.message}")
        
        elif isinstance(event, PhaseCompleteEvent):
            emoji = "✅" if event.success else "❌"
            print(f"[{event.pattern_id}] {emoji} {event.phase} ({event.duration_seconds:.1f}s)")

monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
monitor_thread.start()

# Run batch
config = HealConfig.from_yaml("config.yaml")
runner = BatchRunner(
    patterns_dir=Path("config/patterns/"),
    config=config,
    event_bus=event_bus
)

results = runner.run_all(max_workers=4)

# Summary
successes = sum(1 for r in results.values() if r.success)
print(f"Results: {successes}/{len(results)} patterns succeeded")
```

### Example 3: Integration with Other Projects

```python
# In another project (e.g., web UI, CLI tool, etc.)
from heal import DiagnosticEngine, HealConfig
from heal.events import EventBus, ProgressEvent

# Initialize
config = HealConfig.from_env()  # Load from environment
event_bus = EventBus()
engine = DiagnosticEngine(config, event_bus)

# Real-time progress via websocket
async def stream_progress(websocket):
    while True:
        event = event_bus.get(timeout=0.1)
        if isinstance(event, ProgressEvent):
            await websocket.send_json({
                "pattern": event.pattern_id,
                "progress": event.current / event.total,
                "message": event.message
            })

# Diagnose ticket
result = engine.diagnose("RSPEED-2482", runs=5)

# Use result
if result.is_retrieval_problem:
    print("Need to fix Solr boost queries")
elif result.is_answer_problem:
    print("Need to fix system prompt")
```

### Example 4: Custom Event Handlers

```python
from heal import PatternFixer, HealConfig
from heal.events import IterationEvent, PhaseCompleteEvent
import json

config = HealConfig.from_yaml("config.yaml")
fixer = PatternFixer("AUTH_PATTERN", config)

# Log to file
log_file = open("fix.log", "w")

@fixer.on(IterationEvent)
def log_iteration(event):
    log_file.write(json.dumps({
        "iteration": event.iteration,
        "metrics": event.metrics
    }) + "\n")
    log_file.flush()

@fixer.on(PhaseCompleteEvent)
def notify_slack(event):
    if event.phase == "validation" and event.success:
        # Send Slack notification
        send_slack_message(f"Pattern {event.pattern_id} fixed! ✅")

result = fixer.run()
log_file.close()
```

## Migration Path

### Phase 1: Extract Core (Week 1)

1. Create library structure under `src/heal/`
2. Move models to `heal/core/models.py`
3. Implement EventBus in `heal/core/events.py`
4. Extract config to `heal/core/config.py`

### Phase 2: Refactor Diagnostics (Week 2)

1. Create `DiagnosticEngine` class
2. Extract evaluation logic from `okp_mcp_agent.py`
3. Add event emission
4. Write tests

### Phase 3: Refactor Pattern Fixing (Week 3)

1. Create `PatternFixer` class
2. Extract optimization logic
3. Extract validation logic
4. Add event emission
5. Write tests

### Phase 4: CLI Compatibility (Week 4)

1. Keep existing CLI scripts as thin wrappers
2. Implement backward compatibility
3. Update documentation

### Phase 5: BatchRunner (Week 5)

1. Implement `BatchRunner`
2. Add parallel execution
3. Migrate `run_all_pattern_fixes.sh` logic

## Testing Strategy

```python
# tests/test_pattern_fixer.py
from heal import PatternFixer, HealConfig, EventBus
from heal.events import PhaseCompleteEvent
from pathlib import Path
import pytest

@pytest.fixture
def config(tmp_path):
    return HealConfig(
        eval_root=tmp_path / "eval",
        okp_mcp_root=tmp_path / "okp-mcp",
        lscore_deploy_root=tmp_path / "lscore-deploy"
    )

@pytest.fixture
def event_bus():
    return EventBus()

def test_pattern_fixer_emits_events(config, event_bus):
    """Test that PatternFixer emits events."""
    events = []
    
    def capture_event(event):
        events.append(event)
    
    event_bus.subscribe(PhaseCompleteEvent, capture_event)
    
    fixer = PatternFixer("TEST_PATTERN", config, event_bus)
    # ... run with mocked diagnostics
    
    assert len(events) > 0
    assert any(isinstance(e, PhaseCompleteEvent) for e in events)

def test_diagnostic_engine_mock():
    """Test DiagnosticEngine with mocked evaluation."""
    # Use dependency injection to mock evaluation
    # ...
```

## Benefits

1. **Reusable**: Import HEAL in any Python project
2. **Observable**: Event system for progress monitoring
3. **Testable**: Dependency injection, mock-friendly
4. **Type-safe**: Full Pydantic models, type hints
5. **Modular**: Use only what you need
6. **Maintainable**: Clear separation of concerns
7. **Extensible**: Easy to add new event types, handlers

## Package Distribution

```toml
# pyproject.toml
[project]
name = "heal"
version = "0.1.0"
description = "Heuristic Engine for Autonomous Labor - RAG diagnostics and fixing"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
llm = ["claude-agent-sdk>=0.1"]
solr = ["requests>=2.31"]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]

[project.scripts]
heal = "heal.runners.cli:main"
```

Installation:
```bash
# Install core
pip install heal

# Install with LLM support
pip install heal[llm]

# Install for development
pip install -e ".[dev]"
```

## Next Steps

1. Review this design with team
2. Create GitHub issues for each phase
3. Start with Phase 1 (extract core)
4. Maintain backward compatibility during migration
5. Update documentation as we go
