# Cogito Frontend Architecture Specification

**Version:** 1.0  
**Date:** November 23, 2025  
**Status:** Implementation Ready

---

## Executive Summary

This document specifies a comprehensive, extensible front-end architecture for the Cogito AI research platform. Based on thorough backend analysis, this architecture provides full feature coverage, modular expansion capabilities, and production-ready patterns aligned with Clean Architecture principles.

---

## Backend Specification Answers

### 1. Protocols Exposed

**Primary Protocol:** REST API via FastAPI
- **Endpoints:** RESTful resources for CRUD operations
- **Real-time:** WebSocket connections for:
  - Research pipeline progress updates
  - Streaming critique results
  - Live thesis generation status
  - Agent activity monitoring
- **File Transfer:** Multipart form-data for document uploads
- **Export:** Binary responses for PDF/LaTeX downloads

**Future Consideration:** GraphQL for complex query optimization (Phase 3+)

### 2. Authentication & Authorization

**Implementation:** OAuth2 + JWT (JSON Web Tokens)

**Flow:**
```
User → Login → FastAPI OAuth2 → JWT Access Token (15min) + Refresh Token (7 days)
     → Subsequent requests include Bearer token
     → Token refresh on expiry
     → Session invalidation on logout
```

**Authorization Levels:**
- **Anonymous:** Read-only access to public research outputs
- **Researcher:** Full access to research tools, personal workspace
- **Admin:** User management, system configuration, usage analytics
- **API Key:** Programmatic access for integrations

**Security Features:**
- Password hashing (bcrypt/argon2)
- Rate limiting per user/IP
- CORS configuration
- API key management for external integrations

### 3. Core Feature Domains

#### A. Research Synthesis (Syncretic Catalyst)
**Capabilities:**
- Concept-to-thesis generation
- Multi-agent research orchestration
- ArXiv + multi-database literature search
- Academic document production (LaTeX/PDF)

**API Endpoints:**
- `POST /api/v1/research/initiate` - Start research project
- `GET /api/v1/research/{id}/status` - Progress tracking
- `GET /api/v1/research/{id}/results` - Retrieve outputs
- `POST /api/v1/research/{id}/refine` - Iterative refinement
- `WS /api/v1/research/{id}/stream` - Real-time updates

#### B. Critique & Review (Council of Critics)
**Capabilities:**
- Philosophical critique generation
- Scientific peer review synthesis
- Multi-perspective analysis
- Confidence scoring & arbitration

**API Endpoints:**
- `POST /api/v1/critique/submit` - Upload document for critique
- `POST /api/v1/critique/directory` - Batch directory processing
- `GET /api/v1/critique/{id}/report` - Retrieve critique
- `POST /api/v1/critique/{id}/regenerate` - Re-run with options
- `GET /api/v1/critique/{id}/download` - PDF/LaTeX export

#### C. Literature Search & Discovery
**Capabilities:**
- Unified search across ArXiv, PubMed, Semantic Scholar, CrossRef
- Vector-based semantic search
- Citation graph traversal
- Research gap identification

**API Endpoints:**
- `POST /api/v1/search/query` - Execute research query
- `POST /api/v1/search/semantic` - Vector similarity search
- `GET /api/v1/search/{id}/results` - Paginated results
- `POST /api/v1/search/citations` - Citation expansion

#### D. Document Generation & Management
**Capabilities:**
- LaTeX compilation
- PDF generation with citations
- BibTeX management
- Template customization

**API Endpoints:**
- `POST /api/v1/documents/compile` - Compile LaTeX to PDF
- `GET /api/v1/documents/{id}/preview` - Document preview
- `GET /api/v1/documents/{id}/download` - Download artifacts
- `GET /api/v1/templates` - List available templates

#### E. User Management & Preferences
**Capabilities:**
- User profile management
- API key generation
- Usage quota tracking
- Preference persistence

**API Endpoints:**
- `GET /api/v1/users/me` - Current user profile
- `PATCH /api/v1/users/me` - Update preferences
- `POST /api/v1/users/api-keys` - Generate API key
- `GET /api/v1/users/usage` - Usage statistics

