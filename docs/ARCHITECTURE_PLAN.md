# IterateSwarm: Architecture Enhancement Plan

**Version:** 1.0
**Date:** 2026-02-05
**Status:** DRAFT - Awaiting Approval

---

## Executive Summary

This plan outlines enhancements to IterateSwarm across six key areas:
1. **Auth & Multi-tenancy** - Secure access control with tenant isolation
2. **Mockoon Integration** - API mocking for development/testing
3. **Third-Party Integration Framework** - Extensible plugin system
4. **Internal System Architecture** - Self-hosted management plane
5. **Monitoring Dashboards** - Observability & operational insights
6. **LiteDebug Tools** - No-code troubleshooting utilities

---

# IterateSwarm: Architecture Enhancement Plan

**Version:** 2.0 (Senior Engineer Portfolio Edition)
**Date:** 2026-02-05
**Status:** APPROVED
**Reviewer:** Senior Engineer (Portfolio Focus)

---

## Executive Summary

**Strategic Shift:** From broad implementation (~105h) to focused systems work (~60h).

**Key Changes from v1.0:**
1. **Auth:** Clerk SDK for Go instead of custom JWT engine
2. **Monitoring:** Keep Jaeger, add Prometheus/Grafana for metrics only
3. **Removed:** Admin Console CRUD (use Prisma Studio instead)
4. **Reordered:** LiteDebug → Monitoring → Integrations → Auth

---

## Part 1: Auth & Multi-Tenancy (SIMPLIFIED)

### Current State
- Clerk SDK installed (`@clerk/nextjs`) but NOT configured
- `INTERNAL_API_KEY` for service-to-service auth only
- Webhook signature verification (Discord ED25519, Slack HMAC)

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    IterateSwarm Auth Layer                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    Clerk (Primary)                   │   │
│   │   Frontend: React components (SignIn/SignUp)         │   │
│   │   Backend:  clerk-sdk-go (JWT validation)            │   │
│   │   User Mgmt: Clerk Dashboard                         │   │
│   └─────────────────────────────────────────────────────┘   │
│                              │                                │
│         ┌────────────────────┼────────────────────┐         │
│         ▼                    ▼                    ▼         │
│   ┌──────────┐        ┌──────────┐        ┌──────────┐       │
│   │ Frontend │        │  Go API  │        │ Python   │       │
│   │  (Next)  │        │  (Fiber) │        │   (AI)   │       │
│   │ Clerk.js │        │ clerk-go │        │ JWT only │       │
│   └──────────┘        └──────────┘        └──────────┘       │
│                              │                                │
│   ┌─────────────────────────────────────────────────────┐   │
│   │   API Keys (External Integrations - Discord/Slack)  │   │
│   │   NOT handled by Clerk - Custom table in Prisma    │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Why This Approach?

| Approach | Complexity | Maintenance | Seniority Signal |
|----------|-------------|-------------|------------------|
| Custom JWT + BFF | High | High | Junior |
| Clerk SDK (Frontend + Backend) | Low | Low | **Senior** |

A senior engineer doesn't reinvent authentication. They integrate proven services and focus on business logic.

### Database Schema Changes

```prisma
// NOTE: Removed User/Tenant tables - Clerk manages users
// Keep ONLY what Clerk cannot handle

// API Keys for External Integrations (Discord/Slack webhooks)
// These cannot use Clerk's JWT (webhooks don't have user context)
model ApiKey {
  id          String   @id @default(uuid())
  key         String   @unique @db.VarChar(64)
  prefix      String   @db.VarChar(4)  // First 4 chars for identification
  name        String                    // e.g., "Production Webhook"
  hashedKey   String   @db.VarChar(128)
  scopes      String[]  @default([])   // feedback:read, issues:write
  lastUsedAt  DateTime?
  expiresAt   DateTime?
  active      Boolean  @default(true)
  createdAt   DateTime @default(now())

  @@index([key(12)])  // Hash prefix index
}

// Keep existing tables - add tenant_id when multi-tenancy is needed
model FeedbackItem {
  id          String   @id @default(uuid())
  content     String   @db.Text
  source      String
  status      String   @default("pending")
  // ... existing fields

  // Optional: Add when implementing multi-tenancy
  // tenantId   String?
  // @@index([tenantId])
}

model Issue {
  id          String   @id @default(uuid())
  feedbackId  String   @unique
  title       String   @db.VarChar(255)
  // ... existing fields

  // Optional: Add when implementing multi-tenancy
  // tenantId   String?
  // @@index([tenantId])
}
```

