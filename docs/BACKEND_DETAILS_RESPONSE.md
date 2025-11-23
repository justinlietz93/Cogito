# Cogito Frontend Architecture - Backend Details Response

**Date:** November 23, 2025  
**Status:** Specification Complete

---

## Response to Backend Specification Questions

This document provides definitive answers to the 10 questions posed in the frontend architecture proposal problem statement, based on comprehensive analysis of the Cogito Python-based AI research platform.

---

### 1. What protocols are exposed?

**Current State:** Cogito is a CLI-only application with no existing web protocols.

**Proposed Implementation:**
- **REST API** (Primary): FastAPI-based RESTful endpoints for all CRUD operations
- **WebSocket**: Real-time progress updates for long-running research and critique jobs
- **Multipart Form-Data**: Document uploads for critique functionality
- **Binary Responses**: PDF/LaTeX file downloads

**Rationale:** FastAPI chosen for native async support, automatic OpenAPI documentation, excellent integration with existing Python AI libraries, and built-in WebSocket support.

**No GraphQL initially** - REST provides sufficient flexibility for current requirements. GraphQL can be added in Phase 3+ if complex query optimization becomes necessary.

---

### 2. How does authentication/authorization work?

**Proposed Implementation: OAuth2 + JWT (Industry Standard)**

**Authentication Flow:**
```
1. User Registration → Password hashing (bcrypt/argon2) → User account created
2. User Login → Credentials validation → JWT Access Token (15min) + Refresh Token (7 days)
3. Subsequent Requests → Bearer token in Authorization header
4. Token Expiry → Refresh endpoint → New access token
5. Logout → Session invalidation
```

**Authorization Levels:**
- **Anonymous**: Read-only access to public research outputs
- **Researcher**: Full research/critique capabilities, personal workspace
- **Admin**: User management, system configuration, usage analytics
- **API Key**: Programmatic access for integrations

**Security Features:**
- Password hashing (bcrypt minimum 12 rounds)
- JWT with short expiry (15 minutes access, 7 days refresh)
- Rate limiting per user/IP
- CORS configuration
- API key management for external integrations
- Permission-based access control (RBAC)

---

### 3. What are the core feature domains?

Based on analysis of Cogito's architecture, the system has 6 primary feature domains:

#### A. Research Synthesis (Syncretic Catalyst)
**Purpose:** AI-powered thesis generation from research concepts

**Capabilities:**
- Multi-agent research orchestration (historical, modern, methodological, mathematical agents)
- Literature discovery across ArXiv, PubMed, Semantic Scholar, CrossRef
- Academic document production (LaTeX/PDF with proper citations)
- Iterative refinement workflows

**Integration Point:** `src/syncretic_catalyst/` (existing)

#### B. Critique & Review (Council of Critics)
**Purpose:** Multi-perspective philosophical and scientific critique

**Capabilities:**
- Philosophical critique from multiple traditions (Aristotle, Kant, Popper, Russell, etc.)
- Scientific peer review synthesis
- Confidence scoring and arbitration
- LaTeX/PDF formal review generation
- Directory batch processing

**Integration Point:** `src/council/` (existing)

#### C. Literature Search & Discovery
**Purpose:** Unified research database access

**Capabilities:**
- Unified search across 4 databases (ArXiv, PubMed, Semantic Scholar, CrossRef)
- Vector-based semantic search (OpenAI embeddings + local fallback)
- Citation graph traversal
- Research gap identification
- Query plan execution

**Integration Point:** `src/research_apis/` (existing)

#### D. Document Generation & Management
**Purpose:** Academic document compilation and storage

**Capabilities:**
- LaTeX compilation to PDF
- BibTeX citation management
- Template system (IEEE, thesis, etc.)
- Document preview generation
- Version control and storage

**Integration Point:** `src/latex/` (existing)

#### E. User Management & Preferences
**Purpose:** User accounts, settings, usage tracking

**Capabilities:**
- Profile management
- API key generation and management
- Usage quota tracking
- Preference persistence (default research configs, UI theme)
- Usage analytics

**Integration Point:** New - to be implemented

#### F. System Configuration & Administration
**Purpose:** System management and monitoring

**Capabilities:**
- LLM provider configuration (OpenAI, Anthropic, Gemini, DeepSeek)
- Research database API settings
- System health monitoring
- User administration
- Usage metrics and analytics

**Integration Point:** `config.json`, `src/config_loader.py` (existing)

---

### 4. Do any features require real-time updates?

**Yes - Critical for User Experience**

**Real-Time Requirements:**

#### Research Pipeline Progress (High Priority)
- Multi-stage progress tracking:
  - Literature search (papers found count)
  - Agent synthesis (current agent, completion %)
  - Document generation (compilation status)
- Estimated time remaining
- Live result streaming