#### F. System Configuration & Administration
**Capabilities:**
- LLM provider configuration
- System health monitoring
- User administration
- Usage analytics

**API Endpoints:**
- `GET /api/v1/admin/config` - System configuration
- `PATCH /api/v1/admin/config` - Update configuration
- `GET /api/v1/admin/users` - User management
- `GET /api/v1/admin/metrics` - System metrics

### 4. Real-Time Requirements

**Critical Real-Time Features:**
- **Research Pipeline Progress:** Multi-stage progress updates (literature search, agent synthesis, document generation)
- **Critique Generation:** Streaming critique results as philosophical agents complete analysis
- **Literature Discovery:** Live result streaming during semantic search
- **System Notifications:** User alerts, quota warnings, job completions

**Technical Implementation:**
- WebSocket connections per active job
- Server-Sent Events (SSE) for notifications
- Optimistic UI updates with reconciliation
- Automatic reconnection with exponential backoff

### 5. Multi-Tenant Concerns

**Current Phase:** Single-tenant optimized (individual researcher workstations)

**Future Considerations:**
- Workspace isolation (shared institutional deployment)
- Resource quota enforcement per workspace
- Collaborative research projects (shared access to research artifacts)
- Per-workspace configuration (LLM providers, API keys)

**Data Isolation:**
- User ID in all database records
- Query-level filtering enforced at ORM level
- File storage segregated by user namespace

### 6. Scale & Performance Constraints

**Expected Scale:**
- **Concurrent Users:** 10-50 researchers (Phase 1), 100-500 (Phase 2)
- **Data Volume:** 
  - Vector database: 100K-1M paper embeddings
  - Document storage: 10-100GB research outputs
  - Session data: Ephemeral, Redis-backed
- **Request Profile:**
  - Synchronous API: 10-100 req/sec
  - Long-running jobs: 1-10 concurrent research pipelines
  - WebSocket: 10-50 active connections

**Performance Targets:**
- API response: <200ms (p95) for CRUD operations
- Research initiation: <1s acknowledgment
- Literature search: <5s for initial results
- UI load: <2s First Contentful Paint (FCP)
- Real-time latency: <500ms update propagation

**Resource Constraints:**
- CPU-intensive: LLM API calls, LaTeX compilation (offload to workers)
- Memory-intensive: Vector similarity calculations (batch processing)
- I/O-intensive: Paper PDF retrieval, result serialization

### 7. Accessibility & Compliance

**Accessibility Targets:**
- **WCAG 2.1 Level AA** compliance
- Keyboard navigation throughout
- Screen reader compatibility (ARIA labels, landmarks)
- High contrast mode support
- Responsive typography (scalable fonts)

**Internationalization:**
- **Phase 1:** English only
- **Phase 2+:** Locale framework for UI strings
- Research outputs remain in source language (English-centric academic corpus)

**Compliance:**
- Data privacy: No PII collected beyond email/username
- API rate limiting for responsible AI usage
- Audit logging for administrative actions
- Open-source license compliance (MIT)

### 8. Preferred Tech Stack

**Backend:** FastAPI (Python)
- Native async/await support
- Automatic OpenAPI documentation
- Pydantic data validation
- WebSocket support
- Excellent Python AI library integration

**Frontend:** Next.js 14+ (React, TypeScript)
- Server-side rendering for initial load performance
- File-based routing with App Router
- API routes for BFF (Backend for Frontend) pattern
- Image optimization
- Built-in TypeScript support

**State Management:** Zustand + TanStack Query
- Zustand: Lightweight, simple, sufficient for UI state
- TanStack Query: Server state caching, invalidation, optimistic updates

**UI Components:** Radix UI + Tailwind CSS
- Radix: Accessible primitives, unstyled
- Tailwind: Utility-first styling, design system tokens
- Custom component library built on primitives

**Forms:** React Hook Form + Zod
- Type-safe validation schemas
- Performance-optimized re-renders
- Backend schema synchronization

**Real-Time:** Socket.IO (client + server)
- WebSocket with automatic fallback (polling)
- Room-based broadcasting
- Connection state management

