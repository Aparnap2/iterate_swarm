# IterateSwarm: Architectural Review & Recommendations

## Executive Summary

**Overall Grade: B+ (Solid Foundation, Polish Needed)**

This is a well-architected polyglot system with correct patterns, but there are gaps in production readiness, observability, and edge case handling that would prevent me from shipping this to production as-is.

---

## Part 1: What I'd KEEP (Don't Change)

### 1.1 Polyglot Architecture ✓

```
Go for Orchestration  →  CORRECT
Python for AI        →  CORRECT
gRPC Communication   →  CORRECT
```

**Rationale:** Each language plays to its strengths. Go's type safety + performance for orchestration, Python's ecosystem for AI. This is a defensible architecture.

### 1.2 Temporal for Workflow ✓

The state machine pattern is correctly implemented:

```go
// This is correct
workflow.ExecuteActivity(ctx, "AnalyzeFeedback", input)
signalChan := workflow.GetSignalChannel(ctx, "user-action")
workflow.AwaitWithTimeout(ctx, 5*time.Minute, ...)
```

**Rationale:** Temporal is the right choice. SDK is excellent, UI provides observability.

### 1.3 gRPC Contract ✓

The protobuf definitions are clean and minimal:

```protobuf
rpc AnalyzeFeedback(AnalyzeFeedbackRequest) returns (AnalyzeFeedbackResponse);
```

**Rationale:** Keep it simple. Don't over-engineer the contract.

### 1.4 Event Sourcing Pattern ✓

```
Discord → Redpanda → Temporal Worker → gRPC → Python
```

**Rationale:** Decouples ingestion from processing. Enables replayability.

---

## Part 2: What I'd ADD (Production Readiness)

### 2.1 Critical: Error Handling & Retry Policies

**Current State:**
```go
func (a *Activities) SendDiscordApproval(...) error {
    // No retry logic
    // No circuit breaker
    // Silent failures
}
```

**Problem:** External APIs (Discord, GitHub) are flaky. No resilience.

**My Fix:**
```go
import "github.com/raft-tech/tenacity"

func (a *Activities) SendDiscordApproval(ctx context.Context, ...) error {
    return tenacity.Config{
        MaxRetries:           3,
        RetryDelay:           1 * time.Second,
        RetryJitter:          100 * time.Millisecond,
        RetryOnTimeout:       true,
    }.Run(func() error {
        // Discord API call with backoff
    })
}
```

**Recommended Additions:**
1. **tenacity** for retry with backoff
2. **gobreaker** for circuit breaker
3. **slog** for structured logging (Go 1.21+)

### 2.2 Critical: Observability (Not Just Logging)

**Current State:**
```go
log.Printf("Analyzing feedback: %s", text)
```

**Problem:** No structured logs, no metrics, no tracing.

**My Fix - Add OpenTelemetry:**

```go
import "go.opentelemetry.io/otel"
import "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
import "go.opentelemetry.io/otel/sdk/resource"

func InitTracer() (*trace.TracerProvider, error) {
    ctx := context.Background()

    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("localhost:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.ServiceName("iterateswarm-core"),
        )),
    )

    otel.SetTracerProvider(tp)
    return tp, nil
}
```

**Span Propagation in Workflow:**
```go
func FeedbackWorkflow(ctx workflow.Context, input FeedbackInput) error {
    ctx, span := tracer.Start(ctx, "FeedbackWorkflow",
        trace.WithAttributes(
            attribute.String("user_id", input.UserID),
            attribute.String("source", input.Source),
        ),
    )
    defer span.End()
    // ... workflow continues with traced context
}
```

### 2.3 Critical: Configuration Management

**Current State:**
```go
discordToken := os.Getenv("DISCORD_BOT_TOKEN")
githubToken := os.Getenv("GITHUB_TOKEN")
```

**Problem:** No validation, no defaults, no environment prefixes.

**My Fix - Add Pydantic-Settings Pattern to Go:**

