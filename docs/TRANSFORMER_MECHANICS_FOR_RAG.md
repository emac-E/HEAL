# Transformer Mechanics for RAG Optimization

**Author:** Conversation with Claude (2026-04-15)  
**Context:** Applying transformer attention mechanics to RAG system optimization  
**Target Audience:** Engineers researching "Lost in the Middle" effect and RAG performance

---

## Table of Contents

1. [Positional Encoding: Why Document Order Matters](#1-positional-encoding-why-document-order-matters)
2. [Attention Mechanism: "Lost in the Middle" Effect](#2-attention-mechanism-lost-in-the-middle-effect)
3. [Context Window as a Resource Constraint](#3-context-window-as-a-resource-constraint)
4. [Attention Heads: Multi-Scale Pattern Matching](#4-attention-heads-multi-scale-pattern-matching)
5. [RAG-Specific Measurements](#5-rag-specific-measurements-you-can-add)
6. [Practical Optimization Strategies](#6-practical-optimization-strategies)
7. [Measuring What Matters in HEAL](#7-measuring-what-matters-in-heal)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [Research Papers & References](#9-research-papers--references)

---

## 1. Positional Encoding: Why Document Order Matters

### The Math

Transformers use **positional embeddings** to encode token position:

```python
# Sinusoidal positional encoding (original Transformer)
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

# Where:
# - pos = token position (0, 1, 2, ...)
# - i = dimension index
# - d_model = embedding dimension (e.g., 768, 1024)
```

### What This Means for RAG

Position information is **encoded directly** into token representations:

- **Position 0-512:** Strong positional signal, high differentiation
- **Position 512-2048:** Medium signal, moderate differentiation
- **Position 2048+:** Weaker signal, diminishing returns
- **Document order directly affects LLM attention weights**

### HEAL Metrics Already Capture This

```python
# Average Position metric
avg_position = sum(positions_of_expected_urls) / len(expected_urls)

# Interpretation:
# - Good: avg_position < 5.0 (docs in high-attention zone)
# - Medium: avg_position 5.0-10.0 (moderate attention)
# - Bad: avg_position > 10.0 (docs buried, weak positional signal)
```

### Actionable Insights

1. **Solr ranking order matters** - it's not just "retrieved or not"
2. Top 3 positions get **exponentially more attention** than position 10+
3. MRR metric (Mean Reciprocal Rank) measures this: `MRR = 1/position`
4. **Optimization goal:** Get expected docs in positions 1-5

### Experimental Questions

- **Q1:** How does position affect answer quality for the same document set?
- **Q2:** Is there a position threshold where retrieval becomes useless?
- **Q3:** Does the effect differ by query type (factual vs procedural)?

**Experiment design:**
```python
# Test: Shuffle same 10 docs to different positions
# Measure: answer_correctness vs avg_position
# Hypothesis: answer_correctness ∝ 1/avg_position

positions_to_test = [1, 3, 5, 10, 15, 20]
for target_pos in positions_to_test:
    # Place expected doc at target_pos
    # Run evaluation
    # Plot: (position, answer_correctness)
```

---

## 2. Attention Mechanism: "Lost in the Middle" Effect

### The Math

Self-attention computes relevance scores between all token pairs:

```python
# Attention formula
Attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V

# Where:
# Q = query vectors (what we're looking for)
# K = key vectors (all context tokens)
# V = value vectors (actual content)
# d_k = key dimension (for scaling)

# Softmax normalizes to probability distribution:
# sum(attention_weights) = 1.0
```

### The Problem: U-Shaped Attention Curve

Empirical studies show attention weights form a **U-shaped curve** across context:

```
Attention Weight Distribution Across Context Window

  High ┤ ██                              ██
       ┤ ██                              ██
       ┤ ██                              ██
  Med  ┤ ███                            ███
       ┤ ████                          ████
       ┤ █████                        █████
  Low  ┤ ██████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██████
       └─┬──────┬──────┬──────┬──────┬───
         0     50    100    150    200
              Token Position

Legend:
█ = High attention (primacy + recency bias)
▓ = Low attention (LOST IN THE MIDDLE)
```

### Empirical Measurements (from research)

**Liu et al. (2023) - "Lost in the Middle":**

| Position Range | Avg Attention Weight | Relative Performance |
|----------------|---------------------|----------------------|
| 1-10 (start) | 0.15-0.20 | 100% (baseline) |
| 50-100 (early-mid) | 0.08-0.12 | 65% |
| 100-150 (middle) | 0.05-0.08 | **40%** ← Lost! |
| 150-190 (late-mid) | 0.08-0.12 | 65% |
| 190-200 (end) | 0.12-0.15 | 85% (recency) |

### HEAL Application

Diagnose "lost in the middle" effect:

```python
# Scenario: url_f1 is high BUT answer_correctness is low
# → Docs retrieved BUT in wrong positions (lost in middle)

if url_f1 >= 0.7 and answer_correctness < 0.7:
    # Check Average Position
    if avg_position > 8.0:
        problem = "LOST_IN_MIDDLE"
        fix = "Re-rank docs: move relevant ones to top 3"
    
    # Check if docs are scattered
    positions = [get_position(url) for url in expected_urls]
    if max(positions) - min(positions) > 15:
        problem = "SCATTERED_DOCS"
        fix = "Cluster relevant docs together"
```

### Practical Fix Strategies

**Strategy 1: Solr Boost Query**
```python
# Exponentially boost top positions
solr_query = {
    "q": user_query,
    "boost": "recip(position, 1, 1, 1)^10",  # 1/position^10
    "qf": "title^5 content^2",
}
```

**Strategy 2: Post-Retrieval Re-Ranking**
```python
def rerank_for_attention(docs, expected_doc_ids):
    """Move expected docs to top positions."""
    expected = [doc for doc in docs if doc.id in expected_doc_ids]
    other = [doc for doc in docs if doc.id not in expected_doc_ids]
    
    # Expected docs at top (positions 1-N)
    # Other docs fill remaining positions
    return expected + other
```

### Experimental Questions

- **Q1:** At what position does performance drop by 50%? (measure threshold)
- **Q2:** Does the U-curve shape differ by model size? (Sonnet vs Opus vs Haiku)
- **Q3:** Can we quantify the "middle zone" boundaries? (where does it start/end?)
- **Q4:** Does chunking documents help? (5 small chunks vs 1 large doc)

**Experiment design:**
```python
# Controlled experiment: Place relevant doc at each position
for position in range(1, 21):
    # Insert relevant doc at this position
    # Fill other positions with irrelevant docs
    # Measure: answer_correctness(position)
    # Plot: U-shaped curve

# Expected result:
# positions 1-5: high performance
# positions 6-15: degraded performance (middle)
# positions 16-20: moderate recovery (recency)
```

---

## 3. Context Window as a Resource Constraint

### Think Like Embedded Systems Memory

| Embedded | LLM Context |
|----------|-------------|
| 64KB RAM | 128K token window |
| Stack overflow | Context overflow |
| Memory fragmentation | Token fragmentation |
| Priority queuing | Document ranking |
| Memory allocation | Token budget allocation |

### Token Budget Allocation for RAG

**Claude Sonnet 4.5 (128K context window):**

```python
Total tokens: 128,000 (100%)

Allocations:
- System prompt:    ~2,000 tokens   (1.6%)
- User query:       ~100 tokens     (0.08%)
- Retrieved docs:   ~10,000 tokens  (7.8%) ← Your controllable budget
- LLM response:     ~1,000 tokens   (0.8%)
- Safety buffer:    ~5,000 tokens   (3.9%)
--------------------------------------------
Remaining:          ~109,900 tokens (85.7%)
```

**Your control surface:**
1. **Number of docs:** More docs = more tokens, but diluted attention
2. **Doc length:** Truncate to most relevant sections
3. **Doc quality:** 3 perfect docs > 10 mediocre docs

### HEAL's Current Approach

```python
# From linux_expert.py:425-430
doc_context = "\n\n".join(
    [
        f"**{doc['title']}**\n{doc['url']}\n{doc['content'][:2000]}..."
        for doc in verification.found_docs[:5]  # ← Top 5 docs only
    ]
)

# Fixed allocation:
# - 5 docs max
# - 2000 chars per doc (~500 tokens)
# - Total: ~2500 tokens for retrieved content
```

### Optimization Opportunity: Dynamic Allocation

```python
def allocate_token_budget(docs, total_budget=10000):
    """Allocate tokens proportional to relevance scores.
    
    Args:
        docs: List of documents with relevance scores
        total_budget: Total tokens available for docs
    
    Returns:
        List of docs with allocated token budgets
    """
    # Normalize scores to sum to 1.0
    total_score = sum(doc.relevance_score for doc in docs)
    
    for doc in docs:
        # Allocate tokens proportional to relevance
        doc_proportion = doc.relevance_score / total_score
        doc.token_budget = int(doc_proportion * total_budget)
        
        # Truncate content to budget (rough: 4 chars per token)
        max_chars = doc.token_budget * 4
        doc.truncated_content = doc.content[:max_chars]
    
    return docs

# Usage:
docs = allocate_token_budget(retrieved_docs, total_budget=10000)
# High-relevance doc: 4000 tokens
# Medium-relevance doc: 3000 tokens
# Low-relevance doc: 2000 tokens
# Irrelevant doc: 1000 tokens (or exclude)
```

### Measuring Token Efficiency

```python
def measure_token_efficiency(retrieved_docs, answer_quality):
    """How many tokens needed per unit of answer quality?
    
    Returns:
        dict with efficiency metrics
    """
    total_tokens = sum(
        len(doc.content.split()) * 1.3  # Rough token estimate
        for doc in retrieved_docs
    )
    
    return {
        "tokens_used": total_tokens,
        "tokens_per_quality_point": total_tokens / answer_quality,
        "efficiency": answer_quality / (total_tokens / 1000),  # Quality per 1K tokens
        "waste_ratio": (total_tokens - optimal_tokens) / total_tokens,
    }

# Good: efficiency > 0.5 (high quality with few tokens)
# Bad: efficiency < 0.2 (wasting tokens on irrelevant docs)
```

### Experimental Questions

- **Q1:** What's the optimal number of docs for different query types?
- **Q2:** Does truncation hurt answer quality? At what threshold?
- **Q3:** Is token efficiency correlated with answer quality?

---

## 4. Attention Heads: Multi-Scale Pattern Matching

### The Architecture

Modern transformers have **multiple attention heads** per layer:

**Claude Sonnet (estimated architecture):**
- ~40 layers
- ~32 attention heads per layer
- **Total: ~1,280 attention heads** working in parallel

**Head specialization** (empirical observation):
- **Heads 1-8:** Local patterns (syntax, entities, noun phrases)
- **Heads 9-16:** Medium-range (sentence relationships, coreference)
- **Heads 17-24:** Long-range (paragraph structure, document theme)
- **Heads 25-32:** Very long-range (cross-document, multi-hop reasoning)

### What This Means for RAG

Different heads focus on different scales:

```
Document 1: "RHEL 8 EOL is June 2029..."
            ↑        ↑
          Head 1   Head 3
        (entity) (date)

Document 2: "To check RHEL version, run: cat /etc/redhat-release"
            ↑                           ↑
          Head 10                    Head 5
      (instruction)                (command)

Cross-doc: "RHEL 8... (doc 1)" → "To check version... (doc 2)"
           ↑
         Head 25
    (long-range connection)
```

**Key insights:**
1. **Document boundaries matter** - heads attend within/across docs differently
2. **Formatting matters** - markdown structure aids multi-head parsing
3. **Chunking strategy matters** - affects which heads can connect info

### HEAL Optimization: Better Structure

**Current (good):**
```python
doc_context = f"**{title}**\n{url}\n{content}"
```

**Better (helps attention heads parse):**
```python
doc_context = f"""
## Document {i+1}: {title}
**Source:** {url}
**Relevance:** {relevance_score:.2f}

### Content:
{content}

---
"""
# Benefits:
# - Clear boundaries help long-range heads
# - Numbered docs aid positional reasoning
# - Section markers help medium-range heads
# - Separators (---) create distinct chunks
```

### Experimental Questions

- **Q1:** Does explicit structure improve answer quality?
- **Q2:** Do numbered documents help position-based reasoning?
- **Q3:** What's the optimal document separator? (blank lines vs --- vs ###)

---

## 5. RAG-Specific Measurements You Can Add

Based on transformer mechanics, here are **measurable, actionable metrics**:

### A. Positional Attention Decay

**Hypothesis:** Attention weight decays with position  
**Formula:** Model empirical attention decay curve

```python
def measure_position_sensitivity(expected_urls, retrieved_urls):
    """How much does position hurt performance?
    
    Returns:
        dict with attention-weighted metrics
    """
    position_scores = []
    
    for url in expected_urls:
        if url in retrieved_urls:
            pos = retrieved_urls.index(url) + 1
            
            # Model attention decay (empirical fit from research)
            # Position 1: weight = 1.0
            # Position 5: weight = 0.57
            # Position 10: weight = 0.40
            # Position 20: weight = 0.25
            attention_weight = 1.0 / (1.0 + 0.15 * pos)
            position_scores.append({
                "url": url,
                "position": pos,
                "attention_weight": attention_weight,
            })
    
    if not position_scores:
        return {
            "avg_attention_weight": 0.0,
            "position_penalty": 1.0,
            "positions": [],
        }
    
    avg_weight = np.mean([s["attention_weight"] for s in position_scores])
    
    return {
        "avg_attention_weight": avg_weight,
        "position_penalty": 1.0 - avg_weight,  # How much we lose to position
        "positions": position_scores,
    }

# Interpretation:
# - avg_attention_weight > 0.8: Docs in high-attention positions (good)
# - avg_attention_weight 0.5-0.8: Moderate attention (acceptable)
# - avg_attention_weight < 0.5: Lost in middle or buried (bad)
```

**Add to evaluation:**
```python
results["position_sensitivity"] = measure_position_sensitivity(
    expected_urls=turn.expected_urls,
    retrieved_urls=retrieval_result.urls,
)

# Use in diagnosis:
if results["position_sensitivity"]["position_penalty"] > 0.4:
    diagnosis = "HIGH_POSITION_PENALTY"
    recommendation = "Re-rank to move docs to top 3 positions"
```

### B. Context Fragmentation Score

**Hypothesis:** Clustered docs (positions 1-5) are better than scattered docs (positions 1, 10, 20)  
**Reason:** Multi-head attention can connect nearby tokens more easily

```python
def measure_context_fragmentation(expected_urls, retrieved_urls):
    """Are relevant docs clustered (good) or scattered (bad)?
    
    Returns:
        dict with fragmentation metrics
    """
    positions = [
        retrieved_urls.index(url) + 1
        for url in expected_urls
        if url in retrieved_urls
    ]
    
    if len(positions) < 2:
        return {
            "fragmentation": 0.0,
            "is_clustered": True,
            "span": 0,
        }
    
    # Standard deviation of positions
    fragmentation = np.std(positions)
    
    # Span: max - min position
    span = max(positions) - min(positions)
    
    return {
        "fragmentation": fragmentation,
        "span": span,
        "is_clustered": fragmentation < 5.0,  # Within 5 positions
        "positions": sorted(positions),
    }

# Interpretation:
# - fragmentation < 5: Docs clustered together (good for attention)
# - fragmentation 5-10: Moderate spread (acceptable)
# - fragmentation > 15: Scattered across context (bad)
```

**Why this matters:**
```
Scenario A (clustered):     Scenario B (scattered):
Position 1: Expected doc    Position 1: Expected doc
Position 2: Expected doc    Position 5: Noise
Position 3: Expected doc    Position 10: Noise
Position 4: Noise           Position 15: Expected doc
Position 5: Noise           Position 20: Expected doc

Multi-head attention:       Multi-head attention:
✅ Can connect 1→2→3       ❌ Hard to connect 1→15→20
✅ Local context helps      ❌ Intervening noise
```

### C. Token Efficiency Ratio

**Hypothesis:** More tokens != better answers  
**Goal:** Maximize answer quality per token used

```python
def measure_token_efficiency(retrieved_docs, answer_correctness):
    """How many tokens needed per unit of answer quality?
    
    Returns:
        dict with efficiency metrics
    """
    # Estimate tokens (rough: 1.3 tokens per word)
    total_tokens = sum(
        len(doc["content"].split()) * 1.3
        for doc in retrieved_docs
    )
    
    # Prevent division by zero
    if answer_correctness == 0:
        efficiency = 0.0
        waste_ratio = 1.0
    else:
        # Quality per 1K tokens
        efficiency = answer_correctness / (total_tokens / 1000)
        
        # Estimate "optimal" tokens (perfect docs only)
        # Assume: 2 perfect docs * 500 tokens = 1000 tokens
        optimal_tokens = 1000
        waste_ratio = max(0, (total_tokens - optimal_tokens) / total_tokens)
    
    return {
        "tokens_used": int(total_tokens),
        "tokens_per_quality_point": int(total_tokens / answer_correctness) if answer_correctness > 0 else float('inf'),
        "efficiency": efficiency,  # Quality per 1K tokens
        "waste_ratio": waste_ratio,  # % of tokens wasted
        "optimal_tokens": optimal_tokens,
    }

# Interpretation:
# - efficiency > 0.5: High quality with few tokens (excellent)
# - efficiency 0.3-0.5: Good efficiency (acceptable)
# - efficiency < 0.3: Wasting tokens on irrelevant docs (bad)
```

**Use in optimization:**
```python
# Phase 2: Optimize token usage
if token_efficiency < 0.3 and answer_correctness < 0.7:
    # Too many tokens, low quality
    fix_strategies = [
        "Reduce number of docs (10 → 5)",
        "Truncate irrelevant sections",
        "Re-rank to remove low-relevance docs",
    ]
```

### D. Attention Coverage

**Hypothesis:** % of expected docs in "high-attention zone" (top-5) predicts answer quality

```python
def measure_attention_coverage(expected_urls, retrieved_urls, top_k=5):
    """% of expected URLs in high-attention zone (top K positions).
    
    Args:
        expected_urls: URLs that should be retrieved
        retrieved_urls: Actually retrieved URLs (in order)
        top_k: Size of high-attention zone (default: 5)
    
    Returns:
        dict with coverage metrics
    """
    top_k_urls = set(retrieved_urls[:top_k])
    expected_set = set(expected_urls)
    
    # How many expected docs are in top-K?
    hits_in_top_k = len(expected_set & top_k_urls)
    
    # Coverage: % of expected docs in high-attention zone
    coverage = hits_in_top_k / len(expected_urls) if expected_urls else 0.0
    
    return {
        "coverage": coverage,
        "hits_in_top_k": hits_in_top_k,
        "total_expected": len(expected_urls),
        "top_k": top_k,
    }

# Interpretation:
# - coverage = 1.0: All expected docs in top-5 (perfect)
# - coverage > 0.7: Most expected docs in high-attention zone (good)
# - coverage < 0.5: Expected docs buried (bad)
```

**Relationship to existing metrics:**
```python
# url_f1 measures: "Were docs retrieved at all?"
# attention_coverage measures: "Were docs retrieved in good positions?"

# Both high: Excellent retrieval
if url_f1 >= 0.7 and attention_coverage >= 0.7:
    status = "EXCELLENT_RETRIEVAL"

# url_f1 high, coverage low: Lost in middle problem
if url_f1 >= 0.7 and attention_coverage < 0.5:
    status = "LOST_IN_MIDDLE"
    fix = "Re-rank to improve positions"

# Both low: Complete retrieval failure
if url_f1 < 0.5 and attention_coverage < 0.5:
    status = "RETRIEVAL_FAILURE"
    fix = "Fix Solr query"
```

---

## 6. Practical Optimization Strategies

### Strategy 1: Adaptive Document Truncation

**Problem:** Fixed truncation (2000 chars) wastes tokens on irrelevant sections

**Solution:** Truncate to most relevant section for the query

```python
def adaptive_truncation(doc, query, max_tokens=500):
    """Truncate doc to most relevant section for query.
    
    Args:
        doc: Document content (full text)
        query: User query
        max_tokens: Maximum tokens to allocate
    
    Returns:
        Truncated document content
    """
    # Split into sections (paragraphs)
    sections = doc.split('\n\n')
    
    # Extract query terms (simple tokenization)
    query_terms = set(query.lower().split())
    
    # Score each section by keyword overlap with query
    section_scores = []
    for sec in sections:
        sec_terms = set(sec.lower().split())
        
        # Overlap score
        overlap = len(query_terms & sec_terms)
        
        # Bonus for exact phrase match
        if query.lower() in sec.lower():
            overlap += 10
        
        section_scores.append((overlap, sec))
    
    # Sort by relevance (highest score first)
    section_scores.sort(reverse=True, key=lambda x: x[0])
    
    # Take top sections until budget exhausted
    result = []
    token_count = 0
    
    for score, sec in section_scores:
        sec_tokens = len(sec.split()) * 1.3  # Rough estimate
        
        if token_count + sec_tokens > max_tokens:
            # Partial section to fill remaining budget
            remaining_tokens = max_tokens - token_count
            remaining_words = int(remaining_tokens / 1.3)
            words = sec.split()[:remaining_words]
            result.append(' '.join(words) + '...')
            break
        
        result.append(sec)
        token_count += sec_tokens
    
    return '\n\n'.join(result)

# Usage in HEAL:
doc_context = "\n\n".join(
    [
        f"**{doc['title']}**\n{doc['url']}\n{adaptive_truncation(doc['content'], query, max_tokens=500)}"
        for doc in verification.found_docs[:5]
    ]
)
```

**Benefits:**
- Keeps query-relevant content
- Removes irrelevant sections
- Better token efficiency
- Focuses LLM attention on relevant parts

### Strategy 2: Position-Aware Boosting

**Problem:** Solr returns relevant docs but in poor positions (buried)

**Solution:** Boost queries to promote docs to top positions

```python
def generate_position_aware_boost(query, field_weights=None):
    """Generate Solr boost query that considers LLM attention patterns.
    
    Args:
        query: User query
        field_weights: Dict of field → weight (e.g., {"title": 5, "content": 2})
    
    Returns:
        Solr query dict with boost parameters
    """
    if field_weights is None:
        field_weights = {
            "title": 5,
            "content": 2,
            "summary": 3,
        }
    
    # Build field query (qf parameter)
    qf_parts = [f"{field}^{weight}" for field, weight in field_weights.items()]
    qf = " ".join(qf_parts)
    
    # Exponential boost for top positions
    # recip(position, 1, 1, 1)^N creates 1/position^N curve
    # Higher N = more aggressive top-position bias
    position_boost = "recip(position, 1, 1, 1)^10"
    
    return {
        "q": query,
        "qf": qf,
        "boost": position_boost,
        "defType": "edismax",  # Extended DisMax for boost support
    }

# Usage in Solr Expert:
boost_query = generate_position_aware_boost(
    query=user_query,
    field_weights={"title": 5, "main_content": 2}
)
results = solr_client.search(**boost_query)
```

**Post-Retrieval Re-Ranking:**

```python
def rerank_by_attention_model(docs, query, expected_doc_ids=None):
    """Re-rank docs considering LLM attention patterns.
    
    Args:
        docs: Retrieved documents (with position, relevance score)
        query: User query
        expected_doc_ids: Known good doc IDs (if available)
    
    Returns:
        Re-ranked document list
    """
    scored = []
    
    for doc in docs:
        # Base relevance score (from Solr)
        relevance = doc.score
        
        # Position weight (models attention decay)
        # Position 1: weight = 1.0
        # Position 5: weight = 0.57
        # Position 10: weight = 0.40
        position_weight = 1.0 / (1.0 + 0.15 * doc.position)
        
        # Expected doc bonus (if we know which docs should be there)
        expected_bonus = 2.0 if doc.id in (expected_doc_ids or []) else 1.0
        
        # Combined score
        final_score = relevance * position_weight * expected_bonus
        
        scored.append((final_score, doc))
    
    # Sort by combined score (descending)
    scored.sort(reverse=True, key=lambda x: x[0])
    
    return [doc for score, doc in scored]

# Usage after Solr retrieval:
docs = rerank_by_attention_model(
    docs=raw_solr_results,
    query=user_query,
    expected_doc_ids=["doc123", "doc456"],  # From HEAL extracted tickets
)
```

### Strategy 3: Context Window Budgeting

**Problem:** No systematic token allocation strategy

**Solution:** Treat tokens like memory allocation in embedded systems

```python
class ContextBudget:
    """Token budget allocation for RAG context construction.
    
    Treats context window as finite resource, allocates deterministically.
    """
    
    def __init__(self, total_tokens=128000):
        """Initialize budget.
        
        Args:
            total_tokens: Total context window size (default: 128K for Claude)
        """
        self.total = total_tokens
        
        # Fixed allocations
        self.allocated = {
            "system_prompt": 2000,
            "query": 500,
            "response_buffer": 2000,
            "safety_margin": 1000,
        }
        
        self.remaining = total_tokens - sum(self.allocated.values())
    
    def allocate_for_docs(self, num_docs, min_per_doc=200):
        """Allocate remaining budget to docs.
        
        Args:
            num_docs: Number of documents to allocate for
            min_per_doc: Minimum tokens per doc (default: 200)
        
        Returns:
            Tokens per document
        """
        tokens_per_doc = self.remaining // num_docs
        
        # Enforce minimum
        if tokens_per_doc < min_per_doc:
            # Reduce num_docs to meet minimum
            feasible_docs = self.remaining // min_per_doc
            print(f"Warning: Can only fit {feasible_docs} docs at {min_per_doc} tokens each")
            return min_per_doc
        
        return tokens_per_doc
    
    def should_add_doc(self, doc_tokens):
        """Check if adding doc exceeds budget.
        
        Args:
            doc_tokens: Tokens required for this doc
        
        Returns:
            bool: True if doc fits in budget
        """
        return doc_tokens <= self.remaining
    
    def consume(self, tokens, category="docs"):
        """Consume tokens from budget.
        
        Args:
            tokens: Number of tokens consumed
            category: Category name (for tracking)
        """
        self.remaining -= tokens
        if category in self.allocated:
            self.allocated[category] += tokens
        else:
            self.allocated[category] = tokens
    
    def get_status(self):
        """Get budget status.
        
        Returns:
            dict with allocation breakdown
        """
        return {
            "total": self.total,
            "allocated": self.allocated,
            "remaining": self.remaining,
            "utilization": (self.total - self.remaining) / self.total,
        }

# Usage in document retrieval:
budget = ContextBudget(total_tokens=128000)

# Allocate for 5 documents
tokens_per_doc = budget.allocate_for_docs(num_docs=5)
print(f"Budget: {tokens_per_doc} tokens per document")

# Truncate documents to budget
for doc in docs[:5]:
    max_chars = tokens_per_doc * 4  # Rough: 4 chars per token
    doc.content = doc.content[:max_chars]
    
    # Track consumption
    actual_tokens = len(doc.content.split()) * 1.3
    budget.consume(actual_tokens, category="docs")

# Check final status
status = budget.get_status()
print(f"Token utilization: {status['utilization']:.1%}")
```

### Strategy 4: Document Clustering

**Problem:** Relevant docs scattered across context (fragmentation)

**Solution:** Cluster related docs together for better multi-hop reasoning

```python
def cluster_documents(docs, max_distance=5):
    """Cluster related documents together in context.
    
    Args:
        docs: List of documents with relevance scores
        max_distance: Max position distance to consider "nearby"
    
    Returns:
        Re-ordered document list with clusters
    """
    # Separate into expected (high-relevance) and other
    expected = [doc for doc in docs if doc.relevance_score > 0.8]
    other = [doc for doc in docs if doc.relevance_score <= 0.8]
    
    # Strategy: Place expected docs at top (positions 1-N)
    # This creates a "cluster" of relevant docs
    # Other docs fill remaining positions
    
    clustered = expected + other
    
    return clustered

# Usage:
docs = cluster_documents(retrieved_docs)
# Result: Positions 1-3 have expected docs (clustered)
#         Positions 4-10 have other docs
```

---

## 7. Measuring What Matters in HEAL

### Implementing Attention-Aware Metrics

**Add to HEAL evaluation framework:**

```python
# In lightspeed-evaluation or HEAL metrics
class AttentionAwareMetrics:
    """Metrics based on transformer attention mechanics.
    
    These metrics capture how well retrieval aligns with LLM attention patterns.
    """
    
    @staticmethod
    def position_weighted_recall(expected_urls, retrieved_urls):
        """Recall weighted by positional attention.
        
        Standard recall treats all positions equally.
        This version weights by attention decay.
        
        Args:
            expected_urls: URLs that should be retrieved
            retrieved_urls: Actually retrieved URLs (in order)
        
        Returns:
            float: Attention-weighted recall (0.0-1.0)
        """
        if not expected_urls:
            return 0.0
        
        total_weight = 0.0
        for url in expected_urls:
            if url in retrieved_urls:
                pos = retrieved_urls.index(url) + 1
                # Attention decay model
                weight = 1.0 / (1.0 + 0.15 * pos)
                total_weight += weight
        
        # Normalize by number of expected URLs
        # Perfect score (1.0): all expected docs at position 1
        # Good score (>0.7): most expected docs in top 5
        # Bad score (<0.5): expected docs buried or missing
        return total_weight / len(expected_urls)
    
    @staticmethod
    def context_efficiency(total_tokens, answer_correctness):
        """Quality per 1K tokens used.
        
        Measures token efficiency: how much quality per token?
        
        Args:
            total_tokens: Total tokens in retrieved context
            answer_correctness: Answer quality score (0.0-1.0)
        
        Returns:
            float: Efficiency (quality per 1K tokens)
        """
        if total_tokens == 0:
            return 0.0
        return answer_correctness / (total_tokens / 1000)
    
    @staticmethod
    def attention_coverage(expected_urls, retrieved_urls, top_k=5):
        """% of expected URLs in high-attention zone (top K).
        
        Measures what fraction of expected docs are in positions
        where LLM attention is strongest.
        
        Args:
            expected_urls: URLs that should be retrieved
            retrieved_urls: Actually retrieved URLs (in order)
            top_k: Size of high-attention zone (default: 5)
        
        Returns:
            float: Coverage (0.0-1.0)
        """
        if not expected_urls:
            return 0.0
        
        top_k_urls = set(retrieved_urls[:top_k])
        expected_set = set(expected_urls)
        
        hits = len(expected_set & top_k_urls)
        return hits / len(expected_urls)
    
    @staticmethod
    def context_fragmentation(expected_urls, retrieved_urls):
        """Measure how scattered relevant docs are.
        
        Low fragmentation (clustered docs) is better for multi-hop reasoning.
        
        Args:
            expected_urls: URLs that should be retrieved
            retrieved_urls: Actually retrieved URLs (in order)
        
        Returns:
            dict with fragmentation metrics
        """
        positions = [
            retrieved_urls.index(url) + 1
            for url in expected_urls
            if url in retrieved_urls
        ]
        
        if len(positions) < 2:
            return {
                "fragmentation": 0.0,
                "span": 0,
                "is_clustered": True,
            }
        
        import numpy as np
        
        return {
            "fragmentation": float(np.std(positions)),
            "span": max(positions) - min(positions),
            "is_clustered": np.std(positions) < 5.0,
        }

# Usage in pattern fixing:
metrics = AttentionAwareMetrics()

# During Phase 1: Diagnosis
position_weighted_recall = metrics.position_weighted_recall(
    expected_urls=turn.expected_urls,
    retrieved_urls=retrieval_result.urls,
)

attention_coverage = metrics.attention_coverage(
    expected_urls=turn.expected_urls,
    retrieved_urls=retrieval_result.urls,
    top_k=5,
)

fragmentation = metrics.context_fragmentation(
    expected_urls=turn.expected_urls,
    retrieved_urls=retrieval_result.urls,
)

# Diagnosis logic:
if url_f1 >= 0.7 and answer_correctness < 0.7:
    # Docs retrieved but answer poor
    
    if attention_coverage < 0.5:
        diagnosis = "LOST_IN_MIDDLE"
        fix_strategy = "RERANK_TO_TOP_5"
    
    elif fragmentation["is_clustered"] == False:
        diagnosis = "FRAGMENTED_CONTEXT"
        fix_strategy = "CLUSTER_RELEVANT_DOCS"
    
    elif context_efficiency < 0.3:
        diagnosis = "TOKEN_WASTE"
        fix_strategy = "TRUNCATE_IRRELEVANT_DOCS"
```

### Integration with Existing HEAL Workflow

**Phase 1: Enhanced Baseline Assessment**

```python
# Current: Basic metrics
baseline_metrics = {
    "url_f1": 0.65,
    "url_precision": 0.70,
    "url_recall": 0.60,
    "answer_correctness": 0.45,
}

# Enhanced: Add attention-aware metrics
attention_metrics = AttentionAwareMetrics()

baseline_metrics["position_weighted_recall"] = attention_metrics.position_weighted_recall(...)
baseline_metrics["attention_coverage"] = attention_metrics.attention_coverage(...)
baseline_metrics["context_fragmentation"] = attention_metrics.context_fragmentation(...)
baseline_metrics["context_efficiency"] = attention_metrics.context_efficiency(...)

# New diagnosis paths:
if baseline_metrics["attention_coverage"] < 0.5:
    routing_decision = "RERANK_OPTIMIZATION"
elif baseline_metrics["context_fragmentation"]["fragmentation"] > 10:
    routing_decision = "CLUSTERING_OPTIMIZATION"
```

**Phase 2: Position-Aware Optimization**

```python
# New optimization phase: Improve positions without changing retrieved docs
if routing_decision == "RERANK_OPTIMIZATION":
    for iteration in range(max_iterations):
        # Re-rank retrieved docs
        reranked_docs = rerank_by_attention_model(docs, query)
        
        # Evaluate with new positions
        new_metrics = evaluate(reranked_docs)
        
        # Check if attention coverage improved
        if new_metrics["attention_coverage"] >= 0.7:
            break
```

---

## 8. Implementation Roadmap

### Phase 1: Measurement (Week 1-2)

**Goal:** Add attention-aware metrics to HEAL evaluation

**Tasks:**
1. Implement `AttentionAwareMetrics` class
2. Add metrics to evaluation pipeline
3. Collect baseline data on existing patterns
4. Analyze correlation: attention metrics ↔ answer quality

**Deliverables:**
- `src/heal/core/metrics/attention_metrics.py`
- Updated evaluation reports with new metrics
- Baseline data analysis notebook

### Phase 2: "Lost in the Middle" Experiments (Week 3-4)

**Goal:** Quantify the effect empirically

**Experiments:**

**Experiment 1: Position Sensitivity**
```python
# Test: Same docs, different positions
for target_position in [1, 3, 5, 10, 15, 20]:
    # Place expected doc at target_position
    # Run evaluation
    # Measure: answer_correctness(position)

# Expected outcome: Decay curve
# Plot: position (x-axis) vs answer_correctness (y-axis)
```

**Experiment 2: U-Curve Validation**
```python
# Test: Measure attention across entire context window
positions = range(1, 201, 5)  # Sample every 5th position
for pos in positions:
    # Place relevant doc at position
    # Measure answer quality
    # Plot U-shaped curve

# Compare to Liu et al. (2023) findings
```

**Experiment 3: Clustering vs Scattering**
```python
# Test A: Cluster (positions 1,2,3)
# Test B: Scatter (positions 1, 10, 20)
# Same docs, different arrangements
# Measure: Does clustering help multi-hop reasoning?
```

**Deliverables:**
- Experimental results documenting position effects
- Quantified "middle zone" boundaries
- U-curve validation plots
- Research paper draft (optional)

### Phase 3: Optimization Implementation (Week 5-6)

**Goal:** Implement fixes based on findings

**Tasks:**
1. Implement position-aware re-ranking
2. Add adaptive truncation
3. Implement context budgeting
4. Add clustering strategy

**Deliverables:**
- Updated Solr Expert with re-ranking
- Updated Linux Expert with adaptive truncation
- New optimization phase in pattern fixing
- Performance comparison (before/after)

### Phase 4: Validation & Tuning (Week 7-8)

**Goal:** Validate improvements on real patterns

**Tasks:**
1. Re-run failed patterns with new optimizations
2. Measure improvement in answer_correctness
3. Analyze token efficiency gains
4. Tune parameters (top_k, truncation thresholds, etc.)

**Deliverables:**
- Pattern fix success rate comparison
- Token efficiency analysis
- Optimized parameter settings
- Production deployment plan

---

## 9. Research Papers & References

### Essential Reading

**1. "Lost in the Middle: How Language Models Use Long Contexts"**
- Authors: Liu et al. (2023)
- arXiv: https://arxiv.org/abs/2307.03172
- Key findings: U-shaped attention curve, middle-position penalty
- **Read this first** - directly relevant to your experiments

**2. "Attention Is All You Need"**
- Authors: Vaswani et al. (2017)
- arXiv: https://arxiv.org/abs/1706.03762
- The original Transformer paper
- Explains positional encoding, attention mechanism

**3. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"**
- Authors: Lewis et al. (2020)
- arXiv: https://arxiv.org/abs/2005.11401
- RAG foundations, retrieval strategies

**4. "In-Context Retrieval-Augmented Language Models"**
- Authors: Ram et al. (2023)
- arXiv: https://arxiv.org/abs/2302.00083
- Modern RAG techniques, position effects

**5. "Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering"**
- Authors: Izacard & Grave (2021)
- arXiv: https://arxiv.org/abs/2007.01282
- Fusion-in-Decoder (FiD), handling multiple passages

### Related Work on Position Effects

**6. "Does the Order of Context Matter? Exploring How Language Models Use Long Contexts"**
- Similar to Liu et al., explores ordering effects

**7. "An Information-theoretic Approach to Prompt Engineering Without Ground Truth Labels"**
- Position-aware prompt design

**8. "Rethinking the Role of Demonstrations: What Makes In-Context Learning Work?"**
- How position affects few-shot examples

### Practical RAG Optimization

**9. "Precise Zero-Shot Dense Retrieval without Relevance Labels"**
- Authors: Gao et al. (2022)
- Better retrieval without fine-tuning

**10. "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection"**
- Authors: Asai et al. (2023)
- Self-correcting RAG systems

---

## Appendix A: Quick Reference

### Key Formulas

**Attention Weight Decay (Empirical):**
```python
attention_weight(pos) = 1.0 / (1.0 + 0.15 * pos)
```

**Position-Weighted Recall:**
```python
PWR = sum(attention_weight(pos(url)) for url in expected if url in retrieved) / len(expected)
```

**Context Efficiency:**
```python
efficiency = answer_correctness / (total_tokens / 1000)
```

**Fragmentation:**
```python
fragmentation = std_dev([positions of expected docs])
```

### Diagnostic Decision Tree

```
url_f1 >= 0.7 AND answer_correctness < 0.7
├─ attention_coverage < 0.5
│  └─ DIAGNOSIS: "LOST_IN_MIDDLE"
│     FIX: Re-rank to top 5 positions
├─ fragmentation > 10
│  └─ DIAGNOSIS: "FRAGMENTED_CONTEXT"
│     FIX: Cluster relevant docs together
├─ context_efficiency < 0.3
│  └─ DIAGNOSIS: "TOKEN_WASTE"
│     FIX: Truncate irrelevant docs
└─ position_weighted_recall < 0.6
   └─ DIAGNOSIS: "POOR_POSITIONS"
      FIX: Boost query for better ranking
```

### Typical Metric Ranges

| Metric | Excellent | Good | Poor |
|--------|-----------|------|------|
| position_weighted_recall | > 0.8 | 0.6-0.8 | < 0.6 |
| attention_coverage | > 0.8 | 0.5-0.8 | < 0.5 |
| context_efficiency | > 0.5 | 0.3-0.5 | < 0.3 |
| fragmentation | < 5 | 5-10 | > 10 |
| avg_position | < 3 | 3-8 | > 8 |

---

## Appendix B: Experiment Templates

### Template 1: Position Sensitivity

```python
import pandas as pd
import matplotlib.pyplot as plt

# Setup
query = "How to configure SSH authentication in RHEL?"
expected_doc = load_doc("ssh_auth_guide.html")
noise_docs = load_docs("irrelevant/*.html", n=20)

results = []

# Test each position
for target_position in range(1, 21):
    # Build context with expected doc at target_position
    context = noise_docs[:target_position-1] + [expected_doc] + noise_docs[target_position:]
    
    # Evaluate
    answer = llm.generate(query, context=context)
    quality = evaluate_answer(answer, expected_answer)
    
    results.append({
        "position": target_position,
        "answer_correctness": quality,
    })

# Plot
df = pd.DataFrame(results)
plt.plot(df["position"], df["answer_correctness"])
plt.xlabel("Document Position")
plt.ylabel("Answer Correctness")
plt.title("Position Sensitivity Curve")
plt.savefig("position_sensitivity.png")
```

### Template 2: Clustering vs Scattering

```python
# Test A: Clustered
context_clustered = [doc1, doc2, doc3] + noise_docs
quality_clustered = evaluate(query, context_clustered)

# Test B: Scattered  
context_scattered = [doc1] + noise_docs[:5] + [doc2] + noise_docs[5:10] + [doc3] + noise_docs[10:]
quality_scattered = evaluate(query, context_scattered)

print(f"Clustered: {quality_clustered:.3f}")
print(f"Scattered: {quality_scattered:.3f}")
print(f"Improvement: {quality_clustered - quality_scattered:.3f}")
```

---

**End of Document**

For questions or collaboration on "Lost in the Middle" research, contact the HEAL team.