**Build System:** Turbo (Monorepo orchestration)
- Shared packages: `@cogito/ui`, `@cogito/api-client`, `@cogito/types`
- Parallel builds
- Incremental compilation

### 9. Extensibility

**Plugin Architecture:** Internal-only (Phase 1)
- Feature modules as npm packages within monorepo
- Dynamic feature loading based on user permissions/license
- Extension points: Custom critique agents, data sources, export templates

**Future External Plugins (Phase 3+):**
- Module Federation for remote components
- Sandboxed plugin execution
- Plugin marketplace/registry

### 10. CI/CD & Hosting

**Development Environment:**
- Docker Compose: Backend (FastAPI), Frontend (Next.js dev server), Redis, PostgreSQL
- Hot reload for both frontend and backend

**CI Pipeline (GitHub Actions):**
1. **Lint & Type Check:** ESLint, TypeScript, Ruff (Python)
2. **Test:** Jest (frontend unit), Pytest (backend), Playwright (E2E)
3. **Build:** Next.js production build, Docker image creation
4. **Security Scan:** Snyk/Trivy for dependencies, CodeQL for code
5. **Deploy Preview:** Temporary environment for PR review

**Production Hosting:**
- **Self-Hosted (Preferred):** Docker Compose on VPS/bare metal
  - Nginx reverse proxy (SSL termination, caching)
  - Backend: Uvicorn workers behind Nginx
  - Frontend: Next.js standalone output
  - Database: PostgreSQL + Redis
  - Storage: Local filesystem or S3-compatible
- **Alternative:** 
  - Backend: Railway/Render
  - Frontend: Vercel/Cloudflare Pages
  - Database: Managed PostgreSQL (Supabase/Neon)

---

## Architecture Design

### Technology Stack Summary

```yaml
Backend:
  Framework: FastAPI 0.104+
  Language: Python 3.11+
  Database: PostgreSQL 15+ (relational)
  Cache: Redis 7+ (sessions, job queues)
  Vector DB: Existing Agno → Neuroca (as per roadmap)
  Task Queue: Celery + Redis (long-running research jobs)
  WebSocket: Socket.IO (python-socketio)

Frontend:
  Framework: Next.js 14+ (App Router)
  Language: TypeScript 5+
  State: Zustand (UI), TanStack Query (server)
  UI: Radix UI + Tailwind CSS 3+
  Forms: React Hook Form + Zod
  Real-time: Socket.IO client
  Build: Turbo (monorepo)

Testing:
  Unit: Vitest (frontend), Pytest (backend)
  Integration: Playwright (E2E), MSW (API mocking)
  Quality: ESLint, TypeScript strict, Ruff, Codacy

Infrastructure:
  Containerization: Docker + Docker Compose
  Reverse Proxy: Nginx
  CI/CD: GitHub Actions
  Monitoring: Prometheus + Grafana (future)
```

### Project Structure (Monorepo)

