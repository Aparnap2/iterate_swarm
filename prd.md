# IterateSwarm Master Plan (ChatOps Pivot) - v2.0

This is the **Master Plan** for **IterateSwarm** - A Production-Grade Polyglot ChatOps Platform.

***

# **1. Product Requirements Document (PRD)**

**Product Name:** IterateSwarm
**One-Liner:** An event-driven autonomous agent swarm that turns unstructured user feedback into production-ready GitHub Issues via Discord/Slack.
**Architecture:** ChatOps - No dashboard, just Discord interactions.
**Status:** PHASE 5 COMPLETE - Production Ready

### **Core Features (MVP)**
1.  **Universal Ingestion:** Webhooks for Discord/Slack (Go + Fiber)
2.  **Semantic Deduplication:** Qdrant vector search to merge duplicate feedback
3.  **Agentic Triaging:** LangGraph agents classify (Bug/Feature/Question) and score severity
4.  **Spec Generation:** Agent drafts a structured GitHub Issue
5.  **Human-in-the-Loop (ChatOps):** Discord message with [Approve]/[Reject] buttons
6.  **Full Observability:** Temporal UI for workflow tracing
7.  **gRPC Communication:** Type-safe polyglot service communication

***

# **2. System Architecture (Polyglot Temporal)**

### **The Tech Stack**

| Component | Tech Choice | Purpose |
|-----------|-------------|---------|
| **Ingestion API** | Go + Fiber | High-performance webhook receiver |
| **Orchestration** | Temporal | Workflow state machine |
| **AI Worker** | Python + LangGraph | LLM processing (OpenRouter compatible) |
| **Service Communication** | gRPC + Protocol Buffers | Type-safe polyglot IPC |
| **Vector DB** | Qdrant | Semantic duplicate detection |
| **Event Bus** | Redpanda | Kafka-compatible message buffer |
| **Primary DB** | PostgreSQL | App data persistence |
| **Interface** | Discord | ChatOps (Block Kit buttons) |
| **Code Generation** | Buf | Protocol buffer compilation |

### **High-Level Data Flow**

```mermaid
graph TD
    User((User)) -->|Feedback| Discord[Discord Webhook]
    Discord -->|POST /webhooks| GoGateway[Go Gateway (Fiber)]

    subgraph "Event Ingestion"
        GoGateway -->|Produce| Redpanda[(Redpanda / Kafka)]
    end

    subgraph "Orchestration (Go)"
        Redpanda -->|Consume| TemporalWorker[Temporal Worker]
        TemporalWorker <-->|State| TemporalServer[Temporal Server]
    end

    subgraph "AI Intelligence (Python)"
        TemporalWorker -->|gRPC / AnalyzeFeedback| PythonService[Python Agent Service]
        PythonService -->|LangGraph| AgentLogic{Agent Logic}
        AgentLogic -->|Query| Qdrant[(Qdrant Vector DB)]
        AgentLogic -->|Generate| LLM[LLM (OpenRouter)]
    end

    subgraph "Action"
        TemporalWorker -->|Approve?| DiscordBot[Discord Bot (Buttons)]
        DiscordBot -->|Signal| TemporalWorker
        TemporalWorker -->|If Approved| GitHub[GitHub API]
    end
```

### **Polyglot Workflow Pattern**

1.  **Workflow Definition (Go):** The "Manager" - defines steps, waits for signals
2.  **Activity A (Python via gRPC):** The "Specialist" - AI processing (LangGraph agents)
3.  **Activity B (Go):** The "Generalist" - Discord/GitHub API calls

**gRPC Contract:**
```protobuf
service AgentService {
    rpc AnalyzeFeedback(AnalyzeFeedbackRequest) returns (AnalyzeFeedbackResponse);
}

message AnalyzeFeedbackRequest {
    string text = 1;
    string source = 2;
    string user_id = 3;
}

message AnalyzeFeedbackResponse {
    IssueSpec spec = 1;
    bool is_duplicate = 2;
    string reasoning = 3;
}
```

***

# **3. Data Models**

### **Workflow State (Temporal)**

```go
type FeedbackInput struct {
    Text      string
    Source    string
    UserID    string
    ChannelID string
    RepoOwner string
    RepoName  string
}

type IssueSpec struct {
    Title       string
    Description string
    Type        IssueType     // bug, feature, question
    Severity    Severity      // low, medium, high, critical
    Labels      []string
    Confidence  float64
}
```

### **PostgreSQL (App Data)**

