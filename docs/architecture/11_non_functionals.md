# Non-Functional Requirements & Analysis

**System:** Cogito AI Research Platform  
**Commit:** 0f51527  
**Date:** 2025-11-06

---

## 1. Performance

### Latency Requirements

| Operation | Target | Actual P95 | Status | Notes |
|-----------|--------|------------|--------|-------|
| File Read | <1s | 200ms | ✅ Excellent | I/O bound |
| Directory Scan (50 files) | <5s | 2s | ✅ Good | Recursive traversal |
| Vector Search (k=20) | <1s | 500ms | ⚠️ Acceptable | Can optimize with indexes |
| Agent Execution | <60s | 60s | ⚠️ At Limit | LLM latency dominant |
| Full Critique Pipeline | <300s | 300s | ⚠️ At Limit | Multi-agent coordination |
| LaTeX Compilation | <15s | 10s | ✅ Good | Local process |

### Throughput

- **Single Critique:** ~5 per hour (given 300s pipeline)
- **Parallel Execution:** Limited by LLM API rate limits
- **Bottleneck:** LLM API calls (serial within agent, parallel across agents)

### Computational Complexity

| Component | Complexity | Input Size | Acceptable? |
|-----------|-----------|------------|-------------|
| Directory Scan | O(n) | Files | ✅ |
| Embedding Generation | O(n * d) | Docs × Dimensions | ✅ |
| Vector Search | O(n log k) | Docs × Results | ✅ (with ANN) |
| Agent Reasoning | O(depth × breadth) | Tree structure | ⚠️ Can grow large |
| Synthesis | O(n²) | Agents | ✅ (small n) |

### Optimization Opportunities

1. **Batch LLM Calls:** Combine multiple prompts where possible (-30% latency)
2. **Cache Embeddings:** Reuse vectors for similar content (-50% embedding time)
3. **Parallel Research:** Already implemented ✅
4. **Streaming Responses:** Partial results as agents complete (-perceived latency)
5. **Approximate Vector Search:** Trade accuracy for speed (ANN algorithms)

---

## 2. Scalability

### Vertical Scaling

**Current Resource Usage:**
- CPU: ~50% (during LLM waits), 100% (during local processing)
- Memory: ~800MB average, ~1.7GB peak
- Disk I/O: Minimal (cache operations)
- Network: ~10-50 Mbps (LLM API traffic)

**Scaling Limits:**
- Memory: Vector store can grow to GB scale
- Disk: Cache can grow indefinitely without cleanup
- API Rate Limits: Primary constraint

### Horizontal Scaling

**Current State:** Single-process monolith

**Path to Horizontal Scale:**

```
┌─────────────────────┐
│   Load Balancer     │
└──────────┬──────────┘
           │
     ┌─────┴─────┬────────┐
     ↓           ↓        ↓
┌─────────┐ ┌─────────┐ ┌─────────┐
│Worker 1 │ │Worker 2 │ │Worker N │
└─────────┘ └─────────┘ └─────────┘
     ↓           ↓        ↓
┌──────────────────────────┐
│   Shared Vector Store    │
└──────────────────────────┘
```

**Requirements:**
- Stateless workers
- Shared cache (Redis)
- Message queue (RabbitMQ)
- Distributed vector store

**Estimated Capacity:**
- Single Worker: ~5 critiques/hour
- 10 Workers: ~50 critiques/hour
- Rate Limit Becomes Constraint

---

## 3. Reliability

### Availability

**Target:** 99.5% uptime (allowing ~43 hours downtime/year)

**Current SPOF (Single Points of Failure):**
- LLM Provider APIs (mitigated by multi-provider)
- Local vector store (no replication)
- File system cache (no backup)

### Fault Tolerance

**Implemented:**
- ✅ Retry with exponential backoff (3x retries)
- ✅ Provider fallback (OpenAI → Anthropic → Gemini)
- ✅ Graceful degradation (partial results on agent failure)
- ✅ Timeout enforcement

**Missing:**
- ❌ Circuit breakers
- ❌ Distributed caching
- ❌ Health checks
- ❌ Automatic recovery

### Failure Modes & Recovery

