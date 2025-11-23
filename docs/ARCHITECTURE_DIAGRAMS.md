# Cogito Frontend Architecture - Visual Diagrams

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USERS & CLIENTS                             │
│  [Web Browser] [Mobile Browser] [API Client] [Third-Party Tools]    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   NGINX (80/443)     │
                    │  - SSL Termination   │
                    │  - Load Balancing    │
                    │  - Static Caching    │
                    └───────────┬──────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
    ┌───────────▼──────────┐      ┌────────────▼──────────┐
    │   FRONTEND (Next.js)  │      │  BACKEND (FastAPI)    │
    │                       │      │                       │
    │  • Server Components  │      │  • REST API (/api/v1) │
    │  • App Router         │      │  • WebSocket (/ws)    │
    │  • Static Assets      │      │  • OpenAPI Docs       │
    │  • Client Components  │      │  • Authentication     │
    │                       │      │                       │
    │  Port: 3000          │      │  Port: 8000           │
    └───────────┬──────────┘      └────────────┬──────────┘
                │                               │
                │       ┌───────────────────────┤
                │       │                       │
    ┌───────────▼───────▼────────┐  ┌──────────▼──────────┐
    │    STATE MANAGEMENT        │  │  TASK QUEUE         │
    │                            │  │                     │
    │  • TanStack Query (Server) │  │  • Celery Workers   │
    │  • Zustand (UI State)      │  │  • Research Jobs    │
    │  • WebSocket Client        │  │  • Critique Jobs    │
    │                            │  │  • Document Compile │
    └────────────────────────────┘  └─────────┬───────────┘
                                              │
                ┌─────────────────────────────┴───────────────┐
                │                                             │
    ┌───────────▼──────────┐    ┌──────────▼───────┐  ┌──────▼───────┐
    │   PostgreSQL (DB)    │    │  Redis (Cache)   │  │ Vector DB    │
    │                      │    │                  │  │              │
    │  • Users             │    │  • Sessions      │  │ • Agno       │
    │  • Research Jobs     │    │  • Task Queue    │  │ → Neuroca    │
    │  • Critique Jobs     │    │  • Cache         │  │              │
    │  • Documents         │    │                  │  │ • Embeddings │
    │  • API Keys          │    │  Port: 6379      │  │              │
    │                      │    │                  │  │              │
    │  Port: 5432          │    └──────────────────┘  └──────────────┘
    └──────────────────────┘
                │
    ┌───────────▼──────────────────────────────────────────┐
    │              EXTERNAL INTEGRATIONS                    │
    │                                                       │
    │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
    │  │ LLM APIs     │  │ Research DBs │  │ LaTeX      │ │
    │  │              │  │              │  │ Compiler   │ │
    │  │ • OpenAI     │  │ • ArXiv      │  │            │ │
    │  │ • Anthropic  │  │ • PubMed     │  │ • pdflatex │ │
    │  │ • Gemini     │  │ • Semantic   │  │ • bibtex   │ │
    │  │ • DeepSeek   │  │   Scholar    │  │            │ │
    │  │              │  │ • CrossRef   │  │            │ │
    │  └──────────────┘  └──────────────┘  └────────────┘ │
    └───────────────────────────────────────────────────────┘