```sql
CREATE TABLE feedback (
    id UUID PRIMARY KEY,
    content TEXT,
    source VARCHAR(50),
    status VARCHAR(20),  -- pending, approved, rejected
    issue_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

***

# **4. Project Structure**

```
iterate_swarm/
├── apps/
│   ├── core/                    # Go orchestration service
│   │   ├── cmd/
│   │   │   ├── server/         # HTTP API server (Fiber)
│   │   │   └── worker/         # Temporal worker
│   │   └── internal/
│   │       ├── api/            # HTTP handlers & webhooks
│   │       ├── grpc/           # gRPC client to Python AI
│   │       ├── redpanda/       # Kafka client
│   │       ├── temporal/       # Temporal client wrapper
│   │       └── workflow/       # Workflow & activities
│   │
│   └── ai/                     # Python AI service
│       ├── src/
│       │   ├── agents/         # LangGraph agents
│       │   ├── grpc_server.py  # gRPC server implementation
│       │   └── main.py         # Entry point (temporal + grpc)
│       └── tests/              # Test suite (47 tests)
│
├── proto/
│   └── ai/v1/
│       └── agent.proto         # gRPC contract definition
│
├── gen/                        # Generated code
│   ├── go/ai/v1/              # Go protobuf stubs
│   └── python/ai/v1/          # Python protobuf stubs
│
├── scripts/
│   └── verify_system.sh        # E2E verification script
│
├── docker-compose.yml          # Local dev infrastructure
├── Makefile                    # Development commands
└── prd.md                     # This document
```

***

# **5. Development Phases**

## **Phase 1: Infrastructure (COMPLETED)**
- [x] Docker Compose: Temporal, PostgreSQL, Elasticsearch, Qdrant, Redpanda
- [x] Health check scripts
- [x] Network configuration

## **Phase 2: Protobuf Contract (COMPLETED)**
- [x] Define `agent.proto` with AnalyzeFeedback RPC
- [x] Configure `buf.yaml` and `buf.gen.yaml`
- [x] Generate Go and Python stubs

## **Phase 3: Python AI Worker (COMPLETED)**
- [x] gRPC server implementation
- [x] LangGraph triage agent
- [x] LangGraph spec writer agent
- [x] Qdrant vector service for deduplication
- [x] Test suite (27 tests)

## **Phase 4: Go Core Service (COMPLETED)**
- [x] Fiber HTTP server for webhooks
- [x] Temporal workflow definition with signal handling
- [x] gRPC client to Python AI service
- [x] Go activities (Discord, GitHub) - REAL IMPLEMENTATION
- [x] Test suite (9 tests)

## **Phase 5: Integrations & Polish (COMPLETED)**
- [x] Real Discord integration with buttons (bwmarrin/discordgo)
- [x] Real GitHub integration (google/go-github)
- [x] Professional README.md with architecture diagram
- [x] Makefile for unified operations
- [x] E2E verification script
- [x] LLM evaluation tests

## **Phase 6: Production (IN PROGRESS)**
- [ ] Dockerfiles for both services
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Deployment scripts (Fly.io/Railway)
- [ ] Monitoring and alerting

***

# **6. API Endpoints**

### **Go Core (Fiber)**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/webhooks/discord` | Discord webhook receiver |
| POST | `/webhooks/interaction` | Discord interaction handler |
| GET | `/test/kafka` | Kafka test endpoint |

### **Python AI Service (gRPC)**

| Method | Description |
|--------|-------------|
| `AnalyzeFeedback` | Analyze feedback and return structured issue spec |

### **Temporal Workflow**

**Workflow:** `FeedbackWorkflow`

1. Activity `AnalyzeFeedback` (Python via gRPC) - AI processing
2. Activity `SendDiscordApproval` (Go) - Discord buttons with embed
3. Signal `user-action` - Wait for admin decision (5 min timeout)
4. Activity `CreateGitHubIssue` (Go) - Create issue (if approved)

***

# **7. Configuration**

### **Environment Variables**

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token for sending approval messages | No |
| `GITHUB_TOKEN` | GitHub Personal Access Token for issue creation | No |
| `GITHUB_OWNER` | GitHub repository owner | No |
| `GITHUB_REPO` | GitHub repository name | No |
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | No |
| `OPENAI_BASE_URL` | OpenAI-compatible API base URL | No |
| `OPENAI_MODEL_NAME` | LLM model name | No |

### **Docker Services**

| Service | Port | Description |
|---------|------|-------------|
| Temporal | 7233 | gRPC API |
| Temporal UI | 8088 | Web UI (remapped from 8080) |
| PostgreSQL | 5432 | Database |
| Qdrant | 6333 | Vector DB REST |
| Redpanda | 9092 | Kafka API |
| Redpanda Admin | 9644 | Admin API |

***

# **8. Testing Strategy**

### **Unit Tests**
- **Go:** `go test ./...` (9 tests passing)
- **Python:** `uv run pytest tests/` (47 tests passing)

### **Integration Tests**
- Temporal worker connectivity
- gRPC client-server communication
- Qdrant duplicate detection
- Full workflow execution

### **E2E Tests**
- Webhook -> Workflow -> Discord -> Approval -> GitHub
- Verification script: `./scripts/verify_system.sh`

### **LLM Evaluation Tests**
- Mocked LLM responses for deterministic testing
- Classification accuracy tests
- Severity scoring tests
- Label generation tests

***

# **9. Quick Start**

```bash
# Clone and enter directory
cd iterate_swarm

# Start infrastructure
make up

# Run tests
make test

# Full verification
make verify

# Individual services
make ai-start      # Python AI service
make core-start    # Go core services
```

***

# **10. Verification Results**

```
==============================================
  VERIFICATION SUMMARY
==============================================

[PASS] Infrastructure: HEALTHY
[PASS] Go Code: VERIFIED
[PASS] Python Code: VERIFIED (47 tests)
[PASS] Protocol Buffers: VERIFIED
[PASS] gRPC Server: Running on port 50051

==============================================
  SYSTEM VERIFIED
==============================================
```

***

# **11. Portfolio Value Proposition**

IterateSwarm demonstrates:

1. **Polyglot Architecture** - Go and Python working together via gRPC
2. **Event-Driven Design** - Temporal workflows with durable execution
3. **AI Integration** - LangGraph agents with structured outputs
4. **Production Patterns** - Environment configuration, graceful degradation
5. **Testing Excellence** - 56 total unit tests, E2E verification
6. **DevOps Maturity** - Docker Compose, Makefile, verification scripts

This is a **showcase piece** for any senior full-stack or platform engineering role.

***

Last Updated: 2026-02-03
Version: 2.0 (Phase 5 Complete)