```
cogito/
├─ apps/
│  ├─ web/                      # Next.js frontend application
│  │  ├─ app/                   # App router pages
│  │  │  ├─ (auth)/             # Auth-protected routes
│  │  │  │  ├─ research/        # Research synthesis UI
│  │  │  │  ├─ critique/        # Critique workflow UI
│  │  │  │  ├─ search/          # Literature search UI
│  │  │  │  └─ profile/         # User settings
│  │  │  ├─ api/                # API routes (BFF)
│  │  │  ├─ auth/               # Auth pages
│  │  │  └─ layout.tsx          # Root layout
│  │  ├─ components/            # Page-specific components
│  │  ├─ lib/                   # Utilities, hooks
│  │  ├─ public/                # Static assets
│  │  └─ styles/                # Global styles
│  │
│  └─ api/                      # FastAPI backend application
│     ├─ main.py                # Application entry point
│     ├─ api/                   # API layer (presentation)
│     │  ├─ v1/                 # Version 1 endpoints
│     │  │  ├─ auth.py          # Authentication routes
│     │  │  ├─ research.py      # Research endpoints
│     │  │  ├─ critique.py      # Critique endpoints
│     │  │  ├─ search.py        # Search endpoints
│     │  │  ├─ documents.py     # Document management
│     │  │  └─ users.py         # User management
│     │  ├─ dependencies.py     # Dependency injection
│     │  ├─ middleware.py       # Auth, CORS, logging
│     │  └─ websocket.py        # WebSocket handlers
│     ├─ application/           # Application services (use cases)
│     │  ├─ research/           # Research orchestration
│     │  ├─ critique/           # Critique orchestration
│     │  ├─ search/             # Search coordination
│     │  └─ auth/               # Auth services
│     ├─ domain/                # Domain models (existing)
│     ├─ infrastructure/        # External integrations (existing)
│     ├─ models/                # ORM models (SQLAlchemy)
│     │  ├─ user.py
│     │  ├─ research_job.py
│     │  ├─ critique_job.py
│     │  └─ document.py
│     ├─ schemas/               # Pydantic schemas (DTOs)
│     │  ├─ auth.py
│     │  ├─ research.py
│     │  ├─ critique.py
│     │  └─ user.py
│     ├─ core/                  # Core utilities
│     │  ├─ config.py           # Settings management
│     │  ├─ security.py         # JWT, password hashing
│     │  └─ database.py         # DB session management
│     └─ tasks/                 # Celery background tasks
│        ├─ research.py         # Research pipeline tasks
│        └─ critique.py         # Critique pipeline tasks
│
├─ packages/
│  ├─ ui/                       # Shared UI component library
│  │  ├─ src/
│  │  │  ├─ components/         # Reusable components
│  │  │  │  ├─ Button/
│  │  │  │  ├─ DataTable/
│  │  │  │  ├─ Form/
│  │  │  │  ├─ Modal/
│  │  │  │  └─ ProgressBar/
│  │  │  ├─ hooks/              # Shared hooks
│  │  │  ├─ utils/              # Helper functions
│  │  │  └─ theme/              # Design tokens
│  │  └─ package.json
│  │
│  ├─ api-client/               # TypeScript API client
│  │  ├─ src/
│  │  │  ├─ client.ts           # Base HTTP client
│  │  │  ├─ auth.ts             # Auth methods
│  │  │  ├─ research.ts         # Research API
│  │  │  ├─ critique.ts         # Critique API
│  │  │  ├─ search.ts           # Search API
│  │  │  ├─ types.ts            # Generated types
│  │  │  └─ websocket.ts        # WebSocket client
│  │  └─ package.json
│  │
│  ├─ types/                    # Shared TypeScript types
│  │  ├─ src/
│  │  │  ├─ api.ts              # API request/response types
│  │  │  ├─ domain.ts           # Domain models
│  │  │  └─ events.ts           # WebSocket event types
│  │  └─ package.json
│  │
│  └─ config/                   # Shared configuration
│     ├─ eslint/
│     ├─ typescript/
│     └─ tailwind/
│
├─ docs/                        # Documentation
│  ├─ api/                      # API documentation
│  ├─ architecture/             # Architecture diagrams
│  ├─ user-guide/               # User documentation
│  └─ development/              # Developer guides
│
├─ scripts/                     # Build/deployment scripts
│  ├─ setup.sh                  # Initial setup
│  ├─ codegen.sh                # OpenAPI client generation
│  └─ deploy.sh                 # Deployment automation
│
├─ docker/                      # Docker configurations
│  ├─ Dockerfile.api
│  ├─ Dockerfile.web
│  └─ docker-compose.yml
│
├─ .github/
│  └─ workflows/                # CI/CD pipelines
│     ├─ ci.yml                 # Lint, test, build
│     ├─ deploy-preview.yml     # PR preview deployments
│     └─ deploy-prod.yml        # Production deployment
│
├─ turbo.json                   # Turbo configuration
├─ package.json                 # Root package.json
└─ README.md
```

---

## Modular Feature Architecture

### Feature Manifest Pattern

Each feature domain is a self-contained module with standardized exports:

```typescript
// packages/ui/src/features/research/manifest.ts
export interface FeatureManifest {
  id: string;
  version: string;
  name: string;
  description: string;
  routes: RouteDef[];
  navItems: NavItem[];
  permissions: PermissionDef[];
  dependencies?: string[];
}

export const researchFeatureManifest: FeatureManifest = {
  id: 'research',
  version: '1.0.0',
  name: 'Research Synthesis',
  description: 'Syncretic Catalyst research generation',
  routes: [
    {
      path: '/research',
      component: lazy(() => import('./pages/ResearchDashboard')),
      permission: 'research.view',
    },
    {
      path: '/research/new',
      component: lazy(() => import('./pages/NewResearch')),
      permission: 'research.create',
    },
    {
      path: '/research/:id',
      component: lazy(() => import('./pages/ResearchDetail')),
      permission: 'research.view',
    },
  ],
  navItems: [
    {
      label: 'Research',
      icon: 'FlaskConical',
      path: '/research',
      permission: 'research.view',
    },
  ],
  permissions: [
    { key: 'research.view', description: 'View research projects' },
    { key: 'research.create', description: 'Create research projects' },
    { key: 'research.delete', description: 'Delete research projects' },
  ],
};
```

### Feature Registration

```typescript
// apps/web/lib/features/registry.ts
import { researchFeatureManifest } from '@cogito/ui/features/research';
import { critiqueFeatureManifest } from '@cogito/ui/features/critique';
import { searchFeatureManifest } from '@cogito/ui/features/search';

export const featureRegistry = new FeatureRegistry([
  researchFeatureManifest,
  critiqueFeatureManifest,
  searchFeatureManifest,
]);

// Filter features based on user permissions
export function getEnabledFeatures(userPermissions: string[]): FeatureManifest[] {
  return featureRegistry.getFeatures().filter(feature =>
    feature.permissions.some(p => userPermissions.includes(p.key))
  );
}

// Generate navigation from features
export function generateNavigation(features: FeatureManifest[]): NavItem[] {
  return features.flatMap(f => f.navItems);
}
```

### Vertical Expansion (Feature Depth)

Adding new capabilities within an existing feature:

```typescript
// New capability: Research templates
export interface ResearchTemplate {
  id: string;
  name: string;
  description: string;
  defaultConfig: ResearchConfig;
}

// Add to existing feature manifest
researchFeatureManifest.capabilities.push({
  id: 'templates',
  routes: [
    { path: '/research/templates', component: TemplateList },
    { path: '/research/templates/:id', component: TemplateDetail },
  ],
  permissions: ['research.templates.view', 'research.templates.manage'],
});
```

### Horizontal Expansion (New Features)

Adding an entirely new feature domain:

```bash
# Create new feature package
npx create-feature @cogito/features/analytics

# Implement manifest
# apps/web/lib/features/registry.ts
import { analyticsFeatureManifest } from '@cogito/ui/features/analytics';
featureRegistry.register(analyticsFeatureManifest);
```

---

## Data Access Layer

### Unified API Client

```typescript
// packages/api-client/src/client.ts
export class CogitoAPIClient {
  private http: HTTPClient;
  
  constructor(config: APIConfig) {
    this.http = new HTTPClient({
      baseURL: config.baseURL,
      timeout: config.timeout,
      interceptors: {
        request: [authInterceptor, tracingInterceptor],
        response: [errorNormalizationInterceptor],
      },
    });
  }
  
  // Convenience accessors
  get research() { return new ResearchAPI(this.http); }
  get critique() { return new CritiqueAPI(this.http); }
  get search() { return new SearchAPI(this.http); }
  get auth() { return new AuthAPI(this.http); }
  get users() { return new UsersAPI(this.http); }
}

// Usage in React components
export function useAPIClient() {
  const { token } = useAuth();
  return useMemo(() => new CogitoAPIClient({ 
    baseURL: '/api/v1',
    token 
  }), [token]);
}
```

### TanStack Query Integration

```typescript
// apps/web/lib/queries/research.ts
export function useResearchProjects() {
  const api = useAPIClient();
  
  return useQuery({
    queryKey: ['research', 'projects'],
    queryFn: () => api.research.list(),
    staleTime: 60_000, // 1 minute
  });
}

export function useResearchProject(id: string) {
  const api = useAPIClient();
  
  return useQuery({
    queryKey: ['research', 'project', id],
    queryFn: () => api.research.get(id),
    enabled: !!id,
  });
}

export function useCreateResearch() {
  const api = useAPIClient();
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateResearchRequest) => api.research.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research', 'projects'] });
    },
  });
}
```

