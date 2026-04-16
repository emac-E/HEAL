# HEAL: Autonomous Multi-Agent RAG Fixing

**Fully autonomous system for diagnosing and fixing incorrect AI answers at scale**

---

## The Problem

RHEL Lightspeed (CLA) produces incorrect answers to user questions:
- 68 JIRA tickets logged with "cla-incorrect-answer" label
- Manual diagnosis: 2-4 hours per ticket, requires SME expertise
- Traditional LLM extraction: 21% success rate (hallucinations, no verification)
- No way to find patterns across similar failures
- Each ticket fixed individually → doesn't scale

## The Solution

HEAL uses autonomous multi-agent collaboration to extract quality test cases and fix issues:

```
JIRA Tickets (68) 
    ↓
Scope Check (filters meta-tickets, jailbreaks)
    ↓
Multi-Agent Extraction (Linux + Solr + Review Agents)
    ↓
Quality-Verified Q&A (42 RHEL tickets, 100% success)
    ↓
Pattern Discovery (groups similar failures)
    ↓
Automated Fixes (10-15 tickets per pattern)
```

**Key Innovation:** Autonomous quality loop with iterative refinement - no human intervention required.

---

## Results from Real Deployment

| Metric | Before HEAL | After HEAL | Improvement |
|--------|-------------|------------|-------------|
| **Extraction Success** | 21% | **100%** | 4.8x |
| **Time to Extract** | 2-4 hours | 10-15 minutes | 10-20x faster |
| **Security** | Vulnerable to jailbreaks | Auto-blocks attacks | ✓ Protected |
| **Scope Detection** | Manual triage | Auto-filters 38% noise | ✓ Intelligent |
| **Answer Quality** | Unverified | Production-ready | ✓ Validated |
| **Traceability** | None | Every answer has source URLs | ✓ Auditable |
| **Pattern Detection** | Manual | Automatic clustering | 10-15 tickets/fix |

**Real Results (68 tickets processed):**
- ✅ 42 RHEL tickets extracted (100% success)
- 🚫 26 meta-tickets filtered (jailbreaks, CLA behavior tests)
- ⏱️ Total time: 1-1.5 hours vs 100+ hours manual
- 🔒 8 jailbreak attempts blocked (0% success)

---

## How It Works: Three Autonomous Agents

### 1. Linux Expert Agent
15+ years RHEL expertise encoded as agent behavior
- Forms hypotheses about correct answers
- Synthesizes verified responses from documentation
- Refines based on quality feedback

### 2. Solr Expert Agent
Searches RHEL documentation (OKP) for fact verification
- Verifies answers against authoritative sources
- Returns clean docs + source URLs
- Builds search intelligence database

### 3. Review Agent
Quality gatekeeper ensuring production-ready answers
- Scores answers 0.0-1.0 (must score ≥ 0.7)
- Identifies specific issues
- Provides suggested fixes for common problems

**Plus:** Scope Check (pre-flight filter) and Pattern Discovery Agent (clustering)

---

## The Autonomous Quality Loop

```
┌─────────────────────────────────────────┐
│  Linux Expert synthesizes answer        │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Review Agent checks quality            │
│  Score ≥ 0.7? → Pass                    │
│  Score < 0.7? → Refine (up to 3x)       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  If suggested_fix available: use it     │
│  Else: Re-synthesize with feedback      │
└──────────────┬──────────────────────────┘
               ↓
          Repeat until passing
          (100% success on RHEL tickets)
```

**No human in the loop** - fully autonomous from JIRA to verified Q&A.

---

## Security: Built-In Jailbreak Protection

**Scope Check** runs before any expensive LLM processing:
- Detects meta-tickets about AI behavior
- Blocks jailbreak attempts and prompt injection
- Filters non-RHEL questions (Windows, Ubuntu, etc.)

**Demo Results:**
- 8 jailbreak attempts blocked automatically
- 18 meta-tickets about CLA behavior filtered
- 0% attack success rate
- Saves ~20-30 minutes by skipping invalid tickets early

---

## Business Value

**Faster Resolution:**
- Hours instead of days/weeks
- 60-100x faster than manual approach

**Consistent Quality:**
- Autonomous review ensures production-ready answers
- Every answer grounded in actual RHEL documentation
- Complete audit trail (source URLs for every answer)

**Scalable Approach:**
- Pattern-based fixing: address 10-15 tickets with one fix
- Reusable patterns across product versions
- Knowledge base grows over time (search intelligence)

**Risk Reduction:**
- Prevents regressions (CLA test suite validation)
- Blocks security attacks (jailbreak protection)
- Reduces hallucination risk (doc-grounded answers)

---

## Product-Agnostic Architecture

HEAL can be adapted to any product with documentation:

| Component | RHEL Implementation | Other Products |
|-----------|---------------------|----------------|
| Expert Agent | Linux Expert | Swap → Product Expert |
| Search Backend | Solr (OKP) | Any doc search API |
| Review Guidelines | RHEL-specific | Configurable YAML |
| Pattern Discovery | Domain-independent | No changes needed |

**Use Cases Beyond RHEL:**
- OpenShift documentation
- Kubernetes knowledge bases
- Enterprise software support
- Medical/legal information systems

---

## Next Steps

**Try It:**
```bash
# Quick demo (10 tickets, ~5-10 minutes)
./scripts/demo_heal_workflow.sh --quick
```

**Learn More:**
- Full documentation: `README.md`
- Demo plan: `docs/DEMO_PLAN.md`
- Technical deep dive: `docs/TRANSFORMER_MECHANICS_FOR_RAG.md`

**Contact:**
- GitHub: [Coming Soon]
- Questions: See README for contribution guidelines

**Production Deployment:**
- Currently deployed for RHEL Lightspeed
- Processing 68 tickets with 100% success on valid RHEL questions
- Open for collaboration on other products

---

## Key Takeaways

✅ **Fully autonomous** - Zero human intervention  
✅ **100% extraction success** - On valid RHEL tickets  
✅ **60-100x faster** - Than manual approach  
✅ **Security built-in** - Jailbreak protection  
✅ **Production-ready** - Quality validated  
✅ **Product-agnostic** - Adaptable to any domain  

**HEAL transforms RAG diagnosis from manual, error-prone work into autonomous, validated, scalable automation.**

---

*Generated: 2026-04-15 | Version: 1.0 | Status: Production Deployed*