```

## Frontend Architecture Layers

```
┌──────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Next.js App Router Pages                       │ │
│  │                                                              │ │
│  │  /app                                                        │ │
│  │  ├─ layout.tsx              (Root layout + providers)       │ │
│  │  ├─ page.tsx                (Landing page)                  │ │
│  │  ├─ auth/                   (Auth pages)                    │ │
│  │  │  ├─ login/page.tsx                                       │ │
│  │  │  └─ register/page.tsx                                    │ │
│  │  └─ (auth)/                 (Protected routes)              │ │
│  │     ├─ research/            (Research dashboard & forms)    │ │
│  │     ├─ critique/            (Critique submission & results) │ │
│  │     ├─ search/              (Literature search)             │ │
│  │     └─ profile/             (User settings)                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    COMPONENT LAYER                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    React Components                         │ │
│  │                                                              │ │
│  │  Feature Components:                                         │ │
│  │  • ResearchForm          • CritiqueUpload                   │ │
│  │  • ProgressMonitor       • ResultViewer                     │ │
│  │  • SearchFilters         • PaperCard                        │ │
│  │                                                              │ │
│  │  Shared Components (from @cogito/ui):                       │ │
│  │  • Button  • DataTable  • Modal  • Form  • ProgressBar     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    STATE MANAGEMENT LAYER                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                                                              │ │
│  │  UI State (Zustand):                                        │ │
│  │  • Theme (light/dark)    • Sidebar open/closed             │ │
│  │  • Form drafts           • Modal state                      │ │
│  │                                                              │ │
│  │  Server State (TanStack Query):                             │ │
│  │  • useResearchProjects() • useCritiqueResults()            │ │
│  │  • useSearchResults()    • useUserProfile()                │ │
│  │  • Automatic caching     • Optimistic updates              │ │
│  │                                                              │ │
│  │  Real-Time (WebSocket):                                     │ │
│  │  • useResearchProgress() • useCritiqueProgress()           │ │
│  │  • Socket.IO client      • Auto-reconnection               │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    API CLIENT LAYER                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              CogitoAPIClient (@cogito/api-client)           │ │
│  │                                                              │ │
│  │  • HTTP Client (fetch-based)                                │ │
│  │  • Authentication interceptor (JWT token injection)         │ │
│  │  • Error normalization                                      │ │
│  │  • Tracing & logging                                        │ │
│  │                                                              │ │
│  │  Domain APIs:                                               │ │
│  │  • AuthAPI       • ResearchAPI    • CritiqueAPI            │ │
│  │  • SearchAPI     • DocumentAPI    • UserAPI                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       [Backend REST API]
```

## Backend Architecture Layers (Clean Architecture)

```
┌──────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER (API)                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                FastAPI Routers (/api/v1)                    │ │
│  │                                                              │ │
│  │  • auth.py       → Authentication endpoints                 │ │
│  │  • research.py   → Research project CRUD                    │ │
│  │  • critique.py   → Critique submission & results            │ │
│  │  • search.py     → Literature search                        │ │
│  │  • documents.py  → Document management                      │ │
│  │  • users.py      → User management                          │ │
│  │                                                              │ │
│  │  WebSocket:                                                  │ │
│  │  • websocket.py  → Real-time event handlers                │ │
│  │                                                              │ │
│  │  Middleware:                                                 │ │
│  │  • Authentication  • CORS  • Logging  • Rate Limiting       │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    APPLICATION LAYER (SERVICES)                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Use Case Services                         │ │
│  │                                                              │ │
│  │  /application/research/                                      │ │
│  │  • ResearchOrchestrator   → Coordinate research pipeline   │ │
│  │  • LiteratureSearchService → Search across sources         │ │
│  │  • ThesisGenerationService → Generate academic document    │ │
│  │                                                              │ │
│  │  /application/critique/                                      │ │
│  │  • CritiqueOrchestrator   → Coordinate critique pipeline   │ │
│  │  • PhilosophicalAnalyzer  → Multi-agent critique           │ │
│  │  • ReviewSynthesizer      → Synthesize peer reviews        │ │
│  │                                                              │ │
│  │  /application/auth/                                          │ │
│  │  • AuthService            → User authentication            │ │
│  │  • TokenService           → JWT management                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    DOMAIN LAYER (MODELS)                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Domain Entities (Pure Python)                 │ │
│  │                                                              │ │
│  │  Existing (from src/domain/):                                │ │
│  │  • preflight/         → Query plans, extraction results     │ │
│  │  • user_settings/     → User preferences                    │ │
│  │                                                              │ │
│  │  New (to be added):                                          │ │
│  │  • User              → User entity                          │ │
│  │  • ResearchJob       → Research project entity              │ │
│  │  • CritiqueJob       → Critique request entity              │ │
│  │  • Document          → Document metadata entity             │ │
│  │                                                              │ │
│  │  Value Objects:                                              │ │
│  │  • Email  • Password  • JobStatus  • Permissions            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                INFRASTRUCTURE LAYER (PERSISTENCE)                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   External Integrations                      │ │
│  │                                                              │ │
│  │  ORM Models (SQLAlchemy):                                    │ │
│  │  • /models/user.py           → User table                   │ │
│  │  • /models/research_job.py   → Research jobs table          │ │
│  │  • /models/critique_job.py   → Critique jobs table          │ │
│  │  • /models/document.py       → Documents table              │ │
│  │                                                              │ │
│  │  Existing Infrastructure (from src/):                        │ │
│  │  • /research_apis/       → PubMed, Semantic Scholar, etc.  │ │
│  │  • /arxiv/               → ArXiv integration               │ │
│  │  • /council/             → Critique agents                 │ │
│  │  • /syncretic_catalyst/  → Research synthesis              │ │
│  │  • /latex/               → LaTeX compilation               │ │
│  │  • /providers/           → LLM API clients                 │ │
│  │                                                              │ │
│  │  Task Queue (Celery):                                        │ │
│  │  • /tasks/research.py    → Long-running research tasks     │ │
│  │  • /tasks/critique.py    → Long-running critique tasks     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Feature Module Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FEATURE: RESEARCH                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Feature Manifest (researchFeatureManifest)              │  │
│  │                                                           │  │
│  │  • id: 'research'                                         │  │
│  │  • version: '1.0.0'                                       │  │
│  │  • routes: [/research, /research/new, /research/:id]     │  │
│  │  • navItems: [{label: 'Research', icon, path}]          │  │
│  │  • permissions: [research.view, research.create]         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Pages (Next.js)                                          │  │
│  │                                                           │  │
│  │  • ResearchDashboard     → List projects                 │  │
│  │  • NewResearch           → Create form                   │  │
│  │  • ResearchDetail        → Progress & results            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Components                                               │  │
│  │                                                           │  │
│  │  • ResearchForm          → Input concept, config         │  │
│  │  • ResearchCard          → Project summary card          │  │
│  │  • ProgressMonitor       → Real-time progress display    │  │
│  │  • ResultViewer          → Display thesis, citations     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  State Hooks (TanStack Query)                             │  │
│  │                                                           │  │
│  │  • useResearchProjects() → List queries                  │  │
│  │  • useResearchProject()  → Single project                │  │
│  │  • useCreateResearch()   → Mutation                      │  │
│  │  • useResearchProgress() → WebSocket subscription        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Service (ResearchAPI)                                │  │
│  │                                                           │  │
│  │  • list(params)          → GET /research                 │  │
│  │  • get(id)               → GET /research/:id             │  │
│  │  • create(data)          → POST /research                │  │
│  │  • refine(id, data)      → POST /research/:id/refine     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Similar structure for:
• FEATURE: CRITIQUE
• FEATURE: SEARCH
• FEATURE: DOCUMENTS
• FEATURE: PROFILE
```

## Authentication Flow

```
┌─────────────┐                ┌─────────────┐               ┌─────────────┐
│   Browser   │                │  Next.js    │               │  FastAPI    │
│             │                │  Frontend   │               │  Backend    │
└──────┬──────┘                └──────┬──────┘               └──────┬──────┘
       │                              │                              │
       │  1. Visit /auth/login        │                              │
       ├─────────────────────────────►│                              │
       │                              │                              │
       │  2. Render login form        │                              │
       │◄─────────────────────────────┤                              │
       │                              │                              │
       │  3. Submit credentials       │                              │
       ├─────────────────────────────►│                              │
       │    (email, password)         │                              │
       │                              │  4. POST /auth/login         │
       │                              ├─────────────────────────────►│
       │                              │    (email, password)         │
       │                              │                              │
       │                              │  5. Verify credentials       │
       │                              │     Hash password            │
       │                              │     Generate JWT             │
       │                              │                              │
       │                              │  6. Return tokens            │
       │                              │◄─────────────────────────────┤
       │                              │    {access_token,            │
       │                              │     refresh_token, user}     │
       │  7. Store tokens             │                              │
       │    (localStorage/cookies)    │                              │
       │                              │                              │
       │  8. Redirect to /research    │                              │
       │◄─────────────────────────────┤                              │
       │                              │                              │
       │  9. Request protected page   │                              │
       ├─────────────────────────────►│                              │
       │                              │                              │
       │                              │  10. API call with token     │
       │                              ├─────────────────────────────►│
       │                              │     Authorization:           │
       │                              │     Bearer {access_token}    │
       │                              │                              │
       │                              │  11. Verify JWT              │
       │                              │      Extract user_id         │
       │                              │      Check permissions       │
       │                              │                              │
       │                              │  12. Return data             │
       │                              │◄─────────────────────────────┤
       │                              │                              │
       │  13. Render protected page   │                              │
       │◄─────────────────────────────┤                              │
       │                              │                              │
       
       [15 minutes later - Token Expiry]
       
       │                              │  14. API call fails (401)    │
       │                              ├─────────────────────────────►│
       │                              │                              │
       │                              │  15. Token expired           │
       │                              │◄─────────────────────────────┤
       │                              │                              │
       │                              │  16. POST /auth/refresh      │
       │                              ├─────────────────────────────►│
       │                              │     {refresh_token}          │
       │                              │                              │
       │                              │  17. New access token        │
       │                              │◄─────────────────────────────┤
       │                              │                              │
       │                              │  18. Retry original request  │
       │                              ├─────────────────────────────►│
       │                              │     Authorization: Bearer... │
       │                              │                              │
       │                              │  19. Success                 │
       │                              │◄─────────────────────────────┤
       │                              │                              │