**Technical Approach:** WebSocket per active research job

#### Critique Generation Progress (High Priority)
- Agent-by-agent completion tracking
- Current philosophical perspective being analyzed
- Intermediate results as agents complete

**Technical Approach:** WebSocket per active critique job

#### Literature Search Streaming (Medium Priority)
- Live result streaming as papers are discovered
- Source-by-source result aggregation
- Real-time relevance scoring updates

**Technical Approach:** Server-Sent Events (SSE) or WebSocket

#### System Notifications (Low Priority)
- Job completion alerts
- Usage quota warnings
- System maintenance notifications

**Technical Approach:** Server-Sent Events (SSE)

**Implementation Details:**
- Socket.IO library (Python: `python-socketio`, JavaScript: `socket.io-client`)
- Automatic reconnection with exponential backoff
- Graceful degradation to polling if WebSocket unavailable
- Room-based broadcasting (per user/job)

---

### 5. Any multi-tenant concerns?

**Current Phase: Single-Tenant Optimized**

Cogito is designed for individual researcher workstations or small research teams. However, architecture supports future multi-tenant deployment.

**Data Isolation Strategy:**
- User ID foreign key in all database records
- Query-level filtering enforced at ORM level (SQLAlchemy)
- File storage segregated by user namespace (`/storage/{user_id}/`)
- No shared state between user sessions

**Future Multi-Tenant Considerations (Phase 3+):**

#### Workspace Isolation
- Shared institutional deployment
- Workspace-level resource quotas
- Collaborative research projects (shared access to artifacts)
- Per-workspace LLM provider configuration

#### Resource Management
- CPU/memory quotas per workspace
- Concurrent job limits per user
- Storage quotas with enforcement
- Rate limiting per workspace

#### Security
- Workspace-level API keys
- Row-level security in database
- Tenant ID in JWT claims
- Audit logging per workspace

**Current Implementation:**
- Single database (PostgreSQL)
- User-scoped data access
- No workspace concept initially

---

### 6. Expected scale and performance constraints

**Scale Targets:**

#### Phase 1 (Current Year)
- **Concurrent Users:** 10-50 researchers
- **Data Volume:**
  - Vector database: 100K-1M paper embeddings
  - Document storage: 10-100 GB research outputs
  - Session data: Ephemeral (Redis-backed)
- **Request Profile:**
  - Synchronous API: 10-100 req/sec
  - Long-running jobs: 1-10 concurrent research pipelines
  - WebSocket: 10-50 active connections

#### Phase 2 (Year 2)
- **Concurrent Users:** 100-500 researchers
- **Data Volume:**
  - Vector database: 1M-10M embeddings
  - Document storage: 100GB-1TB
- **Request Profile:**
  - Synchronous API: 100-500 req/sec
  - Long-running jobs: 10-50 concurrent
  - WebSocket: 50-200 connections

**Performance Targets:**

| Operation | Target | Measurement |
|-----------|--------|-------------|
| API Response (CRUD) | <200ms | p95 latency |
| Research Job Initiation | <1s | Acknowledgment |
| Literature Search (initial) | <5s | First results |
| UI First Contentful Paint | <2s | FCP |
| Real-time Update Latency | <500ms | Event propagation |
| Database Query | <100ms | p95 |
| File Upload (10MB) | <5s | Complete |

**Resource Constraints:**

#### CPU-Intensive Operations
- LLM API calls (offload to async workers)
- LaTeX compilation (Celery task queue)
- Vector similarity calculations (batch processing)

#### Memory-Intensive Operations
- Large document parsing
- Vector embedding generation
- Result aggregation from multiple sources

#### I/O-Intensive Operations
- Paper PDF retrieval from ArXiv
- Multi-source API calls (parallel execution)
- LaTeX compilation artifacts

**Scaling Strategy:**
- Horizontal: Stateless API servers behind load balancer
- Vertical: Database optimization (indexing, query tuning)
- Async: Celery workers for long-running tasks
- Caching: Redis for session data, frequent queries

---

### 7. Accessibility / compliance targets

**Accessibility: WCAG 2.1 Level AA Compliance**

**Requirements:**
- **Keyboard Navigation**: All interactive elements accessible via keyboard
- **Screen Reader Support**: ARIA labels, landmarks, live regions
- **Focus Management**: Visible focus indicators, logical tab order
- **Color Contrast**: Minimum 4.5:1 for text, 3:1 for UI components
- **Responsive Typography**: Scalable fonts (rem units)
- **Alternative Text**: All images, icons with meaningful alt text
- **Error Identification**: Clear error messages, form validation

**Technical Implementation:**
- Radix UI primitives (accessibility built-in)
- Automated testing (axe-core in Storybook + CI)
- Manual keyboard navigation testing
- Screen reader testing (NVDA, JAWS, VoiceOver)

