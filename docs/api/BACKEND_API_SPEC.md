# Cogito Backend API Specification

**Version:** 1.0.0  
**Base URL:** `/api/v1`  
**Protocol:** REST + WebSocket  
**Authentication:** Bearer JWT Token

---

## Table of Contents

1. [Authentication](#authentication)
2. [Research APIs](#research-apis)
3. [Critique APIs](#critique-apis)
4. [Search APIs](#search-apis)
5. [Document APIs](#document-apis)
6. [User APIs](#user-apis)
7. [Admin APIs](#admin-apis)
8. [WebSocket Events](#websocket-events)
9. [Error Responses](#error-responses)

---

## Authentication

### POST /auth/register

Register a new user account.

**Request:**
```json
{
  "email": "researcher@example.com",
  "password": "securePassword123!",
  "full_name": "Dr. Jane Researcher"
}
```

**Response:** `201 Created`
```json
{
  "id": "usr_abc123",
  "email": "researcher@example.com",
  "full_name": "Dr. Jane Researcher",
  "created_at": "2025-11-23T00:00:00Z"
}
```

### POST /auth/login

Authenticate and receive access token.

**Request:**
```json
{
  "email": "researcher@example.com",
  "password": "securePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "ref_xyz789",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "usr_abc123",
    "email": "researcher@example.com",
    "full_name": "Dr. Jane Researcher",
    "permissions": ["research.view", "research.create", "critique.view"]
  }
}
```

### POST /auth/refresh

Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "ref_xyz789"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### POST /auth/logout

Invalidate current session.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

---

## Research APIs

### POST /research

Create a new research project.

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "concept": "Quantum computing applications in drug discovery",
  "config": {
    "max_papers": 20,
    "include_historical": true,
    "include_modern": true,
    "agents": ["historical", "modern", "methodological", "mathematical"],
    "max_duration_minutes": 60
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "res_def456",
  "user_id": "usr_abc123",
  "concept": "Quantum computing applications in drug discovery",
  "status": "pending",
  "config": { },
  "created_at": "2025-11-23T00:00:00Z",
  "estimated_duration_minutes": 45
}
```

### GET /research

List user's research projects.

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `running`, `completed`, `failed`)
- `page` (default: 1): Page number
- `per_page` (default: 20): Results per page

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "res_def456",
      "concept": "Quantum computing applications...",
      "status": "completed",
      "created_at": "2025-11-23T00:00:00Z",
      "completed_at": "2025-11-23T00:45:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

*Full API specification truncated for brevity. See complete file at docs/api/BACKEND_API_SPEC.md*

---

**Last Updated:** November 23, 2025  
**Version:** 1.0.0