```

## Research Pipeline Flow

```
┌───────────┐       ┌──────────┐       ┌──────────┐       ┌───────────┐
│  Browser  │       │ Next.js  │       │ FastAPI  │       │  Celery   │
│           │       │ Frontend │       │ Backend  │       │  Worker   │
└─────┬─────┘       └────┬─────┘       └────┬─────┘       └─────┬─────┘
      │                  │                   │                   │
      │  1. Fill form    │                   │                   │
      │  (concept, cfg)  │                   │                   │
      ├─────────────────►│                   │                   │
      │                  │                   │                   │
      │                  │  2. POST /research│                   │
      │                  ├──────────────────►│                   │
      │                  │                   │                   │
      │                  │                   │  3. Create job    │
      │                  │                   │     (status:      │
      │                  │                   │      pending)     │
      │                  │                   │                   │
      │                  │                   │  4. Enqueue task  │
      │                  │                   ├──────────────────►│
      │                  │                   │                   │
      │                  │  5. Return job ID │                   │
      │                  │◄──────────────────┤                   │
      │                  │    {id, status}   │                   │
      │                  │                   │                   │
      │  6. Redirect to  │                   │                   │
      │     /research/ID │                   │                   │
      │◄─────────────────┤                   │                   │
      │                  │                   │                   │
      │  7. Connect WS   │                   │                   │
      │                  │  8. WS subscribe  │                   │
      │                  ├──────────────────►│                   │
      │                  │    research:ID    │                   │
      │                  │                   │                   │
      │                  │                   │  9. Start work    │
      │                  │                   │     (status:      │
      │                  │                   │      running)     │
      │                  │                   │                   │
      │                  │                   │  10. Emit progress│
      │                  │                   │◄──────────────────┤
      │                  │                   │     "Searching    │
      │                  │                   │      literature"  │
      │                  │  11. WS event     │                   │
      │                  │◄──────────────────┤                   │
      │                  │   {stage: lit,    │                   │
      │                  │    progress: 25%} │                   │
      │  12. Update UI   │                   │                   │
      │◄─────────────────┤                   │                   │
      │  [Progress Bar]  │                   │                   │
      │                  │                   │                   │
      │                  │                   │  13. Continue...  │
      │                  │                   │      (agents,     │
      │                  │                   │       document    │
      │                  │                   │       generation) │
      │                  │                   │                   │
      │                  │                   │  14. Complete     │
      │                  │                   │      (status:     │
      │                  │                   │       completed)  │
      │                  │                   │                   │
      │                  │                   │  15. Emit complete│
      │                  │                   │◄──────────────────┤
      │                  │                   │     {results,     │
      │                  │                   │      files}       │
      │                  │  16. WS event     │                   │
      │                  │◄──────────────────┤                   │
      │                  │   {status: done,  │                   │
      │                  │    results: {...}}│                   │
      │  17. Show results│                   │                   │
      │◄─────────────────┤                   │                   │
      │  [Download PDF]  │                   │                   │
      │                  │                   │                   │
