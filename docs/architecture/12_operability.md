# Operability & Operations Manual

**System:** Cogito AI Research Platform  
**Commit:** 0f51527  
**Date:** 2025-11-06

---

## 1. Configuration Management

### Configuration Sources

**Precedence (Highest to Lowest):**
1. CLI Arguments
2. Environment Variables
3. `config.json` or `config.yaml`
4. Default Values

### Primary Configuration File

**Location:** `config.json`

**Key Sections:**
```json
{
  "api": {
    "primary_provider": "openai",
    "openai": { "model": "gpt-5", "temperature": 0.2 },
    "anthropic": { "model": "claude-3-opus" },
    "gemini": { "model": "gemini-2.5-pro-exp-03-25" }
  },
  "preflight": {
    "extract": { "enabled": false, "max_points": 12 },
    "queries": { "enabled": false, "max_queries": 8 }
  },
  "council_orchestrator": {
    "max_agents": 6,
    "enable_self_critique": true,
    "parallel_execution": true
  }
}
```

### Environment Variables

**Required:**
```bash
# API Keys (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional
DEEPSEEK_API_KEY=...
```

**Optional:**
```bash
# Override config.json settings
COGITO_PRIMARY_PROVIDER=anthropic
COGITO_MAX_AGENTS=4
COGITO_ENABLE_PREFLIGHT=true
```

### Configuration Validation

**Currently:** ⚠️ No validation

**Recommended:**
```python
# src/config/validator.py
def validate_config(config: Dict) -> List[str]:
    errors = []
    
    # Check API provider configured
    if not config.get('api', {}).get('primary_provider'):
        errors.append("Missing primary_provider in api config")
    
    # Check API key available
    provider = config['api']['primary_provider']
    key_var = f"{provider.upper()}_API_KEY"
    if key_var not in os.environ:
        errors.append(f"Missing environment variable: {key_var}")
    
    # Validate numeric ranges
    max_agents = config.get('council_orchestrator', {}).get('max_agents', 6)
    if not 1 <= max_agents <= 20:
        errors.append(f"max_agents must be 1-20, got {max_agents}")
    
    return errors
```

---

## 2. Logging Strategy

### Current Implementation

**Format:** Plain text with timestamps

**Example:**
```
2025-11-06 13:45:22 INFO Starting council orchestration
2025-11-06 13:45:23 INFO Agent Aristotle initialized
2025-11-06 13:45:45 INFO Agent Aristotle completed (confidence: 0.85)
```

### Log Levels

| Level | Usage | Examples |
|-------|-------|----------|
| DEBUG | Development diagnostics | Token counts, detailed state |
| INFO | Normal operations | Pipeline stages, completions |
| WARNING | Recoverable issues | Retries, fallbacks |
| ERROR | Failures | API errors, validation failures |
| CRITICAL | System failures | Unrecoverable errors |

### Log Locations

**Console:** Stdout/stderr (default)

**File Logging:** Not currently implemented

**Recommended:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('logs/cogito.log')  # File
    ]
)
```

### Structured Logging (Recommended)

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "council.agent.complete",
    agent_id=agent.id,
    persona=agent.persona.name,
    duration_ms=duration,
    confidence=confidence,
    tokens_used=tokens
)
```

**Output:**
```json
{
  "event": "council.agent.complete",
  "timestamp": "2025-11-06T13:45:45.123Z",
  "level": "info",
  "agent_id": "agent-001",
  "persona": "Aristotle",
  "duration_ms": 23450,
  "confidence": 0.85,
  "tokens_used": 15234
}
```

---

## 3. Monitoring & Metrics

### Current State: ⚠️ Minimal

**What's Tracked:**
- Console output (manual observation)
- Token counts (in responses)
- Execution times (partial)

**What's Missing:**
- Real-time dashboards
- Aggregated metrics
- Trend analysis
- Alerting

### Recommended Metrics

**System Metrics:**
- CPU utilization
- Memory usage
- Disk I/O
- Network throughput

**Application Metrics:**
```python
# Pipeline metrics
critique_duration_seconds{pipeline="council"}
critique_success_total{pipeline="council"}
critique_failure_total{pipeline="council",reason="timeout"}

# Agent metrics
agent_execution_seconds{persona="Aristotle"}
agent_confidence{persona="Aristotle"}

# LLM metrics
llm_request_total{provider="openai",model="gpt-5"}
llm_tokens_used{provider="openai",type="input"}
llm_cost_usd{provider="openai"}

# Cache metrics
cache_hit_total{type="vector"}
cache_miss_total{type="vector"}
```

### Metrics Collection

**Recommended Stack:**

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
critique_duration = Histogram(
    'critique_duration_seconds',
    'Time spent on critique',
    ['pipeline']
)

llm_tokens = Counter(
    'llm_tokens_used',
    'Tokens consumed',
    ['provider', 'type']
)

# Instrument code
with critique_duration.labels(pipeline='council').time():
    result = run_critique(content)

