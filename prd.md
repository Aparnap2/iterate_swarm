This is the **Master Plan** for **IterateSwarm**. This document serves as your Product Requirements Document (PRD), Technical Specification, and Implementation Guide.

***

# **1. Product Requirements Document (PRD)**

**Product Name:** IterateSwarm
**One-Liner:** An event-driven autonomous agent swarm that turns unstructured user feedback into production-ready GitHub Issues.
**Target Audience:** Technical Founders (Seed/Series A) drowning in Discord/Slack feedback.

### **Core Features (MVP)**
1.  **Universal Ingestion:** Webhooks for Discord, Slack, and manual entry.
2.  **Semantic Deduplication:** Uses Vector Search to merge duplicate feedback items (e.g., "Login broken" and "Can't sign in" = 1 Issue).
3.  **Agentic Triaging:** Autonomous classification (Bug/Feature/Noise) and severity scoring.
4.  **Spec Generation:** A "Spec Writer" agent drafts a structured GitHub Issue (Title, Repro Steps, Components).
5.  **Human-in-the-Loop (HITL):** A dashboard for founders to approve/reject agent drafts before they hit GitHub.
6.  **Full Observability:** End-to-end tracing of the agent's "thought process."

***

# **2. System Architecture (The "Free Tier" Production Stack)**

### **The Tech Stack**
| Component | Tech Choice | Hosting (Free Tier Strategy) |
| :--- | :--- | :--- |
| **Frontend** | Next.js 14 (App Router) | Vercel (Hobby) |
| **Backend API** | FastAPI (Python) | Render (Free Web Service) |
| **Event Bus** | **Upstash Kafka** | Upstash (Free - 10k daily msgs) |
| **Orchestration** | **Inngest** | Vercel Integration (Free - 50k steps) |
| **Agent Framework** | LangGraph | Runs inside FastAPI on Render |
| **Vector DB** | Qdrant | Qdrant Cloud (1GB Free Cluster) |
| **Primary DB** | Supabase (Postgres) | Supabase (500MB Free) |
| **Observability** | Langfuse | Langfuse Cloud (Hobby Tier) |
| **Validation** | DeepEval | Local / GitHub Actions |

### **High-Level Data Flow**
```mermaid
graph LR
    Discord -->|Webhook| FastAPI
    FastAPI -->|Producer| UpstashKafka[Kafka: feedback.raw]
    UpstashKafka -->|Consumer| Inngest[Inngest Workflow]
    
    subgraph "Inngest Workflow Execution"
        Inngest --> Step1[Dedup Agent (Qdrant)]
        Step1 -->|If New| Step2[Triage Agent]
        Step2 --> Step3[Spec Agent]
        Step3 -->|Draft Saved| Supabase
    end
    
    Supabase -->|Realtime| NextJS[Dashboard]
    User -->|Approve| NextJS
    NextJS -->|API Call| GitHub[GitHub API]
```

***

# **3. Data Models (Schema)**

**SQL (Supabase)**
```sql
-- Table: feedback_items (Raw Ingestion)
CREATE TABLE feedback_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50), -- 'discord', 'slack'
    raw_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) -- 'pending', 'processed', 'ignored'
);

-- Table: issues (The Agent's Output)
CREATE TABLE issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id UUID REFERENCES feedback_items(id),
    title TEXT,
    description TEXT, -- Markdown body
    severity VARCHAR(20), -- 'low', 'medium', 'high', 'critical'
    labels TEXT[], -- ['bug', 'frontend']
    status VARCHAR(20), -- 'draft', 'approved', 'published'
    github_issue_url TEXT
);
```

**Pydantic (Python / API)**
```python
# The structure the Agent MUST output
class IssueSpec(BaseModel):
    title: str = Field(description="Concise, technical title")
    severity: Literal["low", "medium", "high", "critical"]
    components: List[str]
    reproduction_steps: List[str]
    technical_notes: Optional[str]
```

***

# **4. API Structure (FastAPI)**

*   `POST /webhooks/discord`: Receives JSON from Discord -> Pushes to Kafka.
*   `POST /inngest`: The entry point for the Inngest executor (triggers the agents).
*   `GET /api/dashboard/stats`: Returns metrics for the frontend.
*   `POST /api/issues/{id}/approve`: Triggered by HITL -> Calls GitHub API.

***

# **5. Code Snippets (The "Meat")**