### WebSocket Integration

```typescript
// packages/api-client/src/websocket.ts
export class WebSocketClient {
  private socket: Socket;
  
  connect(token: string) {
    this.socket = io('/api/v1/ws', {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
  }
  
  subscribeToResearch(researchId: string, handler: (event: ResearchEvent) => void) {
    this.socket.emit('subscribe', { topic: `research:${researchId}` });
    this.socket.on(`research:${researchId}:update`, handler);
    
    return () => {
      this.socket.off(`research:${researchId}:update`, handler);
      this.socket.emit('unsubscribe', { topic: `research:${researchId}` });
    };
  }
}

// React hook
export function useResearchProgress(researchId: string) {
  const [progress, setProgress] = useState<ResearchProgress | null>(null);
  const ws = useWebSocket();
  
  useEffect(() => {
    return ws.subscribeToResearch(researchId, (event) => {
      if (event.type === 'progress') {
        setProgress(event.data);
      }
    });
  }, [researchId, ws]);
  
  return progress;
}
```

---

## Schema-Driven UI Generation

### Backend Schema Export

```python
# apps/api/api/v1/research.py
from pydantic import BaseModel, Field

class ResearchConfig(BaseModel):
    """Research configuration schema"""
    concept: str = Field(..., description="Research concept or hypothesis")
    max_papers: int = Field(10, ge=1, le=100, description="Maximum papers to retrieve")
    include_historical: bool = Field(True, description="Include historical research")
    agents: list[str] = Field(default_factory=lambda: ['historical', 'modern', 'methodological'])

# Export as JSON Schema
@router.get("/research/config/schema")
async def get_research_config_schema():
    return ResearchConfig.schema()
```

### Frontend Dynamic Form Generation

```typescript
// apps/web/components/research/DynamicResearchForm.tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

export function DynamicResearchForm() {
  const { data: schema } = useQuery({
    queryKey: ['research', 'config', 'schema'],
    queryFn: () => api.research.getConfigSchema(),
  });
  
  // Convert JSON Schema to Zod schema
  const zodSchema = useMemo(() => 
    jsonSchemaToZod(schema),
    [schema]
  );
  
  const form = useForm({
    resolver: zodResolver(zodSchema),
  });
  
  // Render form fields dynamically
  return (
    <Form {...form}>
      {Object.entries(schema.properties).map(([key, fieldSchema]) => (
        <DynamicFormField
          key={key}
          name={key}
          schema={fieldSchema}
          control={form.control}
        />
      ))}
    </Form>
  );
}
```

---

## Authentication & Permission System

### Backend JWT Implementation

```python
# apps/api/core/security.py
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    user_id: str = payload.get("sub")
    user = await users_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=401)
    return user
```

### Frontend Auth Context

```typescript
// apps/web/lib/auth/AuthProvider.tsx
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    // Restore session from token
    const token = getStoredToken();
    if (token) {
      verifyAndRestoreSession(token).then(setUser);
    }
    setLoading(false);
  }, []);
  
  const login = async (email: string, password: string) => {
    const { access_token, user } = await api.auth.login(email, password);
    storeToken(access_token);
    setUser(user);
  };
  
  const logout = async () => {
    await api.auth.logout();
    clearToken();
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

### Permission-Based Rendering

```typescript
// packages/ui/src/components/Permission.tsx
export function Require({ 
  permission, 
  children,
  fallback = null 
}: RequireProps) {
  const { user } = useAuth();
  
  const hasPermission = user?.permissions.includes(permission);
  
  return hasPermission ? <>{children}</> : <>{fallback}</>;
}

// Usage
<Require permission="research.create">
  <Button onClick={createResearch}>New Research</Button>