### Go Implementation (Clerk SDK)

```go
// apps/core/internal/auth/clerk.go

package auth

import (
    "context"
    "fmt"
    "net/http"
    "strings"

    "github.com/clerk/clerk-sdk-go/v2"
    "github.com/clerk/clerk-sdk-go/v2/jwt"
    "github.com/gofiber/fiber/v2"
)

// ClerkConfig holds Clerk configuration
type ClerkConfig struct {
    SecretKey string
}

// NewClerkAuth creates a new Clerk authenticator
func NewClerkAuth(config ClerkConfig) *ClerkAuth {
    return &ClerkAuth{
        client:   clerk.NewClient(config.SecretKey),
    }
}

// ClerkAuth handles Clerk JWT validation
type ClerkAuth struct {
    client *clerk.Client
}

// Middleware returns a Fiber middleware that validates Clerk JWTs
func (c *ClerkAuth) Middleware() fiber.Handler {
    return func(ctx *fiber.Ctx) error {
        authHeader := ctx.Get("Authorization")
        if authHeader == "" {
            return ctx.Status(http.StatusUnauthorized).JSON(fiber.Map{
                "error": "Missing authorization header",
            })
        }

        parts := strings.Split(authHeader, " ")
        if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
            return ctx.Status(http.StatusUnauthorized).JSON(fiber.Map{
                "error": "Invalid authorization header format",
            })
        }

        token := parts[0]

        // Validate JWT using Clerk SDK
        claims, err := jwt.ValidateToken(ctx.Context(), token,
            jwt.WithKeySet(clerk.NewJWTKeySet()),
        )
        if err != nil {
            return ctx.Status(http.StatusUnauthorized).JSON(fiber.Map{
                "error": "Invalid token: " + err.Error(),
            })
        }

        // Store claims in context for downstream use
        ctx.Locals("userID", claims.Subject)
        ctx.Locals("userClaims", claims)

        return ctx.Next()
    }
}

// RequireScope returns a middleware that requires specific scopes
func RequireScope(requiredScope string) fiber.Handler {
    return func(ctx *fiber.Ctx) error {
        claims, ok := ctx.Locals("userClaims").(*jwt.Claims)
        if !ok {
            return ctx.Status(http.StatusUnauthorized).JSON(fiber.Map{
                "error": "No valid session",
            })
        }

        // Check scopes claim (custom claim in Clerk)
        scopes, ok := claims["scope"].(string)
        if !ok || !containsScope(scopes, requiredScope) {
            return ctx.Status(http.StatusForbidden).JSON(fiber.Map{
                "error": "Insufficient permissions",
            })
        }

        return ctx.Next()
    }
}

func containsScope(scopes, required string) bool {
    for _, s := range strings.Split(scopes, " ") {
        if s == required {
            return true
        }
    }
    return false
}
```

### Frontend Implementation (Standard Clerk)

```typescript
// fullstack/src/app/layout.tsx

import { ClerkProvider } from '@clerk/nextjs'
import './globals.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  )
}

// fullstack/src/middleware.ts
import { clerkMiddleware } from '@clerk/nextjs/server'

export default clerkMiddleware()

export const config = {
  matcher: [
    // Skip internal API routes (webhooks, health)
    '/((?!api/internal|health).*)',
  ],
}
```

