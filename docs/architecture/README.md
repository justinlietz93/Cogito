# Cogito Architecture Documentation

**System:** Cogito AI Research Platform  
**Version:** 0.1  
**Commit:** 0f51527  
**Analysis Date:** 2025-11-06

---

## Overview

This directory contains comprehensive architectural documentation for the Cogito AI Research Platform, including C4 diagrams, dependency analysis, pipeline deep dives, quality assessments, and refactoring roadmaps.

---

## Document Index

### Core Architecture (Start Here)

| Document | Description | Size |
|----------|-------------|------|
| **00_executive_summary.md** | High-level overview, scores, risks, recommendations | Essential |
| **architecture-map.json** | Machine-readable architectural graph | Reference |

### C4 Model Diagrams (Visualization)

| Document | C4 Level | Description |
|----------|----------|-------------|
| **01_context_c4.mmd** | Level 1 | System context (users, external systems) |
| **02_containers_c4.mmd** | Level 2 | Containers (pipelines, services, stores) |
| **03_components_critique_pipeline.mmd** | Level 3 | Critique pipeline components |
| **03_components_syncretic_catalyst.mmd** | Level 3 | Syncretic catalyst components |

### Code Structure

| Document | Description |
|----------|-------------|
| **04_code_map.md** | Complete module inventory with responsibilities, LOC, metrics |
| **05_dependency_graph.dot** | Graphviz dependency graph (0 cycles!) |
| **06_dependency_matrix.csv** | Module-to-module adjacency matrix |

### Runtime Behavior

| Document | Description |
|----------|-------------|
| **07_runtime_sequence_critique_council.mmd** | End-to-end critique pipeline sequence |
| **07_runtime_sequence_syncretic_catalyst.mmd** | End-to-end thesis generation sequence |
| **09_domain_model.mmd** | Domain entities, value objects, aggregates |

### Quality & Compliance

| Document | Description |
|----------|-------------|
| **10_quality_gates.md** | Quality metrics, hotspots, test coverage, scoring |
| **11_non_functionals.md** | Performance, security, reliability, scalability analysis |
| **12_operability.md** | Configuration, logging, monitoring, deployment guide |
| **13_refactor_plan.md** | Prioritized improvements (quick wins → strategic) |
| **14_clean_arch_alignment.md** | Clean Architecture compliance assessment |

### Pipeline Deep Dives

| Document | Description |
|----------|-------------|
| **15_pipelines/critique_council.md** | Complete Critique Council documentation (23k words) |
| **15_pipelines/syncretic_catalyst.md** | Complete Syncretic Catalyst documentation |

---

## Quick Start Guide

### For Stakeholders (Non-Technical)

1. Read: **00_executive_summary.md** (scores, risks, recommendations)
2. View: C4 diagrams (visual system overview)
3. Review: **10_quality_gates.md** (quality assessment)

### For Engineers (Technical)