</Require>
```

---

## Design System & Theming

### Design Tokens

```typescript
// packages/ui/src/theme/tokens.ts
export const tokens = {
  colors: {
    primary: {
      50: '#f0f9ff',
      500: '#0ea5e9',
      900: '#0c4a6e',
    },
    semantic: {
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    },
  },
  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
  },
  typography: {
    fontFamily: {
      sans: 'Inter, system-ui, sans-serif',
      mono: 'JetBrains Mono, monospace',
    },
    fontSize: {
      xs: '0.75rem',
      sm: '0.875rem',
      base: '1rem',
      lg: '1.125rem',
      xl: '1.25rem',
      '2xl': '1.5rem',
    },
  },
  borderRadius: {
    sm: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    full: '9999px',
  },
};
```

### Tailwind Configuration

```javascript
// packages/config/tailwind/tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: tokens.colors.primary,
      },
      spacing: tokens.spacing,
      fontFamily: tokens.typography.fontFamily,
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
};
```

### Component Example

```typescript
// packages/ui/src/components/Button/Button.tsx
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2',
  {
    variants: {
      variant: {
        primary: 'bg-primary-500 text-white hover:bg-primary-600',
        secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
        ghost: 'hover:bg-gray-100',
      },
      size: {
        sm: 'h-9 px-3 text-sm',
        md: 'h-10 px-4',
        lg: 'h-11 px-8',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}
```

---

## Testing Strategy

### Backend Testing

```python
# apps/api/tests/test_research_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_research_project(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/research",
        json={
            "concept": "Quantum computing applications in drug discovery",
            "max_papers": 20,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "pending"
```

### Frontend Unit Testing

```typescript
// apps/web/components/research/__tests__/ResearchForm.test.tsx
import { render, screen, userEvent } from '@testing-library/react';
import { ResearchForm } from '../ResearchForm';

describe('ResearchForm', () => {
  it('submits research with valid input', async () => {
    const onSubmit = vi.fn();
    render(<ResearchForm onSubmit={onSubmit} />);
    
    await userEvent.type(
      screen.getByLabelText(/concept/i),
      'Quantum computing'
    );
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    
    expect(onSubmit).toHaveBeenCalledWith({
      concept: 'Quantum computing',
      max_papers: 10,
    });
  });
});
```

### E2E Testing

```typescript
// tests/e2e/research-workflow.spec.ts
import { test, expect } from '@playwright/test';

test('complete research workflow', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name="email"]', 'researcher@example.com');
  await page.fill('[name="password"]', 'password');
  await page.click('button[type="submit"]');
  
  await expect(page).toHaveURL('/research');
  
  await page.click('text=New Research');
  await page.fill('[name="concept"]', 'AI ethics frameworks');
  await page.click('button:has-text("Start Research")');
  
  await expect(page.locator('.progress-bar')).toBeVisible();
  await expect(page.locator('.status')).toContainText('Searching literature');
});
```

### API Mocking (MSW)

```typescript
// apps/web/mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  rest.post('/api/v1/research', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: '123',
        status: 'pending',
        concept: req.body.concept,
      })
    );
  }),
  
  rest.get('/api/v1/research/:id', (req, res, ctx) => {
    return res(
      ctx.json({
        id: req.params.id,
        status: 'completed',
        results: { /* ... */ },
      })
    );
  }),
];
```

---

## Error Handling & Observability

### Backend Error Normalization

```python
# apps/api/api/middleware.py
from fastapi import Request, status
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    
    logger.error(
        "Unhandled exception",
        extra={
            "error_id": error_id,
            "path": request.url.path,
            "method": request.method,
            "exception": str(exc),
        },
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "id": error_id,
                "type": "internal_server_error",
                "message": "An unexpected error occurred",
            }
        },
    )
```

### Frontend Error Boundary

```typescript
// apps/web/components/ErrorBoundary.tsx
export class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logger.error('React error boundary caught error', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
    });
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

### Structured Logging

```typescript
// apps/web/lib/logger.ts
export const logger = {
  error: (message: string, context?: Record<string, any>) => {
    console.error(message, {
      timestamp: new Date().toISOString(),
      level: 'error',
      ...context,
    });
    
    // Send to external service in production
    if (process.env.NODE_ENV === 'production') {
      sendToLogService({ message, ...context });
    }
  },
};
```