### Implementation Steps

| Phase | Task | Effort |
|-------|------|--------|
| **1.1** | Configure Clerk env vars & middleware | 1h |
| **1.2** | Add ClerkProvider to layout | 30m |
| **1.3** | Create Go auth middleware (clerk-sdk-go) | 2h |
| **1.4** | Protect API routes with Clerk middleware | 1h |
| **1.5** | Add ApiKey table to Prisma (webhooks) | 1h |
| **1.6** | Create API key validation middleware | 1h |

**Total: ~6.5 hours** (vs 15h in v1.0)

---

## Part 2: Mockoon Integration

### Current State
- No OpenAPI specification
- No API mocking infrastructure
- Fiber (Go) doesn't auto-generate docs
- Next.js API routes have no schema

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Mockoon Ecosystem                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│   │  OpenAPI     │    │  Mockoon      │    │  Pact/Contract│ │
│   │  Spec 3.0    │───▶│  Docker       │───▶│   Testing     │ │
│   │  (Source)    │    │  Container    │    │              │ │
│   └──────────────┘    └──────────────┘    └──────────────┘ │
│           │                    │                    │       │
│           │                    │                    │       │
│           ▼                    ▼                    ▼       │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│   │ 1. Swagger  │    │ 1. Dev/Test  │    │ 1. Consumer  │ │
│   │    UI       │    │    Mocks     │    │    Tests     │ │
│   │ 2. TypeGen  │    │ 2. CI/CD     │    │ 2. Provider  │ │
│   │ 3. Postman  │    │    Mocking   │    │    Tests     │ │
│   └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Steps

| Phase | Task | Effort |
|-------|------|--------|
| **2.1** | Create OpenAPI spec for all endpoints | 3h |
| **2.2** | Set up Mockoon Docker container | 1h |
| **2.3** | Create mock data for all endpoints | 2h |
| **2.4** | Configure Mockoon environments (dev, test) | 1h |
| **2.5** | Generate TypeScript types from OpenAPI | 1h |
| **2.6** | Create mockoon.yaml migration script | 1h |
| **2.7** | Integrate with CI pipeline | 2h |

### Files to Create

```
mockoon/
├── environments/                   # Mockoon environment files
│   ├── local.json                # Local development mocks
│   └── ci.json                   # CI/CD mocks
├── specs/
│   └── iterateswarm-api.yaml     # OpenAPI 3.0 specification
├── scripts/
│   ├── generate-spec.ts          # Extract spec from code
│   └── import-mockoon.sh         # Import to Mockoon
└── README.md

# Docker Compose addition
services:
  mockoon:
    image: mockoon/cli:latest
    container_name: iterateswarm-mockoon
    ports:
      - "3001:3000"  # Mock API port
      - "3002:9229"  # Mockoon Admin port
    volumes:
      - ./mockoon/environments:/data
    command: mockoon-cli start --data /data/local.json --port 3000
```

### OpenAPI Spec Structure

```yaml
openapi: 3.0.3
info:
  title: IterateSwarm API
  version: 1.0.0
  description: AI-Powered Feedback Triage & Issue Management

servers:
  - url: http://localhost:3000
    description: Go Core Server
  - url: http://localhost:3001
    description: Mockoon Mock Server

paths:
  /health:
    get:
      summary: Health check
      responses:
        '200':
          description: Service healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

  /webhooks/discord:
    post:
      summary: Discord webhook for feedback
      security: []  # No auth (Discord signs)
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DiscordWebhook'
      responses:
        '202':
          description: Feedback accepted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/FeedbackAccepted'

  /api/issues:
    get:
      summary: List issues
      security:
        - BearerAuth: []
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [draft, approved, rejected, published]
        - name: tenant_id
          in: header
          required: true
      responses:
        '200':
          description: List of issues

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key

  schemas:
    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
    FeedbackAccepted:
      type: object
      properties:
        feedback_id:
          type: string
          format: uuid
        status:
          type: string
```