llm_tokens.labels(provider='openai', type='input').inc(tokens_in)
```

**Expose Metrics:**
```python
# Start metrics server
start_http_server(8000)  # Metrics at http://localhost:8000/metrics
```

---

## 4. Health Checks

### Current State: ❌ Not Implemented

### Recommended Health Checks

```python
# src/infrastructure/health.py

class HealthChecker:
    def check_llm_providers(self) -> Dict[str, bool]:
        """Check if LLM providers are accessible."""
        return {
            "openai": self._ping_openai(),
            "anthropic": self._ping_anthropic(),
            "gemini": self._ping_gemini()
        }
    
    def check_file_system(self) -> Dict[str, Any]:
        """Check file system health."""
        return {
            "writable": os.access(".", os.W_OK),
            "disk_space_gb": shutil.disk_usage(".").free / (1024**3),
            "cache_size_mb": self._get_cache_size() / (1024**2)
        }
    
    def check_vector_store(self) -> bool:
        """Check if vector store is operational."""
        try:
            # Perform simple query
            store = VectorStore()
            store.search("test", k=1)
            return True
        except Exception:
            return False
    
    def get_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "0.1.0",
            "providers": self.check_llm_providers(),
            "filesystem": self.check_file_system(),
            "vector_store": self.check_vector_store()
        }
```

**Health Endpoint (if API added):**
```
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2025-11-06T13:45:00Z",
  "checks": {
    "openai": true,
    "anthropic": true,
    "filesystem": true,
    "vector_store": true
  }
}
```

---

## 5. Deployment

### Current Deployment: Manual

**Steps:**
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` with API keys
4. Run: `python run_critique.py`

### Recommended: Containerized Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    texlive-full \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY run_critique.py run_research.py ./

# Create directories
RUN mkdir -p artifacts critiques input latex_output

# Expose metrics port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["python"]
CMD ["run_critique.py", "--help"]
```

**Build & Run:**
```bash
docker build -t cogito:latest .
docker run -it --rm \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/critiques \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  cogito:latest run_critique.py input/document.txt
```

### Docker Compose (with monitoring):

```yaml
version: '3.8'

services:
  cogito:
    build: .
    volumes:
      - ./input:/app/input
      - ./output:/app/critiques
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    ports:
      - "8000:8000"  # Metrics
  
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 6. Troubleshooting

### Common Issues

#### Issue: "API key not found"

**Symptoms:**
```
Error: Missing environment variable: OPENAI_API_KEY
```

**Resolution:**
1. Check `.env` file exists
2. Verify key format: `OPENAI_API_KEY=sk-...`
3. Ensure `.env` loaded: `source .env` or use `python-dotenv`
4. Restart application

---

#### Issue: "Rate limit exceeded"

**Symptoms:**
```
Error 429: Rate limit exceeded
```

**Resolution:**
1. Wait 60 seconds and retry
2. Check API usage dashboard
3. Switch provider: `--provider anthropic`
4. Implement rate limiting in code

---

#### Issue: "Vector store memory error"

**Symptoms:**
```
MemoryError: Unable to allocate array
```

**Resolution:**
1. Clear cache: `rm -rf arxiv_cache/`
2. Reduce vector dimensions in config
3. Increase system RAM
4. Use pagination for large datasets

---

#### Issue: "LaTeX compilation failed"

**Symptoms:**
```
Error: pdflatex not found
```

**Resolution:**
1. Install LaTeX: `apt-get install texlive-full`
2. Verify installation: `which pdflatex`
3. Check PATH includes LaTeX binaries
4. Use `--no-latex` flag as workaround

---

#### Issue: "Timeout during agent execution"

**Symptoms:**
```
TimeoutError: Agent execution exceeded 300s
```

**Resolution:**
1. Increase timeout in config: `timeout_seconds: 600`
2. Reduce reasoning tree depth: `max_depth: 2`
3. Disable self-critique: `enable_self_critique: false`
4. Check LLM provider status

---

### Debugging Tips

**Enable Debug Logging:**
```bash
export COGITO_LOG_LEVEL=DEBUG
python run_critique.py document.txt
```

**Trace LLM Calls:**
```bash
export COGITO_TRACE_LLM=true  # Log all prompts/responses
```

**Profile Performance:**
```python
import cProfile
cProfile.run('run_critique(content)', 'stats.prof')

# Analyze
python -m pstats stats.prof
>>> sort cumtime
>>> stats 20
```

**Memory Profiling:**
```python
from memory_profiler import profile

@profile
def run_critique(content):
    ...
```

---

## 7. Backup & Recovery

### What to Backup

| Data | Frequency | Retention | Priority |
|------|-----------|-----------|----------|
| Source Code | Continuous | Forever | Critical |
| Configuration | On Change | 90 days | High |
| Artifacts | Daily | 30 days | Medium |
| Vector Store | Weekly | 7 days | Low (rebuildable) |
| Logs | Daily | 7 days | Low |

### Backup Script

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/cogito_$DATE"

mkdir -p "$BACKUP_DIR"

# Backup configuration
cp config.json "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/.env.bak"  # Be careful with secrets!

# Backup artifacts
tar -czf "$BACKUP_DIR/artifacts.tar.gz" artifacts/