```go
import "github.com/spf13/viper"

type Config struct {
    Discord   DiscordConfig   `mapstructure:"discord"`
    GitHub    GitHubConfig    `mapstructure:"github"`
    Temporal  TemporalConfig  `mapstructure:"temporal"`
    Qdrant    QdrantConfig    `mapstructure:"qdrant"`
}

type DiscordConfig struct {
    BotToken   string `mapstructure:"bot_token" validate:"required"`
    ChannelID  string `mapstructure:"channel_id" validate:"required"`
}

func LoadConfig() (*Config, error) {
    viper.SetEnvPrefix("ITERATESWARM")
    viper.AutomaticEnv()

    viper.SetDefault("DISCORD_BOT_TOKEN", "")
    viper.SetDefault("TEMPORAL_ADDRESS", "localhost:7233")

    if err := viper.ReadInConfig(); err != nil {
        if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
            return nil, err
        }
    }

    var config Config
    if err := viper.Unmarshal(&config); err != nil {
        return nil, err
    }

    return &config, config.Validate()
}
```

### 2.4 Important: Health Checks & Readiness Probes

**Current State:**
```go
app.Get("/health", func(c *fiber.Ctx) error {
    return c.SendString("OK")
})
```

**Problem:** No dependency checks.

**My Fix:**
```go
func (h *Handlers) HealthCheck(c *fiber.Ctx) error {
    checks := map[string]string{}

    // Check Temporal
    if _, err := h.temporalClient.GetSystemInfo(); err != nil {
        checks["temporal"] = "DOWN: " + err.Error()
    } else {
        checks["temporal"] = "UP"
    }

    // Check gRPC connectivity
    if err := h.grpcClient.HealthCheck(); err != nil {
        checks["ai_service"] = "DOWN: " + err.Error()
    } else {
        checks["ai_service"] = "UP"
    }

    // Check Redpanda
    if err := h.redpandaClient.Ping(); err != nil {
        checks["redpanda"] = "DOWN"
    } else {
        checks["redpanda"] = "UP"
    }

    // Aggregate status
    down := 0
    for _, status := range checks {
        if strings.Contains(status, "DOWN") {
            down++
        }
    }

    statusCode := fiber.StatusOK
    if down > 0 {
        statusCode = fiber.StatusServiceUnavailable
    }

    return c.Status(statusCode).JSON(fiber.Map{
        "status":  map[bool]string{true: "healthy", false: "degraded"}[down == 0],
        "checks":  checks,
        "uptime":  time.Since(startTime).String(),
    })
}
```

### 2.5 Important: Rate Limiting

**Current State:** None.

**Problem:** Discord and GitHub have rate limits. No protection.

**My Fix:**
```go
import "golang.org/x/time/rate"

type RateLimiter struct {
    discord *rate.Limiter
    github  *rate.Limiter
}

func NewRateLimiter() *RateLimiter {
    return &RateLimiter{
        discord: rate.NewLimiter(rate.Limit(5), 10),   // 5 req/sec, burst 10
        github:  rate.NewLimiter(rate.Limit(10), 20), // 10 req/sec, burst 20
    }
}

func (a *Activities) SendDiscordApproval(ctx context.Context, ...) error {
    if !a.rateLimiter.discord.Allow() {
        return fmt.Errorf("rate limited: try again in %v", time.Second)
    }
    // ... API call
}
```

---

## Part 3: What I'd REFACTOR (Design Improvements)

### 3.1 Unify Activity Registration

**Current State:** Activities are registered inline in worker/main.go:

```go
worker.RegisterActivity(workflow.AnalyzeFeedback)
worker.RegisterActivity(workflow.SendDiscordApproval)
```

**Problem:** No dependency injection, hard to test.

**My Fix - Factory Pattern:**
```go
// internal/workflow/activities.go
type ActivityRegistry interface {
    RegisterAll(w worker.Registry)
}

type ActivityFactory struct {
    config     *Config
    grpcClient *grpc.Client
    rateLimiter *RateLimiter
}

func (f *ActivityFactory) CreateActivities() *Activities {
    return &Activities{
        config:      f.config,
        grpcClient:  f.grpcClient,
        rateLimiter: f.rateLimiter,
    }
}

func (f *ActivityFactory) RegisterAll(w worker.Registry) {
    activities := f.CreateActivities()

    w.RegisterActivityWithOptions(
        activities.AnalyzeFeedback,
        worker.ActivityOptions{
            Name:             "AnalyzeFeedback",
            StartToCloseTimeout: 2 * time.Minute,
            RetryPolicy: &temporal.RetryPolicy{
                InitialInterval:    time.Second,
                BackoffCoefficient: 2.0,
                MaximumInterval:    time.Minute,
                MaximumAttempts:   3,
            },
        },
    )

    // Register others...
}
```