---

## Part 3: Third-Party Integration Framework

### Current State
- Discord webhook (ED25519) ✅
- Slack webhook (HMAC) ✅
- GitHub issue creation ✅
- Hardcoded integrations in Next.js route handlers

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Integration Framework                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Integration Manager                      │   │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│   │   │ Discord │ │  Slack  │ │ GitHub  │ │  Jira   │  │   │
│   │   │ Adapter │ │ Adapter │ │ Adapter │ │ Adapter │  │   │
│   │   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │   │
│   │        │          │          │          │        │   │
│   │        └──────────┴──────────┴──────────┘        │   │
│   │                      │                           │   │
│   │                ┌──────▼──────┐                     │   │
│   │                │   Plugin    │                     │   │
│   │                │   Registry  │                     │   │
│   │                └──────┬──────┘                     │   │
│   └───────────────────────┼─────────────────────────────┘   │
│                          │                                  │
│   ┌──────────────────────▼──────────────────────────────┐  │
│   │              Event Bus (Kafka/Redpanda)              │  │
│   │   feedback.created → Integration → External Platform │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Interface Definition

```typescript
// apps/core/internal/integrations/types.ts

export interface Integration {
  id: string;
  name: string;
  version: string;
  provider: string;

  // Capabilities
  capabilities: IntegrationCapability[];

  // Configuration
  configSchema: JSONSchema;
  defaultConfig: Record<string, unknown>;

  // Lifecycle
  initialize(config: IntegrationConfig): Promise<void>;
  shutdown(): Promise<void>;

  // Events
  supportsEvent(event: string): boolean;
  handleEvent(event: IntegrationEvent): Promise<IntegrationResponse>;

  // Webhook handling (for incoming integrations)
  validateWebhook(request: WebhookRequest): Promise<boolean>;
  parseWebhook(request: WebhookRequest): Promise<ParsedEvent>;
}

export interface IntegrationCapability {
  type: 'outbound' | 'inbound' | 'bidirectional';
  events: string[];           // e.g., ['issue.created', 'feedback.approved']
  authType: 'oauth2' | 'api_key' | 'webhook_secret' | 'none';
  autoEnable: boolean;
}

export interface IntegrationEvent {
  type: string;
  payload: Record<string, unknown>;
  metadata: {
    tenantId: string;
    correlationId: string;
    timestamp: Date;
  };
}

export interface IntegrationResponse {
  success: boolean;
  externalId?: string;
  externalUrl?: string;
  error?: string;
}
```

### Adapter Pattern Example

```typescript
// apps/core/internal/integrations/adapters/github/adapter.ts

import { Integration, IntegrationEvent, IntegrationResponse } from '../types';

export class GitHubIntegration implements Integration {
  id = 'github';
  name = 'GitHub';
  version = '1.0.0';
  provider = 'GitHub';

  capabilities = [
    {
      type: 'outbound',
      events: ['issue.created', 'issue.labeled', 'issue.closed'],
      authType: 'api_key',
      autoEnable: true,
    },
    {
      type: 'inbound',
      events: ['pr.merged', 'commit.pushed'],
      authType: 'webhook_secret',
      autoEnable: false,
    },
  ];

  private client: Octokit;

  async initialize(config: IntegrationConfig): Promise<void> {
    this.client = new Octokit({ auth: config.token });
  }

  supportsEvent(event: string): boolean {
    return ['issue.created', 'issue.labeled', 'issue.closed'].includes(event);
  }

  async handleEvent(event: IntegrationEvent): Promise<IntegrationResponse> {
    switch (event.type) {
      case 'issue.created':
        return this.createIssue(event.payload);
      case 'issue.labeled':
        return this.addLabel(event.payload);
      default:
        throw new Error(`Unsupported event: ${event.type}`);
    }
  }

  private async createIssue(payload: any): Promise<IntegrationResponse> {
    const response = await this.client.rest.issues.create({
      owner: payload.owner,
      repo: payload.repo,
      title: payload.title,
      body: payload.body,
      labels: payload.labels,
    });

    return {
      success: true,
      externalId: String(response.data.id),
      externalUrl: response.data.html_url,
    };
  }
  // ... other methods
}
```