**Internationalization (i18n):**

#### Phase 1
- **English only** for UI strings
- Research outputs remain in source language (academic corpus is English-centric)
- Framework in place for future expansion

#### Phase 2+ (Future)
- Locale framework using next-intl or react-i18next
- Message catalogs per feature package
- Keys composed as `feature.domain.key` (e.g., `research.form.concept_label`)
- Lazy-load locale bundles
- Right-to-left (RTL) support if needed

**Compliance & Privacy:**

#### Data Privacy
- **No PII Collection** beyond email/username
- Password hashing (never stored plaintext)
- Optional profile information only
- Data export capability (GDPR-ready)
- Account deletion with data purging

#### API Usage
- Rate limiting for responsible AI provider usage
- Usage quotas to prevent abuse
- Audit logging for administrative actions

#### Open Source
- MIT License compliance
- Third-party license tracking
- Attribution for dependencies

---

### 8. Preferred tech stack

**Backend: FastAPI (Python 3.11+)**

**Rationale:**
- Native async/await (critical for concurrent LLM API calls)
- Automatic OpenAPI documentation (API-first development)
- Pydantic data validation (type-safe DTOs)
- WebSocket support built-in
- Excellent integration with existing Python AI libraries
- High performance (comparable to Node.js/Go)
- Already using Python (seamless integration with existing codebase)

**Frontend: Next.js 14+ (React, TypeScript)**

**Rationale:**
- **Server-Side Rendering** for initial load performance
- **App Router** for modern React Server Components
- **File-based routing** with intuitive structure
- **API Routes** for Backend-for-Frontend (BFF) pattern
- **Image optimization** built-in
- **TypeScript** first-class support
- **Large ecosystem** and active community
- **Vercel deployment** option (but self-hosted preferred)

**State Management:**
- **Zustand**: Lightweight UI state (theme, sidebar open/closed, form drafts)
- **TanStack Query**: Server state (caching, invalidation, optimistic updates)

**Rationale:** Zustand is simpler than Redux for UI state. TanStack Query handles server state better than Redux Toolkit Query for this use case.

**UI Components: Radix UI + Tailwind CSS**

**Rationale:**
- **Radix UI**: Accessible primitives, unstyled, composable
- **Tailwind CSS**: Utility-first styling, design system tokens
- Custom component library built on Radix primitives

**Forms: React Hook Form + Zod**

**Rationale:**
- Performance-optimized (minimal re-renders)
- Type-safe validation schemas
- Backend schema synchronization
- Excellent developer experience

**Real-Time: Socket.IO**

**Rationale:**
- WebSocket with automatic fallback (long-polling)
- Room-based broadcasting
- Connection state management
- Excellent Python and JavaScript support

**Build System: Turbo (Monorepo)**

**Rationale:**
- Parallel builds across packages
- Incremental compilation
- Shared package management
- Used by Vercel, proven at scale

**Database:**
- **PostgreSQL 15+**: Relational data (users, jobs, documents)
- **Redis 7+**: Session storage, task queue, caching
- **Existing Agno → Neuroca**: Vector embeddings (as per roadmap)

**Task Queue: Celery + Redis**

**Rationale:**
- Proven for Python async tasks
- Distributed task execution
- Result backend in Redis
- Retry mechanisms built-in

---

### 9. Do you anticipate third-party plugins or internal-only extensibility?

**Phase 1: Internal-Only Extensibility**

**Feature Module System:**
- Feature packages as npm packages within monorepo
- Dynamic feature loading based on user permissions
- Manifest-based registration (routes, nav items, permissions)
- Extension points:
  - Custom critique agents (new philosophical perspectives)
  - Research data sources (new APIs beyond current 4)
  - Export templates (custom LaTeX templates)
  - UI themes

**Example: Adding New Critique Agent**
```python
# Register new agent
from src.council.agents.base import CritiqueAgent

class EthicalAgent(CritiqueAgent):
    name = "ethical"
    perspective = "Ethical Framework Analysis"
    # Implementation...

# Auto-discovered by agent registry
```

**Phase 3+: External Plugin System (Future)**

**Requirements:**
- Third-party researcher-contributed agents
- Custom visualization components
- Domain-specific analysis tools
- Integration with external tools (Zotero, Mendeley, etc.)

**Technical Approach:**
- **Module Federation** (Webpack 5) for remote component loading
- **Sandboxed Execution** via iframe for untrusted plugins
- **Plugin Marketplace/Registry** with versioning
- **Manifest Validation** and security scanning
- **Permission System** for plugin capabilities

**Security Considerations:**
- Code signing for plugins
- Sandboxed execution environment
- Permission declarations (data access, API calls)
- User approval for plugin installation
- Audit logging for plugin actions