---

## Deployment Configuration

### Docker Compose

```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://cogito:password@postgres:5432/cogito
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ../src:/app/src
      - ./latex_output:/app/latex_output

  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - api

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=cogito
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=cogito
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - api
      - web

volumes:
  postgres_data:
  redis_data:
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          npm ci
          pip install -r requirements.txt -r requirements-dev.txt
      
      - name: Lint
        run: |
          npm run lint
          ruff check apps/api
      
      - name: Type check
        run: npm run type-check
      
      - name: Test backend
        run: pytest apps/api/tests
      
      - name: Test frontend
        run: npm run test
      
      - name: E2E tests
        run: npm run test:e2e
      
      - name: Build
        run: |
          npm run build
          docker build -f docker/Dockerfile.api -t cogito-api .
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [x] Architecture specification (this document)
- [ ] Backend: FastAPI setup, database models, authentication
- [ ] Frontend: Next.js setup, design system, auth flow
- [ ] Core API: User management, session handling
- [ ] Deliverables: Working login, user dashboard

### Phase 2: Research Features (Weeks 4-6)
- [ ] Backend: Research job orchestration, Celery tasks
- [ ] Frontend: Research creation UI, progress monitoring
- [ ] WebSocket: Real-time progress updates
- [ ] Integration: Connect to existing Syncretic Catalyst
- [ ] Deliverables: End-to-end research workflow

### Phase 3: Critique Features (Weeks 7-9)
- [ ] Backend: Critique job management, document upload
- [ ] Frontend: Critique submission UI, report viewer
- [ ] Document preview: PDF/LaTeX rendering in browser
- [ ] Integration: Connect to existing Critique Council
- [ ] Deliverables: Complete critique workflow

### Phase 4: Search & Discovery (Weeks 10-11)
- [ ] Backend: Search API, result aggregation
- [ ] Frontend: Search UI, result visualization
- [ ] Integration: Vector search, citation graphs
- [ ] Deliverables: Unified literature search

### Phase 5: Polish & Performance (Weeks 12-13)
- [ ] Performance optimization
- [ ] Accessibility audit & fixes
- [ ] Error handling improvements
- [ ] Documentation completion
- [ ] Deliverables: Production-ready system

### Phase 6: Advanced Features (Weeks 14+)
- [ ] Schema-driven UI generation
- [ ] Plugin system foundation
- [ ] Advanced analytics dashboard
- [ ] Export template customization
- [ ] Deliverables: Extended capabilities

---

## Next Steps

To proceed with implementation, we need:

1. **Confirm Architecture**: Review and approve this specification
2. **Environment Setup**: 
   - Create `apps/api` and `apps/web` directories
   - Initialize FastAPI and Next.js projects
   - Set up Docker Compose for local development
3. **Database Design**: 
   - Design PostgreSQL schema for users, jobs, documents
   - Create SQLAlchemy models
   - Set up migrations (Alembic)
4. **Authentication**: 
   - Implement JWT-based auth
   - Create user registration/login endpoints
   - Build frontend auth flow
5. **First Feature**: 
   - Implement research job creation
   - Build research dashboard UI
   - Connect frontend to backend

**Immediate Action Items:**
- [ ] Approve architecture specification
- [ ] Provision development resources (database, Redis)
- [ ] Set up monorepo structure
- [ ] Begin Phase 1 implementation

---

## Conclusion

This architecture provides:

✅ **Full Feature Coverage**: All existing backend capabilities exposed via API  
✅ **Rapid Expansion**: Modular features, schema-driven UI, pluggable components  
✅ **Clean Architecture**: Strict layer separation, dependency inversion, testability  
✅ **Production Ready**: Security, observability, performance, accessibility  
✅ **Modern Stack**: FastAPI, Next.js, TypeScript, proven technologies  
✅ **Scalable**: Designed for growth from single user to multi-tenant  

The system is ready for implementation with clear deliverables, timelines, and technical specifications.

---

**Document Version:** 1.0  
**Last Updated:** November 23, 2025  
**Status:** ✅ Ready for Implementation