### Files to Create

```
apps/core/internal/integrations/
├── types.ts                    # Interface definitions
├── registry.go                 # Plugin registry
├── manager.go                 # Integration lifecycle manager
├── events.go                  # Event types
└── adapters/
    ├── discord/
    │   ├── adapter.go
    │   ├── webhook.go
    │   └── config.yaml
    ├── slack/
    │   ├── adapter.go
    │   ├── webhook.go
    │   └── config.yaml
    ├── github/
    │   ├── adapter.go
    │   ├── webhook.go
    │   └── config.yaml
    └── jira/
        ├── adapter.go
        ├── oauth.go
        └── config.yaml

# Configuration
apps/core/config/integrations.yaml:
integrations:
  github:
    enabled: true
    default_config:
      owner: ${GITHUB_OWNER}
      repo: ${GITHUB_REPO}
      token: ${GITHUB_TOKEN}

  discord:
    enabled: true
    default_config:
      bot_token: ${DISCORD_BOT_TOKEN}
      guild_id: ${DISCORD_GUILD_ID}

  slack:
    enabled: false
    default_config:
      bot_token: ${SLACK_BOT_TOKEN}
      signing_secret: ${SLACK_SIGNING_SECRET}

  jira:
    enabled: false
    oauth:
      client_id: ${JIRA_CLIENT_ID}
      client_secret: ${JIRA_CLIENT_SECRET}
      cloud_id: ${JIRA_CLOUD_ID}
```

---

## Part 4: IterateSwarm Internal System

### Current State
- Single-tenant (system-level feedback/issues)
- No internal management UI
- No self-hosted admin capabilities

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               IterateSwarm Internal System                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                   Admin Console                     │   │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│   │  │Tenant   │ │System   │ │Integrations│ │Audit   │  │   │
│   │  │Manager  │ │Health   │ │Console   │ │Logs    │  │   │
│   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│   └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│   ┌──────────────────────▼──────────────────────────────┐  │
│   │              Internal API (BFF Layer)               │  │
│   │   GET /internal/admin/tenants                        │  │
│   │   POST /internal/admin/tenants/{id}/suspend         │  │
│   │   GET /internal/admin/system/status                  │  │
│   │   POST /internal/admin/integrations/{id}/configure  │  │
│   └─────────────────────────────────────────────────────┘  │
│                          │                                  │
│   ┌──────────────────────▼──────────────────────────────┐  │
│   │                 Core Services                        │  │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │  │
│   │   │Tenant   │ │License  │ │Quota    │ │Health   │  │  │
│   │   │Service  │ │Service  │ │Service  │ │Service  │  │  │
│   │   └─────────┘ └─────────┘ └─────────┘ └─────────┘  │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Admin Dashboard Pages

```
fullstack/src/app/
├── (admin)/                      # Admin route group
│   ├── layout.tsx               # Admin shell with sidebar
│   ├── page.tsx                 # System overview
│   ├── tenants/
│   │   ├── page.tsx             # Tenant list
│   │   ├── [id]/
│   │   │   ├── page.tsx         # Tenant details
│   │   │   ├── settings.tsx     # Tenant config
│   │   │   └── usage.tsx        # Usage metrics
│   │   └── new/page.tsx         # Create tenant
│   ├── integrations/
│   │   ├── page.tsx             # All integrations
│   │   └── [id]/configure.tsx   # Configure integration
│   ├── audit/
│   │   └── page.tsx             # Audit log viewer
│   └── system/
│       ├── page.tsx             # System health
│       ├── workers/              # Temporal workers status
│       └── metrics/             # Grafana links
```