**Current Decision: Internal-Only**
- Sufficient for current user base
- Reduced security surface
- Faster development cycle
- Can add external plugins later without refactoring

---

### 10. CI/CD environment and hosting

**Development Environment:**

```yaml
# Docker Compose Local Setup
services:
  - PostgreSQL 15 (database)
  - Redis 7 (cache/queue)
  - FastAPI backend (hot reload)
  - Next.js frontend (dev server)
  - Celery worker (task processing)
```

**CI Pipeline (GitHub Actions):**

```yaml
Pipeline Stages:
1. Lint & Type Check:
   - ESLint (frontend)
   - TypeScript compiler
   - Ruff (Python linting)
   - Black (Python formatting)

2. Test:
   - Pytest (backend unit tests)
   - Vitest (frontend unit tests)
   - Playwright (E2E tests)
   - Coverage reporting (Codecov)

3. Security Scan:
   - Snyk/Trivy (dependency vulnerabilities)
   - CodeQL (code analysis)
   - Codacy integration (existing)

4. Build:
   - Next.js production build
   - Docker image creation (multi-stage)
   - Artifact storage

5. Deploy Preview:
   - Temporary environment for PR review
   - Automatic cleanup after merge
   - Comment with preview URL

6. Deploy Production:
   - On merge to main
   - Blue-green deployment
   - Automatic rollback on failure
```

**Production Hosting (Preferred): Self-Hosted**

**Architecture:**
```
                    ┌─────────────┐
Internet ─────────> │   Nginx     │ (SSL, caching)
                    │   (80/443)  │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────┐     ┌─────────┐    ┌─────────┐
    │FastAPI  │     │FastAPI  │    │ Next.js │
    │Worker 1 │     │Worker 2 │    │  (3000) │
    │ (8001)  │     │ (8002)  │    └─────────┘
    └─────────┘     └─────────┘
           │               │
           └───────┬───────┘
                   ▼
         ┌──────────────────┐
         │   PostgreSQL     │
         │   Redis          │
         │   Celery Workers │
         └──────────────────┘
```

**Components:**
- **Nginx**: Reverse proxy, SSL termination (Let's Encrypt), static file caching
- **FastAPI**: Multiple Uvicorn workers behind Nginx
- **Next.js**: Standalone build, served by Nginx or Node.js
- **PostgreSQL**: Managed or self-hosted with replication
- **Redis**: Single instance or Sentinel for HA
- **Celery Workers**: Separate containers for long-running tasks

**Deployment Method:**
```bash
# Docker Compose Production
docker-compose -f docker-compose.prod.yml up -d

# Or Kubernetes (future)
kubectl apply -f k8s/
```

**Alternative: Managed Services**

| Component | Self-Hosted | Managed Alternative |
|-----------|-------------|-------------------|
| Backend | VPS/Bare Metal | Railway, Render, Fly.io |
| Frontend | Same VPS | Vercel, Cloudflare Pages |
| Database | PostgreSQL on VPS | Supabase, Neon, Railway |
| Redis | Redis on VPS | Upstash, Redis Cloud |
| Storage | Local filesystem | S3, Cloudflare R2, B2 |

**Monitoring & Observability (Future):**
- Prometheus (metrics collection)
- Grafana (visualization)
- Sentry (error tracking)
- Structured logging (JSON format)

**Backup Strategy:**
- Database: Daily backups to S3-compatible storage
- Documents: Replicated storage
- Retention: 30 days rolling, longer for critical data

---

## Implementation Readiness

✅ **All 10 questions answered with concrete specifications**

✅ **Architecture document created** (`docs/FRONTEND_ARCHITECTURE.md`)

✅ **API specification documented** (`docs/api/BACKEND_API_SPEC.md`)

✅ **Implementation guide provided** (`docs/IMPLEMENTATION_GUIDE.md`)

✅ **Technology stack justified and selected**

✅ **Integration points with existing codebase identified**

✅ **Performance targets established**

✅ **Security and compliance requirements defined**

---

## Next Steps for Implementation

1. **Review & Approval**: Stakeholder review of this specification
2. **Environment Setup**: Initialize development environment (Docker Compose)
3. **Database Design**: Design PostgreSQL schema (users, jobs, documents)
4. **Backend Phase 1**: Implement authentication + user management
5. **Frontend Phase 1**: Implement auth flow + dashboard shell
6. **Feature Phase 1**: Research job creation end-to-end
7. **Feature Phase 2**: Critique workflow
8. **Feature Phase 3**: Search & discovery
9. **Polish**: Performance, accessibility, documentation
10. **Production Deployment**: Self-hosted or managed services

**Estimated Timeline:** 13-16 weeks for full implementation

---

**Document Status:** ✅ Complete  
**Ready for Implementation:** Yes  
**Last Updated:** November 23, 2025
