# IterateSwarm Architecture Analysis

## Executive Summary

IterateSwarm is a **polyglot, event-driven ChatOps platform** that transforms unstructured user feedback into production-ready GitHub issues through an AI-powered workflow. This document provides a deep dive into the architectural decisions, design patterns, and implementation details.

---

## Table of Contents

1. [High-Level Design (HLD)](#1-high-level-design-hld)
2. [Low-Level Design (LLD)](#2-low-level-design-lld)
3. [Design Patterns](#3-design-patterns)
4. [Architectural Decisions](#4-architectural-decisions)
5. [Technology Choices & Rationale](#5-technology-choices--rationale)
6. [Data Flow Analysis](#6-data-flow-analysis)
7. [Component Anatomy](#7-component-anatomy)
8. [Trade-offs & Future Considerations](#8-trade-offs--future-considerations)

---

## 1. High-Level Design (HLD)

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IterateSwarm System                                 │
│                                                                             │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐           │
│  │ Discord  │     │  GitHub  │     │  LLM     │     │  User    │           │
│  │  (API)   │     │   (API)  │     │ Provider │     │ Feedback │           │
│  └────┬─────┘     └────┬─────┘     └────┬─────┘     └──────────┘           │
│       │                │                │                                      │
│       └────────────────┴────────────────┘                                      │
│                              │                                                 │
│                              ▼                                                 │
│              ┌─────────────────────────────────┐                               │
│              │      Go Core Service            │                               │
│              │   (Fiber + Temporal Worker)     │                               │
│              │                                 │                               │
│              │  ┌───────────────────────────┐  │                               │
│              │  │  HTTP Gateway              │  │                               │
│              │  │  - Webhook handlers       │  │                               │
│              │  │  - Interaction handlers   │  │                               │
│              │  └───────────────────────────┘  │                               │
│              │                                 │                               │
│              │  ┌───────────────────────────┐  │                               │
│              │  │  Temporal Orchestrator   │  │                               │
│              │  │  - Workflow definition   │  │                               │
│              │  │  - Activity coordination│  │                               │
│              │  └───────────────────────────┘  │                               │
│              └─────────────────────────────────┘                               │
│                              │                                                 │
│                              ▼                                                 │
│              ┌─────────────────────────────────┐                               │
│              │      Python AI Service           │                               │
│              │   (LangGraph + gRPC Server)      │                               │
│              │                                 │                               │
│              │  ┌───────────────────────────┐  │                               │
│              │  │  gRPC Server             │  │                               │
│              │  │  - AnalyzeFeedback RPC   │  │                               │
│              │  └───────────────────────────┘  │                               │
│              │                                 │                               │
│              │  ┌───────────────────────────┐  │                               │
│              │  │  LangGraph Agents        │  │                               │
│              │  │  - Triage Agent          │  │                               │
│              │  │  - Spec Agent           │  │                               │
│              │  └───────────────────────────┘  │                               │
│              └─────────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────────┐
              │      Infrastructure            │
              │                                 │
              │  ┌─────────┐  ┌─────────────┐  │
              │  │Temporal │  │  Redpanda   │  │
              │  │ Server │  │  (Kafka)    │  │
              │  └─────────┘  └─────────────┘  │
              │                                 │
              │  ┌─────────┐  ┌─────────────┐  │
              │  │PostgreSQL│  │   Qdrant   │  │
              │  │  (SQL)  │  │  (Vector)  │  │
              │  └─────────┘  └─────────────┘  │
              └─────────────────────────────────┘
```

### 1.2 Core Principles

| Principle | Implementation |
|-----------|---------------|
| **Polyglot** | Go for orchestration, Python for AI - each language plays to its strengths |
| **Event-Driven** | Temporal for workflow state, Redpanda for async messaging |
| **Type-Safe** | Protocol Buffers for gRPC contracts |
| **Observable** | Temporal UI for tracing, structured logging |
| **Resilient** | Graceful degradation when external APIs are unavailable |

---

## 2. Low-Level Design (LLD)

### 2.1 Go Core Service Architecture

```
apps/core/
├── cmd/
│   ├── server/main.go          # Fiber HTTP server entrypoint
│   └── worker/main.go          # Temporal worker entrypoint
│
└── internal/
    ├── api/
    │   └── handlers.go         # HTTP handlers (webhooks, health)
    │
    ├── grpc/
    │   └── client.go           # gRPC client to Python AI
    │
    ├── redpanda/
    │   └── client.go           # Kafka producer/consumer
    │
    ├── temporal/
    │   └── client.go           # Temporal SDK wrapper
    │
    └── workflow/
        ├── workflow.go         # FeedbackWorkflow definition
        └── activities.go       # Activity implementations
```

### 2.2 Python AI Service Architecture

```
apps/ai/
├── src/
│   ├── agents/
    │   ├── triage.py          # Triage LangGraph agent
    │   └── spec.py            # Spec generation LangGraph agent
    │
    ├── grpc_server.py          # gRPC service implementation
    │   └── main.py             # Unified entrypoint (Temporal + gRPC)
│
└── tests/
    ├── test_grpc_server.py     # gRPC server tests
    ├── test_agents.py          # Agent logic tests
    └── test_agent_logic.py     # LLM evaluation tests
```

### 2.3 gRPC Contract (Protocol Buffers)

```protobuf
// proto/ai/v1/agent.proto
syntax = "proto3";

package ai.v1;

// Service definition
service AgentService {
    // Analyzes feedback and returns structured issue specification
    rpc AnalyzeFeedback(AnalyzeFeedbackRequest) returns (AnalyzeFeedbackResponse);
}

// Request message
message AnalyzeFeedbackRequest {
    string text = 1;      // The feedback text to analyze
    string source = 2;     // Where the feedback came from (discord, slack, etc.)
    string user_id = 3;    // ID of the user who submitted feedback
}

// Response message
message AnalyzeFeedbackResponse {
    IssueSpec spec = 1;       // Structured issue specification
    bool is_duplicate = 2;     // Whether this is a duplicate
    string reasoning = 3;      // AI's reasoning for classification
}

// Issue specification
message IssueSpec {
    string title = 1;
    string description = 2;
    IssueType type = 3;
    Severity severity = 4;
    repeated string labels = 5;
    string confidence = 6;
}

// Enums
enum IssueType {
    ISSUE_TYPE_UNSPECIFIED = 0;
    ISSUE_TYPE_BUG = 1;
    ISSUE_TYPE_FEATURE = 2;
    ISSUE_TYPE_QUESTION = 3;
}

enum Severity {
    SEVERITY_UNSPECIFIED = 0;
    SEVERITY_LOW = 1;
    SEVERITY_MEDIUM = 2;
    SEVERITY_HIGH = 3;
    SEVERITY_CRITICAL = 4;
}
```

---

## 3. Design Patterns

### 3.1 Repository Pattern

**Location:** `apps/core/internal/grpc/client.go`

```go
// The gRPC client wraps the raw connection
type Client struct {
    conn   *grpc.ClientConn
    client pb.AgentServiceClient
}

// Abstraction over the transport layer
func (c *Client) AnalyzeFeedback(ctx context.Context, text, source, userID string) (*pb.AnalyzeFeedbackResponse, error) {
    // Internal implementation details hidden from callers
}
```

**Why:** Provides clean abstraction over gRPC connection management and allows for testing with mocks.

### 3.2 Strategy Pattern

**Location:** `apps/core/internal/workflow/activities.go`

```go
// Activity interface (implicit via function names)
type Activities struct {
    aiClient *grpc.Client
}

// Different strategies for different external services
func (a *Activities) SendDiscordApproval(...) error { ... }
func (a *Activities) CreateGitHubIssue(...) (string, error) { ... }
```

**Why:** Each activity is a separable strategy that can be modified independently.

### 3.3 Factory Pattern

**Location:** `apps/core/internal/workflow/activities.go`

```go
func NewActivities(aiClient *grpc.Client) *Activities {
    return &Activities{aiClient: aiClient}
}
```

**Why:** Decouples activity creation from usage and enables dependency injection.

### 3.4 State Machine Pattern

**Location:** `apps/core/internal/workflow/workflow.go`

```go
func FeedbackWorkflow(ctx workflow.Context, input FeedbackInput) error {
    // State transitions:
    // 1. Analyze → (if duplicate) → End
    // 2. Analyze → Discord Approval → Wait for Signal → (if approved) → GitHub Issue → End
    //                                          → (if rejected) → End
    //                                          → (if timeout) → End
}
```

**Why:** Temporal provides built-in state machine semantics with durable execution.

### 3.5 Builder Pattern

**Location:** `apps/core/internal/workflow/activities.go`

```go
embed := &discordgo.MessageEmbed{
    Title:       fmt.Sprintf("%s New Issue Proposed: %s", emoji, input.IssueTitle),
    Description: truncateString(input.IssueBody, 4000),
    Color:       color,
    Fields: []*discordgo.MessageEmbedField{
        {Name: "Severity", Value: strings.ToUpper(input.Severity), Inline: true},
        // ... more fields
    },
}
```

**Why:** Complex object construction is made readable and flexible.

---

## 4. Architectural Decisions

### 4.1 Polyglot Architecture (Go + Python)

| Decision | Options Considered | Chosen Approach | Rationale |
|----------|-------------------|-----------------|-----------|
| **Orchestration Language** | Python, Go | **Go** | Type safety, performance, excellent Temporal SDK |
| **AI Processing** | Go, Python | **Python** | Rich ML ecosystem, LangGraph, OpenAI SDK |
| **Service Communication** | REST, gRPC, message queue | **gRPC** | Type safety via Protocol Buffers, performance |
| **Workflow Engine** | Temporal, Cadence, AWS Step Functions | **Temporal** | Best Go SDK, excellent debugging with UI |

**Trade-off Analysis:**

```
Pros of Polyglot:
├── Go: Strong typing, high performance, small binaries
├── Python: Best AI/ML ecosystem, rapid prototyping
└── gRPC: Type-safe contracts, code generation

Cons of Polyglot:
├── Added complexity in deployment
├── gRPC code generation overhead
└── Cross-language debugging challenges

mitigation:
├── Docker Compose for local development
├── Protocol Buffers for contract-first development
└── Temporal for observability across services
```

### 4.2 gRPC Communication Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    gRPC Communication Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Temporal Worker (Go)                                           │
│       │                                                         │
│       │ 1. Prepare AnalyzeFeedbackRequest                        │
│       │    - text: "The app crashes on startup"                │
│       │    - source: "discord"                                  │
│       │    - user_id: "user123"                                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │  gRPC Client (Go)                       │                   │
│  │  - Connection pooling                   │                   │
│  │  - Request serialization                │                   │
│  │  - Response deserialization             │                   │
│  └─────────────────────────────────────────┘                   │
│                         │                                     │
│                         │ 2. gRPC Request                     │
│                         │ (HTTP/2 + Protobuf)                │
│                         ▼                                     │
│  ┌─────────────────────────────────────────┐                   │
│  │  gRPC Server (Python)                   │                   │
│  │  - Deserialize request                 │                   │
│  │  - Call LangGraph agents               │                   │
│  │  - Serialize response                  │                   │
│  └─────────────────────────────────────────┘                   │
│                         │                                     │
│                         │ 3. gRPC Response                     │
│                         │ (HTTP/2 + Protobuf)                │
│                         ▼                                     │
│       ┌─────────────────────────────────────┐                 │
│       │  Temporal Worker processes result  │                 │
│       │  - Store in workflow state        │                 │
│       │  - Continue workflow              │                 │
│       └─────────────────────────────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Decision Record:** gRPC was chosen over REST because:
1. **Type Safety:** Protocol Buffers ensure compile-time type checking
2. **Performance:** HTTP/2 + binary serialization is faster than JSON/REST
3. **Code Generation:** buf generates both client and server stubs
4. **Bidirectional Streaming:** Enables future enhancements like streaming responses

### 4.3 Workflow State Management

```go
// FeedbackWorkflow demonstrates Temporal's state management
func FeedbackWorkflow(ctx workflow.Context, input FeedbackInput) error {
    // Activities are executed with automatic retry
    err := workflow.ExecuteActivity(ctx, "AnalyzeFeedback", input).Get(ctx, &result)

    // Signals pause execution until external event
    signalChan := workflow.GetSignalChannel(ctx, "user-action")

    // Timeouts prevent indefinite waiting
    _, _ = workflow.AwaitWithTimeout(ctx, 5*time.Minute, func() bool {
        return signalChan.ReceiveAsync(&signalValue)
    })

    // Workflow state is automatically persisted
    return nil
}
```

**Why Temporal over alternatives:**

| Feature | Temporal | AWS Step Functions | Custom Solution |
|---------|----------|-------------------|------------------|
| **Go SDK** | Excellent | Good | N/A |
| **Local Development** | Docker available | AWS only | Complex |
| **Debugging** | Replay + UI | Limited | Custom needed |
| **Persistence** | Built-in | Managed | DIY |
| **Cost** | Self-hosted free | Pay-per-state | Server costs |

### 4.4 Event Sourcing with Redpanda

```
┌─────────────────────────────────────────────────────────────────┐
│                    Redpanda Event Flow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User submits feedback via Discord webhook                       │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │  Fiber HTTP Server                     │                    │
│  │  - Validates incoming request          │                    │
│  │  - Parses JSON payload                 │                    │
│  └─────────────────────────────────────────┘                    │
│                          │                                      │
│                          │ Produce event                        │
│                          ▼                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │  Redpanda Topic: feedback-events       │                    │
│  │                                         │                    │
│  │  Event Schema:                         │                    │
│  │  {                                     │                    │
│  │    "feedback_id": "uuid",             │                    │
│  │    "content": "text",                 │                    │
│  │    "source": "discord",               │                    │
│  │    "user_id": "user123",             │                    │
│  │    "timestamp": "ISO8601"            │                    │
│  │  }                                     │                    │
│  └─────────────────────────────────────────┘                    │
│                          │                                      │
│                          │ Consume event                        │
│                          ▼                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │  Temporal Worker                        │                    │
│  │  - Starts FeedbackWorkflow              │                    │
│  │  - Passes feedback as input            │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why Redpanda over Kafka:**
- **Performance:** 10x faster than Kafka in benchmarks
- **Compatibility:** Kafka protocol compatible (no vendor lock-in)
- **Simplicity:** Single binary, no JVM required
- **Cost:** Self-hosted, no managed service cost

---

## 5. Technology Choices & Rationale

### 5.1 Orchestration: Go + Temporal

```go
// apps/core/internal/temporal/client.go
type Client struct {
    Client client.Client
}

func NewClient(hostPort, namespace string) (*Client, error) {
    c, err := client.Dial(&client.Config{
        HostPort:  hostPort,
        Namespace: namespace,
    })
    return &Client{Client: c}, err
}
```

**Why Go?**
- **Type Safety:** Critical for workflow definitions
- **Performance:** Low latency for high-throughput scenarios
- **Concurrency:** goroutines + channels for concurrent activities
- **SDK Quality:** Temporal's Go SDK is the reference implementation

### 5.2 AI Processing: Python + LangGraph

```python
# apps/ai/src/agents/triage.py
class TriageAgent:
    """LangGraph agent for feedback classification."""

    def create_workflow(self) -> StateGraph:
        graph = StateGraph(TriageState)

        # Define nodes
        graph.add_node("classify", self._classify_feedback)
        graph.add_node("assess_severity", self._assess_severity)
        graph.add_node("generate_reasoning", self._generate_reasoning)

        # Define edges
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "assess_severity")
        graph.add_edge("assess_severity", "generate_reasoning")
        graph.add_edge("generate_reasoning", END)

        return graph.compile()
```

**Why Python?**
- **LangGraph:** Best-in-class for agentic workflows
- **OpenAI SDK:** First-class support
- **Vector Libraries:** Qdrant, sentence-transformers support
- **Rapid Prototyping:** Easy to experiment with prompts

### 5.3 API Gateway: Fiber (Go)

```go
// apps/core/internal/api/handlers.go
func SetupRoutes(app *fiber.App, handlers *Handlers) {
    app.Get("/health", handlers.Health)

    webhooks := app.Group("/webhooks")
    webhooks.Post("/discord", handlers.DiscordWebhook)
    webhooks.Post("/interaction", handlers.DiscordInteraction)

    test := app.Group("/test")
    test.Get("/kafka", handlers.TestKafka)
}
```

**Why Fiber over Gin/Chi?**
- **Express-like:** Easy for developers familiar with Node.js
- **Performance:** 2x faster than Gin in benchmarks
- **Middleware:** Rich ecosystem of middleware
- **Context:** Similar to Node.js req/res pattern

### 5.4 Vector Database: Qdrant

```python
# apps/ai/src/services/qdrant.py
class QdrantService:
    """Vector similarity search for duplicate detection."""

    async def find_similar(self, text: str, threshold: float = 0.85) -> tuple[bool, float]:
        """Find similar feedback to detect duplicates."""
        query_vector = self.embeddings.encode(text)

        search_result = await self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            score_threshold=threshold,
        )

        return len(search_result.points) > 0, search_result.points[0].score if search_result.points else 0.0
```

**Why Qdrant over Pinecone/Weaviate?**
- **Self-hosted:** No vendor lock-in, no per-query costs
- **Performance:** Rust-based, excellent memory efficiency
- **Python SDK:** First-class async support
- **Open Source:** Community-driven development

---

## 6. Data Flow Analysis

### 6.1 End-to-End Request Flow

```
Step 1: Feedback Submission
────────────────────────────────────────
User posts: "The app crashes when I click Save"
                    │
                    ▼
Discord Webhook → Go Fiber Server
                    │
                    ▼
Parse JSON, validate structure
                    │
                    ▼
Produce to Redpanda topic: feedback-events
```

```
Step 2: Workflow Initiation
────────────────────────────────────────
Temporal Worker consumes Redpanda event
                    │
                    ▼
Start FeedbackWorkflow with input:
{
  "text": "The app crashes...",
  "source": "discord",
  "user_id": "user123",
  "channel_id": "channel456"
}
                    │
                    ▼
Temporal persists workflow state
```

```
Step 3: AI Analysis (gRPC)
────────────────────────────────────────
Workflow executes AnalyzeFeedback activity
                    │
                    ▼
Go gRPC client → Python gRPC Server
Request: AnalyzeFeedbackRequest(text="...", source="...", user_id="...")
                    │
                    ▼
Python service calls LangGraph agents
                    │
                    ├──→ Triage Agent (classify: bug/feature/question)
                    ├──→ Spec Agent (generate title/description)
                    └──→ Qdrant (check duplicates)
                    │
                    ▼
Response: AnalyzeFeedbackResponse(
  spec=IssueSpec(title="Fix crash...", type=BUG, severity=HIGH),
  is_duplicate=false,
  reasoning="User reported..."
)
```

```
Step 4: Human Approval
────────────────────────────────────────
Workflow executes SendDiscordApproval activity
                    │
                    ▼
Discord Bot sends embed with buttons:
┌─────────────────────────────────────┐
│ 🐛 New Issue Proposed: Fix crash    │
│ on Save                             │
│                                     │
│ Severity: HIGH  │ Type: BUG        │
│ Labels: bug, crash, high-priority  │
│                                     │
│ [✅ Approve]  [❌ Reject]           │
└─────────────────────────────────────┘
                    │
                    ▼
Workflow waits for signal (5 min timeout)
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
  Approve         Reject         Timeout
    │               │               │
    ▼               ▼               ▼
  Create         End           End
  GitHub
  Issue
```

### 6.2 Data Transformation Pipeline

```
Raw Feedback
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Python Triage Agent                                        │
│  - Classifies: bug/feature/question                        │
│  - Assesses severity: low/medium/high/critical             │
│  - Generates reasoning: "User reported a crash..."          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Python Spec Agent                                          │
│  - Generates title: "Fix crash on Save"                    │
│  - Generates description with steps                        │
│  - Suggests labels: ["bug", "crash", "high-priority"]     │
│  - Calculates confidence score                             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Go Workflow State                                         │
│  - Persists issue spec                                    │
│  - Tracks duplicate status                                 │
│  - Records AI reasoning                                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Discord Embed (Human-in-the-loop)                         │
│  - Emoji: 🐛/✨/❓ based on type                           │
│  - Color: Red/Orange/Yellow/Green based on severity        │
│  - Fields: Severity, Type, Labels, Workflow ID             │
│  - Components: Approve/Reject buttons                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Component Anatomy

### 7.1 Go Core Service Deep Dive

#### HTTP Handlers (`internal/api/handlers.go`)

```go
// DiscordWebhook handles incoming feedback from Discord
func (h *Handlers) DiscordWebhook(c *fiber.Ctx) error {
    var payload discordPayload
    if err := c.BodyParser(&payload); err != nil {
        return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
            "error": "Invalid payload",
        })
    }

    // Extract feedback text from Discord message
    feedback := extractFeedbackText(payload)
    if feedback == "" {
        return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
            "error": "No feedback text found",
        })
    }

    // Publish to Redpanda
    event := FeedbackEvent{
        ID:        uuid.New().String(),
        Text:      feedback,
        Source:    "discord",
        UserID:    payload.Author.ID,
        ChannelID: payload.ChannelID,
        Timestamp: time.Now().UTC(),
    }

    if err := h.redpandaClient.Publish("feedback-events", event); err != nil {
        return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
            "error": "Failed to publish event",
        })
    }

    return c.JSON(fiber.Map{
        "status":  "accepted",
        "message": "Feedback received and queued for processing",
    })
}
```

#### Temporal Workflow (`internal/workflow/workflow.go`)

```go
func FeedbackWorkflow(ctx workflow.Context, input FeedbackInput) error {
    // 1. Set activity options with timeouts
    ao := workflow.ActivityOptions{
        StartToCloseTimeout: 2 * time.Minute,
        HeartbeatTimeout:    30 * time.Second,
    }
    ctx = workflow.WithActivityOptions(ctx, ao)

    // 2. Execute AI analysis activity
    var analyzeResult *AnalyzeFeedbackOutput
    err := workflow.ExecuteActivity(ctx, "AnalyzeFeedback", AnalyzeFeedbackInput{
        Text:      input.Text,
        Source:    input.Source,
        UserID:    input.UserID,
        ChannelID: input.ChannelID,
    }).Get(ctx, &analyzeResult)
    if err != nil {
        return err
    }

    // 3. Skip if duplicate
    if analyzeResult.IsDuplicate {
        return nil
    }

    // 4. Send Discord approval request
    err = workflow.ExecuteActivity(ctx, "SendDiscordApproval", SendDiscordApprovalInput{
        ChannelID:     input.ChannelID,
        IssueTitle:    analyzeResult.Title,
        IssueBody:     analyzeResult.Description,
        IssueLabels:   analyzeResult.Labels,
        Severity:      analyzeResult.Severity,
        IssueType:     analyzeResult.IssueType,
        WorkflowRunID: "workflow-" + input.UserID + "-" + input.Source,
    }).Get(ctx, nil)
    if err != nil {
        return err
    }

    // 5. Wait for signal with timeout
    signalChan := workflow.GetSignalChannel(ctx, "user-action")
    var signalValue string
    approved := false

    _, _ = workflow.AwaitWithTimeout(ctx, 5*time.Minute, func() bool {
        if signalChan.ReceiveAsync(&signalValue) {
            approved = signalValue == "approve"
            return true
        }
        return false
    })

    // 6. Create GitHub issue if approved
    if approved {
        _, err = workflow.ExecuteActivity(ctx, "CreateGitHubIssue", CreateGitHubIssueInput{
            Title:    analyzeResult.Title,
            Body:     analyzeResult.Description,
            Labels:   analyzeResult.Labels,
            RepoOwner: input.RepoOwner,
            RepoName:  input.RepoName,
        }).Get(ctx, nil)
    }

    return err
}
```

#### Activities (`internal/workflow/activities.go`)

**Discord Activity:**
```go
func (a *Activities) SendDiscordApproval(ctx context.Context, input SendDiscordApprovalInput) error {
    // Get Discord token from environment (graceful degradation)
    discordToken := os.Getenv("DISCORD_BOT_TOKEN")
    if discordToken == "" {
        log.Printf("DISCORD_BOT_TOKEN not set, skipping Discord notification")
        return nil  // Don't fail workflow for missing token
    }

    dg, err := discordgo.New("Bot " + discordToken)
    if err != nil {
        return fmt.Errorf("failed to create Discord session: %w", err)
    }

    // Create rich embed based on issue type and severity
    embed := &discordgo.MessageEmbed{
        Title:       fmt.Sprintf("%s New Issue Proposed: %s", emoji, input.IssueTitle),
        Description: truncateString(input.IssueBody, 4000),
        Color:       severityColor[input.Severity],
        Fields: []*discordgo.MessageEmbedField{
            {Name: "Severity", Value: strings.ToUpper(input.Severity), Inline: true},
            {Name: "Type", Value: strings.ToUpper(input.IssueType), Inline: true},
            {Name: "Labels", Value: strings.Join(input.IssueLabels, ", "), Inline: true},
        },
    }

    // Add buttons for approval
    approveBtn := discordgo.Button{
        Label:    "✅ Approve",
        Style:    discordgo.SuccessButton,
        CustomID: fmt.Sprintf("approve_%s", input.WorkflowRunID),
    }

    // Send message
    msg, err := dg.ChannelMessageSendComplex(input.ChannelID, &discordgo.MessageSend{
        Embeds:     []*discordgo.MessageEmbed{embed},
        Components: []discordgo.MessageComponent{discordgo.ActionsRow{Components: []discordgo.MessageComponent{approveBtn}}},
    })

    log.Printf("Discord approval request sent: message_id=%s", msg.ID)
    return err
}
```

**GitHub Activity:**
```go
func (a *Activities) CreateGitHubIssue(ctx context.Context, input CreateGitHubIssueInput) (string, error) {
    githubToken := os.Getenv("GITHUB_TOKEN")
    if githubToken == "" {
        log.Printf("GITHUB_TOKEN not set, skipping GitHub issue creation")
        return "", nil
    }

    // OAuth2 client for GitHub API
    ts := oauth2.StaticTokenSource(
        &oauth2.Token{AccessToken: githubToken},
    )
    tc := oauth2.NewClient(ctx, ts)
    client := github.NewClient(tc)

    issue, _, err := client.Issues.Create(ctx, owner, repo, &github.IssueRequest{
        Title:  &input.Title,
        Body:   &input.Body,
        Labels: &input.Labels,
    })

    issueURL := issue.GetHTMLURL()
    log.Printf("GitHub issue created: url=%s", issueURL)
    return issueURL, err
}
```

### 7.2 Python AI Service Deep Dive

#### gRPC Server (`apps/ai/src/grpc_server.py`)

```python
class AgentServicer(pb2_grpc.AgentServiceServicer):
    """gRPC service implementing the AgentService contract."""

    async def AnalyzeFeedback(self, request, context):
        """Analyze feedback and return structured issue specification."""

        # 1. Check for duplicates using Qdrant
        is_duplicate, similarity_score = await self.qdrant.check_duplicate(request.text)

        if is_duplicate:
            log.info(
                "Duplicate detected",
                text_preview=request.text[:100],
                score=similarity_score,
            )
            return pb2.AnalyzeFeedbackResponse(
                is_duplicate=True,
                reasoning=f"Duplicate detected with similarity score {similarity_score:.2f}",
            )

        # 2. Run triage agent for classification
        triage_result = await self.triage_agent.analyze(request.text)

        # 3. Generate detailed spec if bug/feature
        if triage_result.issue_type in ("bug", "feature"):
            spec_result = await self.spec_agent.generate_spec(
                request.text,
                triage_result.issue_type,
                triage_result.severity,
            )
        else:
            # For questions, create simple spec
            spec_result = SpecResult(
                spec=IssueSpec(
                    title=f"Question: {request.text[:50]}...",
                    description=request.text,
                    type=triage_result.issue_type,
                    severity=triage_result.severity,
                    labels=["question"],
                )
            )

        # 4. Index in Qdrant for future duplicate detection
        await self.qdrant.index_feedback(
            id=str(uuid.uuid4()),
            text=request.text,
            metadata={"type": triage_result.issue_type},
        )

        return pb2.AnalyzeFeedbackResponse(
            spec=spec_result.spec.to_proto(),
            is_duplicate=False,
            reasoning=triage_result.reasoning,
        )
```

#### LangGraph Triage Agent (`apps/ai/src/agents/triage.py`)

```python
class TriageAgent:
    """LangGraph agent for feedback classification."""

    def create_workflow(self) -> StateGraph:
        graph = StateGraph(TriageState)

        graph.add_node("classify", self._classify)
        graph.add_node("assess_severity", self._assess_severity)
        graph.add_node("generate_reasoning", self._generate_reasoning)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "assess_severity")
        graph.add_edge("assess_severity", "generate_reasoning")
        graph.set_finish_point("generate_reasoning")

        return graph.compile()

    async def _classify(self, state: TriageState) -> TriageState:
        """Classify feedback as bug/feature/question."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", CLASSIFICATION_PROMPT),
            ("human", state.content),
        ])

        result = await self.llm.with_structured_output(TriageResult).ainvoke(
            prompt.invoke({"content": state.content})
        )

        return {"classification": result.type, "severity": result.severity}
```

---

## 8. Trade-offs & Future Considerations

### 8.1 Current Trade-offs

| Area | Trade-off | Mitigation |
|------|-----------|------------|
| **Deployment Complexity** | Two services, multiple dependencies | Docker Compose, clear docs |
| **gRPC without streaming** | Simple request-response only | Future: streaming for long-running AI |
| **Synchronous AI calls** | LLM calls block workflow | Future: caching, async embeddings |
| **No caching layer** | Repeated AI calls for similar feedback | Qdrant provides deduplication |
| **No rate limiting** | Discord/GitHub API limits | Future: token bucket, backoff |

### 8.2 Scalability Considerations

```
Current Architecture          │  Future Scalability
─────────────────────────────┼─────────────────────────────────
Single Temporal worker        │  Multiple workers with task queues
                             │
Single gRPC server            │  Load-balanced gRPC with connection pooling
                             │
In-memory workflow state      │  Temporal handles state persistence
                             │
No message batching           │  Batch processing for high throughput
```

### 8.3 Future Enhancements

| Priority | Feature | Description |
|----------|---------|-------------|
| **High** | Discord Button Handler | Complete the approval workflow |
| **High** | GitHub Webhook Handler | Link PRs back to issues |
| **Medium** | Streaming gRPC | Token-by-token AI responses |
| **Medium** | Caching Layer | Redis for frequent queries |
| **Low** | Multi-language Support | Claude/Gemini as alternatives |
| **Low** | Analytics Dashboard | Feedback trends, metrics |

### 8.4 Security Considerations

| Layer | Current | Future |
|-------|---------|--------|
| **Authentication** | Discord webhook verify | OAuth2 for all APIs |
| **Authorization** | Channel ID validation | RBAC for approvals |
| **Secrets** | Environment variables | HashiCorp Vault |
| **Rate Limiting** | None | Token bucket per user |
| **Input Validation** | Basic parsing | Full schema validation |
| **Audit Logging** | Workflow logs | Immutable audit trail |

---

## Appendix A: File Inventory

### Go Core Service

| File | Lines | Purpose |
|------|-------|---------|
| `cmd/server/main.go` | 85 | Fiber HTTP server entrypoint |
| `cmd/worker/main.go` | 70 | Temporal worker entrypoint |
| `internal/api/handlers.go` | 210 | HTTP handlers + webhooks |
| `internal/grpc/client.go` | 120 | gRPC client to Python AI |
| `internal/redpanda/client.go` | 80 | Kafka producer |
| `internal/temporal/client.go` | 60 | Temporal SDK wrapper |
| `internal/workflow/workflow.go` | 100 | Workflow definition |
| `internal/workflow/activities.go` | 320 | Activity implementations |

### Python AI Service

| File | Lines | Purpose |
|------|-------|---------|
| `src/grpc_server.py` | 200 | gRPC service implementation |
| `src/main.py` | 140 | Unified entrypoint |
| `src/agents/triage.py` | 200 | LangGraph triage agent |
| `src/agents/spec.py` | 250 | LangGraph spec agent |
| `src/config.py` | 110 | Configuration management |

### Configuration

| File | Purpose |
|------|---------|
| `proto/ai/v1/agent.proto` | gRPC contract definition |
| `docker-compose.yml` | Infrastructure orchestration |
| `Makefile` | Development commands |
| `.gitignore` | Git ignore rules |

---

## Appendix B: Environment Variables

```bash
# Required for full functionality
export DISCORD_BOT_TOKEN="your-bot-token"
export GITHUB_TOKEN="your-github-token"
export GITHUB_OWNER="your-username"
export GITHUB_REPO="your-repo"
export OPENAI_API_KEY="your-api-key"

# Optional - defaults provided
export TEMPORAL_ADDRESS="localhost:7233"
export TEMPORAL_NAMESPACE="default"
export QDRANT_URL="http://localhost:6333"
```

---

*Document generated: 2026-02-03*
*Version: 1.0*
*Project: IterateSwarm v2.0 (Phase 5 Complete)*