### Internal API Endpoints

```typescript
// GET /api/internal/admin/tenants
interface TenantListResponse {
  tenants: {
    id: string;
    name: string;
    slug: string;
    plan: 'free' | 'pro' | 'enterprise';
    status: 'active' | 'suspended' | 'trial';
    userCount: number;
    feedbackCount: number;
    createdAt: string;
  }[];
  pagination: {
    page: number;
    limit: number;
    total: number;
  };
}

// POST /api/internal/admin/tenants
interface CreateTenantRequest {
  name: string;
  slug: string;
  plan: 'free' | 'pro' | 'enterprise';
  ownerEmail: string;
}

// GET /api/internal/admin/system/health
interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: {
    name: string;
    status: 'up' | 'down' | 'degraded';
    latencyMs: number;
    error?: string;
  }[];
  metrics: {
    totalFeedback: number;
    totalIssues: number;
    activeTenants: number;
    kafkaLag: number;
  };
}
```

---

## Part 5: Monitoring Dashboards

### Current State
- Basic dashboard with stats cards
- `/health/details` endpoint in Go
- Individual service UIs (Temporal, Redpanda, etc.)

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Monitoring Stack                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Grafana Dashboard (Primary)            │   │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│   │   │Overview │ │ Feedback│ │ Issues  │ │ System  │  │   │
│   │   │Dashboard│ │ Metrics │ │ Metrics │ │ Health  │  │   │
│   │   └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│   └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│   ┌──────────────────────▼──────────────────────────────┐  │
│   │              Data Sources                           │  │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │  │
│   │   │Prometheus│ │Tempo    │ │Loki     │ │Redpanda │  │  │
│   │   │(Metrics) │ │(Traces) │ │(Logs)   │ │Console  │  │  │
│   │   └─────────┘ └─────────┘ └─────────┘ └─────────┘  │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Dashboard Sections

```
┌─────────────────────────────────────────────────────────────────┐
│                    IterateSwarm Overview                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │ Feedback     │ │ Issues      │ │ Published   │ │ Kafka    │ │
│  │ Ingested     │ │ Created     │ │ to GitHub   │ │ Lag      │ │
│  │ 1,234       │ │ 567         │ │ 890         │ │ 12ms     │ │
│  │ +12%        │ │ +8%         │ │ +15%        │ │ 0        │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────┐ ┌─────────────────────────────────┐ │
│  │ Feedback Volume       │ │ Issue Status Distribution      │ │
│  │ (Line Chart 24h)      │ │ (Pie Chart)                     │ │
│  │                       │ │  Draft ████████ 45%            │ │
│  │ ▂▃▅▆▇█▇▆▅▄▃▂▄▃▂▄▃▂  │ │  Approved █████ 30%            │ │
│  │                       │ │  Rejected ███ 15%              │ │
│  └───────────────────────┘ │  Published ██ 10%              │ │
│                            └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ System Health                                             │ │
│  │ ○ Go Server      CPU: 12%  MEM: 450MB  │ STATUS: HEALTHY │ │
│  │ ○ Python AI      CPU: 45%  MEM: 1.2GB  │ STATUS: HEALTHY │ │
│  │ ○ Temporal       Workers: 4/4        │ STATUS: HEALTHY │ │
│  │ ○ Kafka/Redpanda Topics: 4  Lag: 0   │ STATUS: HEALTHY │ │
│  │ ○ PostgreSQL     Connections: 12/100 │ STATUS: HEALTHY │ │
│  │ ○ Qdrant         Collections: 2      │ STATUS: HEALTHY │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Files to Create

```
docker-compose.monitoring.yml:
services:
  prometheus:
    image: prom/prometheus:v2.48
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:10.2
    ports:
      - "3002:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana

  tempo:
    image: grafana/tempo:2.0
    ports:
      - "4317:4317"  # OTLP
      - "3200:3200"  # Query

  loki:
    image: grafana/loki:2.9
    ports:
      - "3100:3100"