### **A. Ingestion (FastAPI + Kafka)**
```python
from fastapi import FastAPI, Request
from upstash_kafka import Producer

app = FastAPI()
producer = Producer(url="...", username="...", password="...")

@app.post("/webhooks/discord")
async def receive_discord(request: Request):
    payload = await request.json()
    # 1. Validate (Pydantic)
    data = DiscordSchema(**payload)
    
    # 2. Push to Kafka (Non-blocking)
    producer.send("feedback.raw", value=data.model_dump_json())
    
    return {"status": "queued"} 
```

### **B. The Agent Workflow (Inngest + LangGraph)**
```python
import inngest

@inngest.create_function(
    fn_id="process-feedback",
    trigger=inngest.TriggerEvent(event="feedback.received"),
)
async def process_feedback_flow(ctx, step):
    feedback = ctx.event.data
    
    # Step 1: Deduplication (Deterministic)
    is_duplicate = await step.run("check-qdrant", 
        lambda: qdrant_client.search(collection="issues", vector=embed(feedback['text']))
    )
    
    if is_duplicate:
        return {"result": "merged"}

    # Step 2: Agent Swarm (The "Thinking")
    # We wrap LangGraph inside an Inngest step for retries/timeouts
    spec = await step.run("generate-spec", 
        lambda: triage_agent_swarm.invoke({"input": feedback['text']})
    )

    # Step 3: Save Draft
    await step.run("save-db", 
        lambda: supabase.table("issues").insert(spec)
    )
```

### **C. The Agent (LangGraph + Langfuse)**
```python
from langfuse.decorators import observe

@observe() # <--- This is the Magic Line for LLMOps
def triage_node(state):
    # Logic to classify bug vs feature
    response = llm.invoke(triage_prompt.format(state['input']))
    return {"classification": response}
```

***

# **6. Standard Operating Procedure (SOP) & Checklist**

**Phase 1: Infrastructure (Day 1)**
- [ ] Create Upstash Kafka Cluster (Free).
- [ ] Create Qdrant Cloud Cluster (Free).
- [ ] Create Supabase Project.
- [ ] Get OpenAI API Key.
- [ ] Get Langfuse Keys.

**Phase 2: Backend Core (Day 2)**
- [ ] `pip install fastapi uvicorn upstash-kafka inngest langchain-openai`.
- [ ] Implement `POST /webhooks/discord`.
- [ ] Implement `process_feedback_flow` in Inngest.
- [ ] Dockerize the FastAPI app.

**Phase 3: The Intelligence (Day 3)**
- [ ] Write the Prompts (System Prompts for Triage/Spec Agents).
- [ ] Implement `check_qdrant` logic.
- [ ] Connect Langfuse.

**Phase 4: Frontend & Polish (Day 4)**
- [ ] `npx create-next-app@latest`.
- [ ] Install Shadcn/UI (Table, Dialog, Button).
- [ ] Fetch data from Supabase (`supabase-js`).
- [ ] Deploy to Vercel & Render.

***

# **7. Deliverables & Testing Strategy**

### **A. Unit Tests (Pytest)**
*   Test that the Pydantic models reject invalid JSON.
*   Test that the deduplication logic returns `True` for 100% identical strings.

### **B. E2E Tests (Manual/Scripted)**
1.  Send a message: "The login button is broken on mobile" to your Discord Mock webhook.
2.  Check Upstash: Did a message appear in `feedback.raw`?
3.  Check Inngest Dashboard: Did the function trigger?
4.  Check Langfuse: Do you see the trace?
5.  Check Supabase: Is there a new row in `issues` with status `draft`?

### **C. LLM Evaluation (DeepEval)**
Create a file `test_agents.py`:
```python
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric

def test_triage_accuracy():
    # Input
    input_text = "The app crashes when I click upload."
    
    # Run Agent
    output = triage_agent.invoke(input_text)
    
    # Metric: Did it catch the severity?
    assert output['severity'] == 'high'
    assert output['type'] == 'bug'
```
*Run this in GitHub Actions on every push.*

***

### **How to Handover**
When you submit this project or show it in an interview, provide:
1.  **The Live Demo Link** (Vercel URL).
2.  **The Loom Video** (Walkthrough of the Inngest flow + Langfuse Trace).
3.  **The GitHub Repo** (With a clean README showing the Architecture Diagram).

This is a Senior Engineer's portfolio piece. Go build it.