### 3.2 Extract Configuration to Separate Module

**Current State:** Configuration scattered across files.

**My Fix:**
```
internal/config/
├── config.go           # Main config struct
├── discord.go         # Discord-specific config
├── github.go          # GitHub-specific config
├── temporal.go        # Temporal-specific config
└── validation.go      # Config validation
```

### 3.3 Use Interface for gRPC Client

**Current State:**
```go
type Client struct {
    conn   *grpc.ClientConn
    client pb.AgentServiceClient
}
```

**Problem:** Tight coupling, hard to mock.

**My Fix:**
```go
// Internal interface for testing
type AgentServiceClient interface {
    AnalyzeFeedback(ctx context.Context, text, source, userID string) (*pb.AnalyzeFeedbackResponse, error)
    Close() error
}

// Implementation wraps generated client
type GRPCClient struct {
    client pb.AgentServiceClient
    conn   *grpc.ClientConn
}

// Mock for testing
type MockClient struct {
    AnalyzeFeedbackFunc func(ctx context.Context, text, source, userID string) (*pb.AnalyzeFeedbackResponse, error)
}
```

---

## Part 4: What I'd REMOVE (Technical Debt)

### 4.1 Remove Unused Imports

```go
// In activities.go - THIS IS DEAD CODE
import (
    "strconv"  // NOT USED
    "github.com/google/go-github/v50/github"  // USED
)
```

### 4.2 Remove Hardcoded Values

**Current:**
```go
workflow.AwaitWithTimeout(ctx, 5*time.Minute, ...)  // Magic number
```

**Fix:**
```go
const (
    ApprovalTimeout = 5 * time.Minute
    ActivityTimeout = 2 * time.Minute
    MaxRetries      = 3
)
```

### 4.3 Remove Redundant Code

**Current:** `NewClient` and `NewClientWithoutBlock` are 95% identical.

**Fix:**
```go
func NewClient(addr string, block bool) (*Client, error) {
    opts := []grpc.DialOption{
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    }

    if block {
        opts = append(opts, grpc.WithBlock())
    }

    conn, err := grpc.Dial(addr, opts...)
    // ...
}
```

---

## Part 5: Recommended File Structure

```
apps/core/
├── cmd/
│   ├── server/
│   │   └── main.go              # Fiber server
│   └── worker/
│       └── main.go              # Temporal worker
│
├── internal/
│   ├── api/
│   │   ├── handlers.go         # HTTP handlers
│   │   ├── middleware.go       # Fiber middleware
│   │   └── routes.go           # Route definitions
│   │
│   ├── config/
│   │   ├── config.go           # Main config
│   │   ├── discord.go          # Discord config
│   │   ├── github.go          # GitHub config
│   │   └── validation.go       # Config validation
│   │
│   ├── grpc/
│   │   ├── client.go           # gRPC client interface
│   │   ├── client_impl.go      # gRPC client implementation
│   │   └── mock.go            # Mock client for testing
│   │
│   ├── observability/
│   │   ├── tracer.go          # OpenTelemetry setup
│   │   ├── metrics.go         # Prometheus metrics
│   │   └── logger.go          # Structured logging
│   │
│   ├── rate/
│   │   └── limiter.go         # Rate limiting
│   │
│   ├── redpanda/
│   │   ├── client.go          # Kafka producer
│   │   └── consumer.go        # Kafka consumer (if needed)
│   │
│   ├── temporal/
│   │   ├── client.go          # Temporal client wrapper
│   │   └── worker.go         # Worker factory
│   │
│   └── workflow/
│       ├── workflow.go        # Workflow definition
│       ├── activities.go      # Activity implementations
│       └── factory.go        # Activity factory
│
├── pkg/
│   ├── discord/
│   │   ├── client.go         # Discord API client
│   │   └── embed.go         # Embed builders
│   │
│   └── github/
│       ├── client.go         # GitHub API client
│       └── issue.go         # Issue builders
│
├── test/
│   ├── fixtures/            # Test data
│   ├── mocks/               # Generated mocks
│   └── integration/         # Integration tests
│
├── config.yaml              # Configuration file
├── config.example.yaml      # Example config
└── Dockerfile
```