| Failure | Frequency | Impact | Recovery | MTTR |
|---------|-----------|--------|----------|------|
| LLM Timeout | Rare | Single agent fails | Retry + fallback | 30s |
| Rate Limit | Occasional | Pipeline pauses | Wait + retry | 60s |
| API Authentication | Rare | Pipeline fails | Manual key fix | 5min |
| Vector Store Corruption | Very Rare | Search degraded | Rebuild index | 30min |
| File System Full | Rare | Writes fail | Clear cache | 5min |
| Memory Exhaustion | Very Rare | Process crash | Restart | 2min |

**Mean Time To Recovery (MTTR):** ~10 minutes average

### Data Durability

- **Input Files:** User-managed
- **Artifacts:** Local file system (single copy)
- **Vector Store:** Rebuilt on demand
- **Critiques:** Saved to disk (no backup)

**Recommendation:** 
- Add S3/cloud backup for artifacts
- Replicate vector store
- Periodic snapshots

---

## 4. Security

### Authentication & Authorization

**Current State:**
- No user authentication (CLI tool)
- API keys via environment variables ✅
- No RBAC (not applicable for CLI)

**LLM Provider Security:**
- API keys in `.env` (✅ not in code)
- `.env` in `.gitignore` ✅
- No key rotation policy ⚠️
- No key expiration checks ⚠️

### Input Validation

| Input Type | Validation | Status |
|------------|-----------|--------|
| File Paths | Basic sanitization | ⚠️ Path traversal risk |
| CLI Arguments | Type checking | ✅ Good |
| LLM Responses | JSON schema validation | ✅ Good |
| Configuration Files | No validation | ⚠️ Risky |

**Vulnerabilities:**
- Path traversal: `../../etc/passwd`
- Command injection: None detected ✅
- SQL injection: Not applicable (no DB)
- XSS: Not applicable (no web UI)

### Data Privacy

**PII Handling:** ⚠️ **Not Formally Documented**

**Current Practice:**
- Content sent to LLM providers (OpenAI, Anthropic, etc.)
- No PII detection or redaction
- No data retention policy
- No user consent mechanism

**Required Actions:**
1. Document PII policy
2. Implement PII detection (regex patterns)
3. Add redaction option
4. User consent for LLM sharing
5. Data retention limits (30/60/90 days)

### Rate Limiting

**Current State:**
- No application-level rate limits
- Relies on provider rate limits
- No cost budgeting

**Recommendation:**
```python
# Implement rate limiter
class RateLimiter:
    def __init__(self, calls_per_minute=10):
        self.calls = []
        self.limit = calls_per_minute
    
    def allow_request(self) -> bool:
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) < self.limit:
            self.calls.append(now)
            return True
        return False
```

### Secrets Management

**Current:** ✅ **Acceptable**
- Environment variables used
- No hardcoded secrets
- `.env` excluded from git

**Improvement:** Use secrets manager (AWS Secrets Manager, HashiCorp Vault)

---

## 5. Maintainability

### Code Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Average File Size | 176 LOC | <300 | ✅ Good |
| Max File Size | 1755 LOC | <500 | ❌ Violation |
| Cyclomatic Complexity | 15 avg | <15 | ✅ At Target |
| Coupling (Avg Dependencies) | 0.42 | <1.0 | ✅ Excellent |
| Test Coverage | 65% | 80% | ⚠️ Below Target |

### Documentation Coverage

| Type | Coverage | Target | Status |
|------|----------|--------|--------|
| Module Docstrings | 65% | 90% | ⚠️ Below Target |
| Function Docstrings | 70% | 90% | ⚠️ Below Target |
| Class Docstrings | 80% | 90% | ⚠️ Near Target |
| Architecture Docs | High | High | ✅ Excellent |

### Technical Debt

**Estimated Debt:** 6 weeks (see [13_refactor_plan.md](./13_refactor_plan.md))

**Debt Items:**
- 🔴 P0: 2 files exceed LOC limit (2 days)
- 🔴 P0: Circuit breaker missing (1 day)
- 🟡 P1: Test coverage gaps (2 weeks)
- 🟡 P1: Structured logging (1 week)
- 🟡 P1: DI container (1 week)

---

## 6. Usability

### CLI Experience

**Strengths:**
- Clear command structure
- Help text available (`--help`)
- Progress indicators
- Error messages

**Weaknesses:**
- No interactive mode for common workflows
- Limited autocomplete support
- Complex flag combinations
- No configuration wizard

**User Feedback:**
```bash
# Current
python run_critique.py --input-dir ./docs --scientific --PR --latex

# Improved
cogito critique ./docs --scientific --format=pdf
```

