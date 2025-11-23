# Frontend Implementation Scaffolds

This directory contains starter code scaffolds for implementing the Cogito frontend architecture.

## Quick Start Guide

### 1. Prerequisites

```bash
# Node.js 18+ and Python 3.11+
node --version  # v18.0.0+
python --version  # Python 3.11+

# Docker and Docker Compose
docker --version
docker-compose --version
```

### 2. Initial Setup

```bash
# From project root
cd /home/runner/work/Cogito/Cogito

# Create monorepo structure
mkdir -p apps/{api,web}
mkdir -p packages/{ui,api-client,types,config}

# Initialize package.json for monorepo
npm init -y

# Install Turbo for monorepo management
npm install --save-dev turbo

# Configure turbo.json (see turbo.json.example)
```

### 3. Backend Setup (FastAPI)

```bash
cd apps/api

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary redis celery pydantic-settings python-jose passlib python-multipart python-socketio aiofiles

# Create directory structure
mkdir -p {api/v1,application/{research,critique,search,auth},models,schemas,core,tasks}

# Initialize database
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### 4. Frontend Setup (Next.js)

```bash
cd apps/web

# Create Next.js app with TypeScript
npx create-next-app@latest . --typescript --tailwind --app --src-dir

# Install additional dependencies
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu
npm install @tanstack/react-query zustand
npm install react-hook-form zod @hookform/resolvers/zod
npm install socket.io-client
npm install class-variance-authority clsx tailwind-merge

# Install dev dependencies
npm install --save-dev @types/node @types/react vitest @testing-library/react @testing-library/jest-dom
```

### 5. Shared Packages Setup

```bash
# UI Package
cd packages/ui
npm init -y
# Add component library dependencies

# API Client Package
cd packages/api-client
npm init -y
# Add HTTP client dependencies

# Types Package
cd packages/types
npm init -y
# TypeScript definitions only
```

### 6. Development Environment

```bash
# From project root

# Start PostgreSQL and Redis via Docker
docker-compose -f docker/docker-compose.dev.yml up -d

# Terminal 1: Start backend
cd apps/api
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Start frontend
cd apps/web
npm run dev

# Terminal 3: Start Celery worker
cd apps/api
celery -A tasks.celery_app worker --loglevel=info

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/v1/docs
```

## File Structure Template

```
apps/
├─ api/
│  ├─ main.py                      # FastAPI application entry
│  ├─ api/
│  │  ├─ v1/
│  │  │  ├─ __init__.py
│  │  │  ├─ auth.py                # Auth endpoints
│  │  │  ├─ research.py            # Research endpoints
│  │  │  ├─ critique.py            # Critique endpoints
│  │  │  └─ ...
│  │  ├─ dependencies.py           # Dependency injection
│  │  ├─ middleware.py             # Middleware configuration
│  │  └─ websocket.py              # WebSocket handlers
│  ├─ application/
│  │  ├─ research/
│  │  │  ├─ __init__.py
│  │  │  └─ services.py            # Research orchestration
│  │  └─ ...
│  ├─ models/                      # SQLAlchemy ORM models
│  │  ├─ __init__.py
│  │  ├─ user.py
│  │  ├─ research_job.py
│  │  └─ ...
│  ├─ schemas/                     # Pydantic schemas (DTOs)
│  │  ├─ __init__.py
│  │  ├─ auth.py
│  │  ├─ research.py
│  │  └─ ...
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ config.py                 # Settings
│  │  ├─ security.py               # JWT, password hashing
│  │  └─ database.py               # DB session
│  ├─ tasks/                       # Celery tasks
│  │  ├─ __init__.py
│  │  ├─ celery_app.py
│  │  └─ research.py
│  ├─ tests/
│  │  ├─ conftest.py
│  │  ├─ test_auth.py
│  │  └─ ...
│  └─ requirements.txt
│
├─ web/
│  ├─ app/
│  │  ├─ (auth)/                   # Auth-protected routes group
│  │  │  ├─ research/
│  │  │  │  ├─ page.tsx            # Research dashboard
│  │  │  │  ├─ new/
│  │  │  │  │  └─ page.tsx         # New research form
│  │  │  │  └─ [id]/
│  │  │  │     └─ page.tsx         # Research detail
│  │  │  ├─ critique/
│  │  │  │  └─ ...
│  │  │  └─ layout.tsx             # Auth layout
│  │  ├─ auth/
│  │  │  ├─ login/
│  │  │  │  └─ page.tsx
│  │  │  └─ register/
│  │  │     └─ page.tsx
│  │  ├─ layout.tsx                # Root layout
│  │  └─ page.tsx                  # Landing page
│  ├─ components/
│  │  ├─ research/
│  │  │  ├─ ResearchForm.tsx
│  │  │  ├─ ResearchCard.tsx
│  │  │  └─ ProgressMonitor.tsx
│  │  ├─ critique/
│  │  │  └─ ...
│  │  └─ shared/
│  │     ├─ Header.tsx
│  │     ├─ Sidebar.tsx
│  │     └─ ...
│  ├─ lib/
│  │  ├─ api/                      # API client usage
│  │  │  ├─ client.ts
│  │  │  └─ hooks.ts
│  │  ├─ auth/
│  │  │  └─ AuthProvider.tsx
│  │  ├─ queries/                  # TanStack Query hooks
│  │  │  ├─ research.ts
│  │  │  └─ ...
│  │  └─ utils.ts
│  ├─ public/
│  │  └─ assets/
│  ├─ styles/
│  │  └─ globals.css
│  ├─ package.json
│  ├─ tsconfig.json
│  └─ next.config.js
│
packages/
├─ ui/
│  ├─ src/
│  │  ├─ components/
│  │  │  ├─ Button/
│  │  │  │  ├─ Button.tsx
│  │  │  │  ├─ Button.test.tsx
│  │  │  │  └─ index.ts
│  │  │  └─ ...
│  │  ├─ theme/
│  │  │  └─ tokens.ts
│  │  └─ index.ts
│  ├─ package.json
│  └─ tsconfig.json
│
├─ api-client/
│  ├─ src/
│  │  ├─ client.ts                 # Base HTTP client
│  │  ├─ auth.ts
│  │  ├─ research.ts
│  │  ├─ types.ts
│  │  └─ index.ts
│  ├─ package.json
│  └─ tsconfig.json
│
└─ types/
   ├─ src/
   │  ├─ api.ts
   │  ├─ domain.ts
   │  └─ index.ts
   └─ package.json