monitoring/
├── prometheus.yml
├── grafana/
│   ├── provisioning/
│   │   ├── dashboards/
│   │   │   └── iterateswarm-overview.json
│   │   ├── datasources/
│   │   │   └── prometheus.yaml
│   │   └── notifiers/
│   │       └── alertmanager.yaml
│   └── dashboards/
│       ├── overview.json
│       ├── feedback.json
│       ├── issues.json
│       └── system.json
└── alerts/
    └── alert_rules.yml
```

### Key Metrics to Track

| Category | Metrics | Alert Threshold |
|----------|---------|-----------------|
| **Ingestion** | feedback/sec, latency_p95 | latency > 2s |
| **AI Processing** | queue depth, processing time | queue > 100 |
| **Kafka** | consumer lag, topic lag | lag > 1000 |
| **Database** | connections, query time | connections > 80% |
| **Infrastructure** | CPU, Memory, Disk | memory > 85% |

---

## Part 6: LiteDebug - Troubleshooting Tools

### Concept
"No-code troubleshooting utilities" - Web-based tools for debugging without deploying code changes.

### Features

```
┌─────────────────────────────────────────────────────────────────┐
│                      LiteDebug Console                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  🔍 Event Trace Viewer                                    │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │  │
│  │  │Kafka    │ │Temporal │ │GitHub   │ │Discord  │          │  │
│  │  │Events   │ │Workflows│ │API      │ │Webhooks │          │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │  │
│  │                                                               │  │
│  │  Filter: correlation_id=abc123 │ Status: ● All ○ Success  │  │
│  │  ○ Error                                                  │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ [13:45:01] feedback.created  ●███████░░ 85%         │   │  │
│  │  │ [13:45:02] ai.classify       ●███████░░ 85%         │   │  │
│  │  │ [13:45:05] issue.created     ●███████░░ 85%         │   │  │
│  │  │ [13:45:06] github.issue.create●███████░░ 85%         │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  📡 Kafka Topic Browser                                   │  │
│  │  Topic: [feedback-events ▼]  Partition: [all ▼]           │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ Offset │ Key                   │ Value             │   │  │
│  │  │ 12345  │ 2026-02-04T13:45:01Z  │ {"feedback_id":...}│   │  │
│  │  │ 12346  │ 2026-02-04T13:45:02Z  │ {"feedback_id":...}│   │  │
│  │  │ 12347  │ 2026-02-04T13:45:05Z  │ {"issue_id":...}   │   │  │
│  │  │ 12348  │ 2026-02-04T13:45:06Z  │ {"issue_id":...}   │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │                                                               │  │
│  │  [Consume] [Produce Test Message] [Clear Topic]            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  ⚡ Workflow Inspector (Temporal)                           │  │
│  │  Workflow ID: [search ▼]  Status: [all ▼]                   │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ wf-12345-abc  ai-feedback-workflow  ● Completed    │   │  │
│  │  │ Details: 4 activities, 12.5s total, 0 retries       │   │  │
│  │  │ Activity List:                                        │   │  │
│  │  │   [1] classify-feedback    2.1s  ● Success         │   │  │
│  │  │   [2] vector-search         150ms ● Success         │   │  │
│  │  │   [3] generate-spec         5.3s  ● Success         │   │  │
│  │  │   [4] create-issue           4.8s  ● Success         │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │  [Replay] [Cancel] [Signal] [Terminate]                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  🧪 Test Console                                          │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ POST /webhooks/discord                               │   │  │
│  │  │ { "content": "Test message", "source": "debug" }    │   │  │
│  │  │                                                     │   │  │
│  │  │ ▶ SEND                                               │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │  Response: 202 Accepted { "feedback_id": "..." }          │  │
│  │  Trace ID: trace-12345-abc                                 │  │
│  │  [View in Trace Viewer]                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Files to Create