1. Read: **04_code_map.md** (module inventory)
2. Study: **07_runtime_sequence_*.mmd** (pipeline flows)
3. Analyze: **05_dependency_graph.dot** (dependency structure)
4. Review: **15_pipelines/** (detailed pipeline documentation)

### For Architects

1. Read: **14_clean_arch_alignment.md** (architecture compliance)
2. Analyze: **architecture-map.json** (complete system graph)
3. Study: **13_refactor_plan.md** (improvement roadmap)
4. Review: **11_non_functionals.md** (NFR analysis)

### For Operations

1. Read: **12_operability.md** (ops manual)
2. Configure: Using configuration guide
3. Monitor: Set up recommended metrics
4. Backup: Implement backup strategy

---

## Key Findings

### Architecture Scores (0-5)

| Dimension | Score | Status |
|-----------|-------|--------|
| Architecture Clarity | 4.0 | ✅ Good |
| Boundary Discipline | 4.0 | ✅ Good |
| Pipeline Separability | 5.0 | ✅ Excellent |
| Observability | 2.0 | ⚠️ Needs Work |
| Reproducibility | 3.0 | ⚠️ Adequate |
| Security Basics | 3.0 | ⚠️ Adequate |
| Performance Hygiene | 3.0 | ⚠️ Adequate |
| Test Depth | 4.0 | ✅ Good |
| **Overall** | **3.5/5** | ✅ **Good** |

### Critical Metrics

- **Total Modules:** 148
- **Total LOC:** ~26,000
- **Dependencies:** 62 edges
- **Cyclic Dependencies:** 0 ✅
- **Files > 500 LOC:** 2 ⚠️
- **Test Coverage:** ~65% (target: 80%)
- **Hotspots:** 28 identified

### Top Risks

1. **R1:** `prompt_texts.py` maintainability (1755 LOC) - High
2. **R2:** `openai_gateway.py` complexity (1235 LOC) - High
3. **R3:** Token cost explosion without controls - Medium
4. **R4:** No distributed tracing - Medium
5. **R5:** PII policy undefined - Medium

---

## Refactoring Priorities

### Immediate (1-2 Days)

- [ ] Refactor `prompt_texts.py` into domain modules
- [ ] Refactor `openai_gateway.py` into focused services
- [ ] Add basic circuit breaker for LLM calls
- [ ] Document PII handling policy
- [ ] Add correlation IDs for tracing

### Short-Term (1-2 Sprints)

- [ ] Implement structured logging
- [ ] Increase test coverage to 80%
- [ ] Define ports & adapters for providers
- [ ] Consolidate configuration sources
- [ ] Add performance monitoring

### Strategic (3-6 Months)

- [ ] Unified evidence graph
- [ ] Neuroca memory integration
- [ ] Evaluation harness
- [ ] Distributed orchestration
- [ ] REST API interface

---

## Architecture Patterns

### ✅ Successfully Implemented

- **Clean Architecture:** Layered with proper dependency inversion
- **Modular Monolith:** Clear module boundaries, single deployment
- **Domain-Driven Design:** Well-defined entities and aggregates
- **Dependency Injection:** Constructor injection throughout
- **Repository Pattern:** Data access abstraction
- **Strategy Pattern:** Multiple LLM providers

### ⚠️ Partially Implemented

- **Ports & Adapters:** ~60% coverage (needs formalization)
- **Circuit Breaker:** Missing (critical gap)
- **CQRS:** Not applicable (CLI tool)
- **Event Sourcing:** Not applicable
- **Saga Pattern:** Not needed (monolith)

---

## Technology Stack

### Core Technologies

- **Language:** Python 3.8+
- **LLM Providers:** OpenAI (GPT-5), Anthropic (Claude), Google (Gemini), DeepSeek
- **Vector Store:** Custom NumPy-based with OpenAI embeddings
- **Document Processing:** LaTeX, BibTeX, pdflatex
- **Research APIs:** ArXiv, PubMed, Semantic Scholar, CrossRef
- **Testing:** pytest, pytest-cov, hypothesis

### Infrastructure

- **Configuration:** JSON + YAML + .env
- **Logging:** Python logging (basic)
- **Caching:** File system
- **Monitoring:** None (recommended: Prometheus + Grafana)

---

## Diagram Formats

All diagrams are provided in **Mermaid** format (`.mmd` files) for easy rendering:

**Render with:**
- [Mermaid Live Editor](https://mermaid.live)
- VS Code Mermaid extension
- GitHub/GitLab native rendering
- `mmdc` CLI tool for SVG/PNG export

**Export Commands:**
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate SVG
mmdc -i 01_context_c4.mmd -o assets/context_c4.svg

# Generate PNG
mmdc -i 01_context_c4.mmd -o assets/context_c4.png -w 2000
```

---

## Machine-Readable Format

The **architecture-map.json** file provides a complete machine-readable representation of the system including:

- Containers and components
- Dependencies and relationships
- Pipelines and stages
- Integration points
- Metrics and scores
- Identified risks

**Schema validated** and ready for programmatic consumption by:
- CI/CD pipelines
- Architecture validation tools
- Dashboards and visualization tools
- Documentation generators

---

## Maintenance

### Review Schedule

- **Weekly:** Check for architectural drift
- **Monthly:** Update metrics, review hotspots
- **Quarterly:** Full architectural review
- **Annually:** Strategic alignment assessment

### Document Ownership

| Document Category | Owner | Review Frequency |
|-------------------|-------|------------------|
| Executive Summary | Architecture Team | Quarterly |
| C4 Diagrams | Architecture Team | Monthly |
| Code Map | Engineering Lead | Monthly |
| Quality Gates | QA Team | Weekly |
| Refactor Plan | Engineering Lead | Sprint |
| Pipeline Docs | Domain Experts | Quarterly |

---

## Tools & Utilities

### Analysis Scripts

- **`/tmp/analyze_architecture.py`** - Generates dependency analysis
- **Custom AST parser** - Builds import graph
- **Tarjan's algorithm** - Detects cycles (found 0!)

### Recommended Tools

- **Static Analysis:** pylint, flake8, mypy
- **Complexity:** radon
- **Security:** bandit, safety
- **Coverage:** pytest-cov
- **Architecture:** ArchUnit (for validation)

---

## Contribution Guidelines

When updating architecture documentation:

1. **Maintain consistency** with existing document structure
2. **Update metrics** in architecture-map.json
3. **Regenerate diagrams** if structure changes
4. **Version documents** with commit SHA
5. **Run validation** before committing

**Document Format:**
- Markdown for prose
- Mermaid for diagrams
- JSON for machine-readable data
- DOT for complex graphs
- CSV for matrices

---

## Support & Contact

**Questions?** Open an issue with label `architecture`

**Contributions?** See CONTRIBUTING.md

**Architecture Review?** Schedule with Architecture Team

---

**Documentation Version:** 1.0  
**Last Updated:** 2025-11-06  
**Maintainer:** Architecture Team  
**Status:** ✅ Complete