---

## Part 6: Recommended Add-ons

### 6.1 Docker Production Ready

```dockerfile
# apps/core/Dockerfile
FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" \
    -o bin/server ./cmd/server
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" \
    -o bin/worker ./cmd/worker

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

COPY --from=builder /app/bin/server /app/bin/worker /app/

EXPOSE 3000 7233

ENTRYPOINT ["/app/server"]
CMD ["/app/worker"]
```

### 6.2 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.23'

      - name: Run Go tests
        run: |
          cd apps/core
          go mod download
          go test -race -cover ./...

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Run Python tests
        run: |
          cd apps/ai
          uv sync
          uv run pytest --cov=src tests/

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run golangci-lint
        uses: golangci/golangci-lint-action@v5
        with:
          version: latest
          working-directory: apps/core

      - name: Run ruff
        run: |
          cd apps/ai
          uv run ruff check src/

  build:
    needs: [test, lint]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Go binary
        run: |
          cd apps/core
          go build -o iterateswarm-core ./...

      - name: Build Docker image
        run: |
          docker build -t iterateswarm:${{ github.sha }} .
```

### 6.3 Kubernetes Helm Chart (Future)

```
helm/
├── iterateswarm/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── templates/
│   │   ├── deployment-core.yaml
│   │   ├── deployment-ai.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   └── configmap.yaml
│   └── values-production.yaml
```

---

## Part 7: Priority Matrix

| Priority | Change | Effort | Impact | Why |
|----------|--------|--------|--------|-----|
| **P0** | Add retry policies (tenacity) | 2h | High | Prevents cascade failures |
| **P0** | Add structured logging | 1h | High | Debug production issues |
| **P0** | Health checks with deps | 3h | High | Kubernetes readiness |
| **P1** | Rate limiting | 2h | Medium | Prevent rate limit bans |
| **P1** | Config validation | 2h | Medium | Fail fast on bad config |
| **P1** | OpenTelemetry tracing | 4h | High | Debug distributed system |
| **P2** | Dependency injection | 8h | Medium | Testability |
| **P2** | Prometheus metrics | 4h | Medium | Monitoring |
| **P3** | Docker multi-stage | 2h | Low | Smaller images |
| **P3** | Kubernetes Helm | 8h | Low | Deployment |

---

## Part 8: Immediate Action Items

### This Week (8 hours)

```bash
# 1. Add tenacity for retries
cd apps/core
go get github.com/raft-tech/tenacity

# 2. Add structured logging
go get github.com/samber/slog-fiber

# 3. Create config.yaml
cat > config.yaml << 'EOF'
discord:
  bot_token: "${DISCORD_BOT_TOKEN}"
  channel_id: "${DISCORD_CHANNEL_ID}"

github:
  token: "${GITHUB_TOKEN}"
  owner: "${GITHUB_OWNER}"
  repo: "${GITHUB_REPO}"

temporal:
  address: "localhost:7233"
  namespace: "default"

qdrant:
  url: "http://localhost:6333"
EOF
```

### This Sprint (2 weeks)

1. **Day 1-2:** Refactor configuration management
2. **Day 3-4:** Add retry policies and rate limiting
3. **Day 5:** Add comprehensive health checks
4. **Day 6-7:** OpenTelemetry integration

### Next Quarter (Tech Debt)

1. Dependency injection framework
2. Prometheus metrics endpoint
3. Kubernetes Helm charts
4. CI/CD pipeline with Docker builds

---

## Summary

| Category | Current | Target | Gap |
|----------|---------|--------|-----|
| **Resilience** | 3/10 | 8/10 | Retry, circuit breaker, rate limiting |
| **Observability** | 2/10 | 8/10 | Tracing, metrics, structured logs |
| **Config** | 4/10 | 8/10 | Validation, defaults, env prefix |
| **Testability** | 5/10 | 8/10 | Dependency injection, mocks |
| **Deployability** | 3/10 | 7/10 | Docker, Helm (partial) |

**Bottom Line:** You have a solid architectural foundation. The gaps are in production hardening, not design. Focus on resilience and observability before adding features.

---

*Review by: Staff+ Architect*
*Date: 2026-02-04*
*Confidence Level: High*