```

## Starter Code Examples

### FastAPI Main Application

```python
# apps/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import auth, research, critique, search, documents, users
from core.config import settings

app = FastAPI(
    title="Cogito API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(critique.router, prefix="/api/v1/critique", tags=["critique"])
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Next.js Root Layout

```typescript
// apps/web/app/layout.tsx
import { Inter } from 'next/font/google';
import { Providers } from '@/lib/providers';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'Cogito Research Platform',
  description: 'AI-powered research synthesis and critique',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### API Client Package

```typescript
// packages/api-client/src/client.ts
export class CogitoAPIClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(config: { baseURL: string; token?: string }) {
    this.baseURL = config.baseURL;
    this.token = config.token || null;
  }

  async request<T>(
    method: string,
    path: string,
    data?: any
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseURL}${path}`, {
      method,
      headers,
      body: data ? JSON.stringify(data) : undefined,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new APIError(error);
    }

    return response.json();
  }

  setToken(token: string) {
    this.token = token;
  }

  // Convenience methods
  get<T>(path: string) {
    return this.request<T>('GET', path);
  }

  post<T>(path: string, data: any) {
    return this.request<T>('POST', path, data);
  }

  // Domain-specific APIs
  get auth() {
    return new AuthAPI(this);
  }

  get research() {
    return new ResearchAPI(this);
  }
}

class AuthAPI {
  constructor(private client: CogitoAPIClient) {}

  login(email: string, password: string) {
    return this.client.post('/auth/login', { email, password });
  }

  register(email: string, password: string, full_name: string) {
    return this.client.post('/auth/register', { email, password, full_name });
  }
}

class ResearchAPI {
  constructor(private client: CogitoAPIClient) {}

  list(params?: { status?: string; page?: number }) {
    const query = new URLSearchParams(params as any).toString();
    return this.client.get(`/research?${query}`);
  }

  get(id: string) {
    return this.client.get(`/research/${id}`);
  }

  create(data: { concept: string; config?: any }) {
    return this.client.post('/research', data);
  }
}
```

## Docker Configuration

### Development Docker Compose

```yaml
# docker/docker-compose.dev.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: cogito
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: cogito_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data

volumes:
  postgres_dev_data:
  redis_dev_data:
```

## Environment Variables

### Backend (.env)

```bash
# apps/api/.env
DATABASE_URL=postgresql://cogito:dev_password@localhost:5432/cogito_dev
REDIS_URL=redis://localhost:6379/0

SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:3000

# LLM API Keys (from existing config)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# Email (optional)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
```

### Frontend (.env.local)

```bash
# apps/web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws
```

## Testing Setup

### Backend Testing

```python
# apps/api/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from core.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### Frontend Testing

```typescript
// apps/web/lib/test-utils.tsx
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

export function renderWithProviders(ui: React.ReactElement) {
  const testQueryClient = createTestQueryClient();
  
  return render(
    <QueryClientProvider client={testQueryClient}>
      {ui}
    </QueryClientProvider>
  );
}
```

## Next Steps

1. **Review Architecture:** Confirm the proposed architecture meets requirements
2. **Initialize Projects:** Create backend and frontend projects using templates above
3. **Database Schema:** Design and implement database models
4. **Authentication:** Implement JWT-based authentication
5. **First Feature:** Build research job creation end-to-end
6. **Iterate:** Add remaining features incrementally

## Support & Resources

- **Architecture Doc:** `docs/FRONTEND_ARCHITECTURE.md`
- **API Spec:** `docs/api/BACKEND_API_SPEC.md`
- **Backend Enhancement Report:** `docs/BACKEND_ENHANCEMENT_REPORT.md`
- **Architecture Rules:** `ARCHITECTURE_RULES.md`

---

**Ready to Begin Implementation!**