### Error Messages

**Good Example:**
```
Error: File 'input.txt' not found.
Suggestion: Check the file path and try again.
```

**Poor Example:**
```
Exception: KeyError: 'openai_key'
```

**Recommendation:** Structured error messages with recovery suggestions

---

## 7. Observability

### Logging

**Current Level:** Basic Python logging

**Gaps:**
- No structured logging (JSON)
- No correlation IDs
- No distributed tracing
- Limited performance metrics

**Target:**
```python
logger.info(
    "agent.execution.complete",
    extra={
        "correlation_id": request_id,
        "agent_id": agent.id,
        "duration_ms": duration,
        "tokens_used": tokens,
        "confidence": confidence
    }
)
```

### Metrics

**Missing Metrics:**
- Request rates
- Success/failure rates
- Token consumption trends
- Cost per critique
- Cache hit rates
- API quota usage

**Recommended Stack:**
- Prometheus (metrics)
- Grafana (dashboards)
- Loki (logs)
- Jaeger (tracing)

### Alerting

**Current:** None

**Recommended Alerts:**
- API rate limit approaching
- Token budget 80% consumed
- Error rate > 5%
- Pipeline latency > 10min
- Disk space < 10%

---

## 8. Portability

### Platform Support

| Platform | Supported | Tested | Status |
|----------|-----------|--------|--------|
| Linux | ✅ | ✅ | Primary |
| macOS | ✅ | ⚠️ Limited | Compatible |
| Windows | ⚠️ | ❌ | Path issues |
| Docker | ❌ | ❌ | Not packaged |

### Dependencies

**Python Version:** 3.8+ (no hard max version pinned)

**External Dependencies:**
- LaTeX distribution (for PDF compilation)
- Internet connection (for LLM APIs)
- ~2GB disk space (for cache)

**Recommendation:** Create Dockerfile for consistent environment

---

## 9. Disaster Recovery

### Backup Strategy

**Current:** ⚠️ **Minimal**
- No automated backups
- User responsible for outputs
- Cache can be rebuilt

**Recommended:**
```
Daily Backups:
- Artifacts folder → S3
- Vector store → Cloud storage
- Configuration → Git

Retention: 30 days
```

### Recovery Time Objectives

| Data Type | RTO | RPO | Current |
|-----------|-----|-----|---------|
| System Code | <5min | 0 | ✅ Git |
| Configuration | <5min | 0 | ✅ Git |
| Vector Store | <30min | 24h | ❌ Rebuild |
| Artifacts | <1h | 24h | ⚠️ Manual |
| User Outputs | N/A | N/A | User-managed |

---

## 10. Compliance & Standards

### Code Standards

- ✅ PEP 8 (Python style guide)
- ⚠️ Type hints (partial coverage)
- ✅ Docstring conventions (Google style)

### Security Standards

- ⚠️ OWASP Top 10 (partial compliance)
- ❌ SOC 2 (not applicable yet)
- ❌ HIPAA (not applicable)
- ⚠️ GDPR (PII policy needed)

### License Compliance

- ✅ MIT License (permissive)
- ✅ All dependencies MIT-compatible
- ✅ No GPL violations

---

## Summary: Non-Functional Requirements Status

| Category | Score | Status |
|----------|-------|--------|
| Performance | 3.0/5 | ⚠️ Adequate |
| Scalability | 2.5/5 | ⚠️ Limited |
| Reliability | 3.0/5 | ⚠️ Adequate |
| Security | 3.0/5 | ⚠️ Needs Improvement |
| Maintainability | 4.0/5 | ✅ Good |
| Usability | 3.5/5 | ✅ Good |
| Observability | 2.0/5 | ⚠️ Weak |
| Portability | 3.0/5 | ⚠️ Adequate |
| Disaster Recovery | 2.0/5 | ⚠️ Minimal |
| Compliance | 3.0/5 | ⚠️ Adequate |
| **Overall** | **2.9/5** | ⚠️ **Functional but needs hardening** |

**Key Takeaways:**
- System is functionally sound but lacks operational maturity
- Primary gaps: observability, security policies, disaster recovery
- Quick wins available in circuit breakers, structured logging, PII policy
- Strategic improvements needed for production-grade reliability

---

**Report Version:** 1.0  
**Next Review:** Quarterly  
**Owner:** Platform Team