# Backup critiques
tar -czf "$BACKUP_DIR/critiques.tar.gz" critiques/

# Backup vector store
tar -czf "$BACKUP_DIR/vector_store.tar.gz" arxiv_cache/

echo "Backup completed: $BACKUP_DIR"
```

### Restore Procedure

```bash
#!/bin/bash
# restore.sh BACKUP_DIR

BACKUP_DIR=$1

# Restore configuration
cp "$BACKUP_DIR/config.json" ./

# Restore artifacts
tar -xzf "$BACKUP_DIR/artifacts.tar.gz"

# Restore critiques
tar -xzf "$BACKUP_DIR/critiques.tar.gz"

# Restore vector store
tar -xzf "$BACKUP_DIR/vector_store.tar.gz"

echo "Restore completed from: $BACKUP_DIR"
```

---

## 8. Capacity Planning

### Resource Requirements (Per Critique)

| Resource | Typical | Peak | Notes |
|----------|---------|------|-------|
| CPU | 2 cores | 4 cores | During local processing |
| Memory | 800MB | 1.7GB | Vector store dominant |
| Disk | 100MB | 500MB | Cache and artifacts |
| Network | 10MB | 50MB | LLM API traffic |
| Time | 5min | 10min | End-to-end |

### Scaling Guidelines

**Single Instance Capacity:**
- ~5 critiques/hour
- ~40 critiques/day (8-hour operation)
- ~800 critiques/month

**Scaling Triggers:**
- Memory usage > 1.5GB sustained
- Queue depth > 10 requests
- Average latency > 7 minutes
- Error rate > 5%

**Scaling Actions:**
- Add horizontal workers
- Increase per-worker resources
- Implement request queueing
- Add caching layers

---

## 9. Security Operations

### Secret Rotation

**Frequency:** Every 90 days (recommended)

**Procedure:**
1. Generate new API key in provider console
2. Update `.env` file with new key
3. Test with `--dry-run` flag
4. Deploy new secret
5. Revoke old key after 24-hour overlap

### Access Control

**Current:** File system permissions

**Recommended:**
- Limit `.env` to owner: `chmod 600 .env`
- Restrict artifacts directory
- Use separate service accounts per environment

### Audit Logging

**Track:**
- Who ran critiques (if multi-user)
- Configuration changes
- API key usage
- Failures and errors

---

## 10. Maintenance Tasks

### Daily
- [ ] Check disk space
- [ ] Review error logs
- [ ] Monitor token usage

### Weekly
- [ ] Clear old cache files (>7 days)
- [ ] Review critique success rate
- [ ] Check for dependency updates
- [ ] Backup artifacts

### Monthly
- [ ] Review and rotate API keys
- [ ] Update dependencies
- [ ] Audit configuration changes
- [ ] Review and optimize costs

### Quarterly
- [ ] Architectural review
- [ ] Performance testing
- [ ] Security audit
- [ ] Disaster recovery drill

---

## 11. Runbooks

### Runbook: Handle API Outage

**Scenario:** Primary LLM provider (OpenAI) is down

**Steps:**
1. Confirm outage: Check provider status page
2. Switch to fallback provider:
   ```bash
   export COGITO_PRIMARY_PROVIDER=anthropic
   python run_critique.py ...
   ```
3. Monitor fallback provider performance
4. Notify stakeholders of temporary provider change
5. Revert to primary when restored

**Recovery Time:** 5 minutes

---

### Runbook: Clear Corrupt Cache

**Scenario:** Vector store returning incorrect results

**Steps:**
1. Stop all running processes
2. Backup current cache:
   ```bash
   mv arxiv_cache arxiv_cache.backup
   ```
3. Clear cache:
   ```bash
   rm -rf arxiv_cache/
   ```
4. Restart system (cache rebuilds automatically)
5. Verify search results
6. Remove backup if successful

**Recovery Time:** 30 minutes

---

### Runbook: Handle Memory Exhaustion

**Scenario:** Process crashes with OOM error

**Steps:**
1. Check available memory: `free -h`
2. Identify memory hog: `ps aux --sort=-%mem | head`
3. Clear caches if possible
4. Restart with reduced load:
   ```bash
   COGITO_MAX_AGENTS=3 python run_critique.py ...
   ```
5. Consider vertical scaling
6. Monitor memory usage

**Recovery Time:** 10 minutes

---

## Appendix: Operational Checklist

### Pre-Production Checklist

- [ ] All API keys configured
- [ ] Configuration validated
- [ ] Logging enabled
- [ ] Monitoring setup
- [ ] Health checks implemented
- [ ] Backup strategy defined
- [ ] Runbooks documented
- [ ] Security audit completed
- [ ] Performance tested
- [ ] Disaster recovery tested

### Production Readiness Score

Current: **40/100** ⚠️ **Not Production Ready**

Gaps:
- Monitoring and alerting
- Automated backups
- Circuit breakers
- Health checks
- Disaster recovery

---

**Manual Version:** 1.0  
**Last Updated:** 2025-11-06  
**Maintainer:** Operations Team