```
fullstack/src/app/
├── (debug)/                       # Debug route group
│   ├── layout.tsx                # Debug shell
│   ├── page.tsx                  # Debug dashboard
│   ├── traces/
│   │   ├── page.tsx             # Distributed trace viewer
│   │   └── [id]/page.tsx        # Trace details
│   ├── kafka/
│   │   ├── page.tsx             # Topic browser
│   │   └── [topic]/page.tsx    # Topic contents
│   ├── workflows/
│   │   ├── page.tsx             # Workflow list
│   │   └── [id]/page.tsx       # Workflow details
│   └── test/
│       ├── page.tsx             # API test console
│       └── webhook/page.tsx    # Webhook tester

apps/core/internal/debug/
├── handlers.go                   # Debug API handlers
├── kafka_browser.go              # Kafka topic browsing
├── workflow_inspector.go         # Temporal workflow inspection
└── trace_viewer.go               # Trace correlation
```

### API Endpoints for Debug

```typescript
// GET /api/debug/kafka/topics
interface KafkaTopicsResponse {
  topics: {
    name: string;
    partitions: number;
    messages: number;
    lag: number;
  }[];
}

// GET /api/debug/kafka/topics/:name/messages
interface KafkaMessagesRequest {
  partition?: number;
  offset?: number;
  limit?: number;
}

// GET /api/debug/workflows
interface WorkflowsRequest {
  status?: 'running' | 'completed' | 'failed' | 'all';
  workflowType?: string;
  limit?: number;
}

// POST /api/debug/test/webhook
interface WebhookTestRequest {
  provider: 'discord' | 'slack';
  payload: Record<string, unknown>;
}

// GET /api/debug/traces/:traceId
interface TraceResponse {
  traceId: string;
  spans: {
    spanId: string;
    operation: string;
    service: string;
    startTime: string;
    duration: number;
    status: 'ok' | 'error';
    logs: { timestamp: string; fields: Record<string, unknown> }[];
  }[];
}
```

---

## Implementation Roadmap

```
Phase 1: Foundation
├── Auth & Multi-tenancy (Parts 1)
├── Prisma Schema Updates
└── Basic RBAC

Phase 2: Observability
├── Monitoring Dashboards (Part 5)
├── LiteDebug Tools (Part 6)
└── Prometheus/Grafana Setup

Phase 3: Extensibility
├── Integration Framework (Part 3)
├── Mockoon Setup (Part 2)
└── Plugin System

Phase 4: Internal Systems
├── Admin Console (Part 4)
├── Tenant Management
└── Self-Service Onboarding
```

---

## Effort Summary

| Part | Scope | Effort |
|------|-------|--------|
| 1. Auth & Multi-tenancy | Full implementation | ~15h |
| 2. Mockoon Integration | Setup + CI integration | ~10h |
| 3. Integration Framework | 4 adapters + registry | ~20h |
| 4. Internal System | Admin UI + APIs | ~25h |
| 5. Monitoring Dashboards | Grafana + Prometheus | ~15h |
| 6. LiteDebug Tools | 4 debug utilities | ~20h |

**Total Estimated Effort: ~105 hours**

---

## Files Modified/Created Summary

```
TOTAL NEW FILES: ~45
TOTAL MODIFIED FILES: ~15

New Directories:
├── apps/core/internal/auth/
├── apps/core/internal/integrations/
├── apps/core/internal/debug/
├── apps/core/internal/tenant/
├── fullstack/src/app/(admin)/
├── fullstack/src/app/(debug)/
├── monitoring/
├── mockoon/
└── scripts/
```

---

## Next Steps

1. **Review & Approve** this plan
2. **Prioritize** which parts to implement first
3. **Identify** any custom requirements not covered
4. **Confirm** timeline/resource constraints

---

*Document generated: 2026-02-05*
*Version: 1.0 DRAFT*