```

## Data Flow - Research Creation

```
                     User Input
                         │
                         ▼
              ┌─────────────────────┐
              │   ResearchForm      │
              │  (React Component)  │
              └──────────┬──────────┘
                         │ onSubmit
                         ▼
              ┌─────────────────────┐
              │  useCreateResearch  │
              │  (TanStack Query)   │
              └──────────┬──────────┘
                         │ mutate
                         ▼
              ┌─────────────────────┐
              │   ResearchAPI       │
              │  (@cogito/api-client│
              └──────────┬──────────┘
                         │ POST /api/v1/research
                         ▼
              ┌─────────────────────┐
              │  FastAPI Router     │
              │  (research.py)      │
              └──────────┬──────────┘
                         │ Validate (Pydantic)
                         ▼
              ┌─────────────────────┐
              │ ResearchOrchestrator│
              │  (Application)      │
              └──────────┬──────────┘
                         │ Create entity
                         ▼
              ┌─────────────────────┐
              │  ResearchJob Model  │
              │  (SQLAlchemy ORM)   │
              └──────────┬──────────┘
                         │ Save to DB
                         ▼
              ┌─────────────────────┐
              │    PostgreSQL       │
              │  (research_jobs     │
              │   table)            │
              └──────────┬──────────┘
                         │ Job ID
                         ▼
              ┌─────────────────────┐
              │   Celery Task       │
              │  (research.py)      │
              └──────────┬──────────┘
                         │ Enqueue
                         ▼
              ┌─────────────────────┐
              │      Redis          │
              │  (Task Queue)       │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Celery Worker     │
              │                     │
              │  1. Literature      │
              │     Search          │
              │  2. Agent Synthesis │
              │  3. Document Gen    │
              └──────────┬──────────┘
                         │ Emit progress
                         ▼
              ┌─────────────────────┐
              │   Socket.IO Server  │
              │  (WebSocket)        │
              └──────────┬──────────┘
                         │ Broadcast
                         ▼
              ┌─────────────────────┐
              │   Socket.IO Client  │
              │  (Frontend WS)      │
              └──────────┬──────────┘
                         │ Update state
                         ▼
              ┌─────────────────────┐
              │  ProgressMonitor    │
              │  (React Component)  │
              └─────────────────────┘
                         │
                         ▼
                     User sees
                   live progress
```

---

## Monorepo Package Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                       Root (/)                               │
│  • package.json (workspaces)                                 │
│  • turbo.json (build pipeline)                               │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────┐        ┌──────────────┐
│ apps/web     │        │ apps/api     │
│ (Next.js)    │        │ (FastAPI)    │
└───────┬──────┘        └──────────────┘
        │
        ├─ depends on ─┐
        │              │
        ▼              ▼
┌──────────────┐  ┌──────────────┐
│ packages/ui  │  │ packages/    │
│ (Components) │  │ api-client   │
└──────┬───────┘  └──────┬───────┘
       │                 │
       │                 │
       └─── depends on ──┤
                         │
                         ▼
                  ┌──────────────┐
                  │ packages/    │
                  │ types        │
                  │ (Shared TS)  │
                  └──────────────┘

Build Order (Turbo):
1. packages/types
2. packages/api-client (depends on types)
3. packages/ui (depends on types)
4. apps/web (depends on ui, api-client, types)
```

---

**These diagrams provide visual reference for the architecture described in the main documentation.**
