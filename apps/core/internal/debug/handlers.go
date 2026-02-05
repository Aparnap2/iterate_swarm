package debug

import (
	"encoding/json"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"

	"iterateswarm-core/internal/logging"
	"iterateswarm-core/internal/redpanda"
	"iterateswarm-core/internal/temporal"
)

// APIResponse represents a standardized API response for LiteDebug.
type APIResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
	Meta    struct {
		Timestamp string `json:"timestamp"`
		TraceID   string `json:"trace_id,omitempty"`
	} `json:"meta"`
}

// Handler handles debug API requests.
type Handler struct {
	redpandaClient  *redpanda.Client
	temporalClient *temporal.Client
	logger         *logging.Logger
	jaegerURL      string
}

// NewHandler creates a new debug Handler.
func NewHandler(redpandaClient *redpanda.Client, temporalClient *temporal.Client, jaegerURL string) *Handler {
	return &Handler{
		redpandaClient:  redpandaClient,
		temporalClient: temporalClient,
		logger:         logging.NewLogger("debug"),
		jaegerURL:      jaegerURL,
	}
}

// newResponse creates a new APIResponse with standard metadata.
func (h *Handler) newResponse(success bool, data interface{}, err error) APIResponse {
	resp := APIResponse{
		Success: success,
		Meta: struct {
			Timestamp string `json:"timestamp"`
			TraceID   string `json:"trace_id,omitempty"`
		}{
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		},
	}

	if success {
		resp.Data = data
	} else {
		resp.Error = err.Error()
	}

	return resp
}

// RegisterRoutes registers all debug routes.
func (h *Handler) RegisterRoutes(app *fiber.App) {
	debug := app.Group("/api/debug")

	// Kafka Topic Browser
	debug.Get("/kafka/topics", h.ListKafkaTopics)
	debug.Get("/kafka/topics/:name/messages", h.GetKafkaTopicMessages)
	debug.Post("/kafka/test-message", h.PublishTestMessage)

	// Temporal Workflow Inspector
	debug.Get("/workflows", h.ListWorkflows)
	debug.Get("/workflows/:id", h.GetWorkflowDetails)

	// Trace Viewer
	debug.Get("/traces/:id", h.GetTraceDetails)

	// Event Trace
	debug.Get("/events", h.ListRecentEvents)
}

// ListKafkaTopics returns a list of all Kafka topics with metadata.
func (h *Handler) ListKafkaTopics(c *fiber.Ctx) error {
	ctx := c.Context()

	topics, err := ListKafkaTopics(ctx, h.redpandaClient)
	if err != nil {
		h.logger.Error("failed to list Kafka topics", err)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, topics, nil))
}

// GetKafkaTopicMessages returns messages from a specific Kafka topic with pagination.
func (h *Handler) GetKafkaTopicMessages(c *fiber.Ctx) error {
	ctx := c.Context()
	topicName := c.Params("name")

	offset := c.QueryInt("offset", 0)
	limit := c.QueryInt("limit", 100)

	messages, err := GetKafkaTopicMessages(ctx, h.redpandaClient, topicName, offset, limit)
	if err != nil {
		h.logger.Error("failed to get Kafka topic messages", err, "topic", topicName)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, messages, nil))
}

// PublishTestMessage publishes a test message to a Kafka topic.
func (h *Handler) PublishTestMessage(c *fiber.Ctx) error {
	var req struct {
		Topic   string `json:"topic"`
		Message string `json:"message"`
	}

	if err := c.BodyParser(&req); err != nil {
		req.Topic = "feedback-events"
		req.Message = "Test message from LiteDebug"
	}

	ctx := c.Context()

	err := PublishTestMessage(ctx, h.redpandaClient, req.Topic, req.Message)
	if err != nil {
		h.logger.Error("failed to publish test message", err, "topic", req.Topic)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, map[string]interface{}{
		"topic":     req.Topic,
		"message":   req.Message,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}, nil))
}

// ListWorkflows returns a list of workflows with filtering.
func (h *Handler) ListWorkflows(c *fiber.Ctx) error {
	ctx := c.Context()

	status := c.Query("status")
	workflowType := c.Query("type")
	limit := c.QueryInt("limit", 50)

	workflows, err := ListWorkflows(ctx, h.temporalClient, status, workflowType, limit)
	if err != nil {
		h.logger.Error("failed to list workflows", err)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, workflows, nil))
}

// GetWorkflowDetails returns details of a specific workflow.
func (h *Handler) GetWorkflowDetails(c *fiber.Ctx) error {
	ctx := c.Context()
	workflowID := c.Params("id")

	details, err := GetWorkflowDetails(ctx, h.temporalClient, workflowID)
	if err != nil {
		h.logger.Error("failed to get workflow details", err, "workflow_id", workflowID)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, details, nil))
}

// GetTraceDetails returns trace details from Jaeger.
func (h *Handler) GetTraceDetails(c *fiber.Ctx) error {
	ctx := c.Context()
	traceID := c.Params("id")

	details, err := GetTraceDetails(ctx, h.jaegerURL, traceID)
	if err != nil {
		h.logger.Error("failed to get trace details", err, "trace_id", traceID)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, details, nil))
}

// ListRecentEvents returns recent events from Redpanda.
func (h *Handler) ListRecentEvents(c *fiber.Ctx) error {
	ctx := c.Context()
	limit := c.QueryInt("limit", 100)

	events, err := ListRecentEvents(ctx, h.redpandaClient, limit)
	if err != nil {
		h.logger.Error("failed to list recent events", err)
		return c.Status(fiber.StatusInternalServerError).JSON(h.newResponse(false, nil, err))
	}

	return c.JSON(h.newResponse(true, events, nil))
}

// generateTraceID generates a unique trace ID for request correlation.
func generateTraceID() string {
	return uuid.New().String()
}

// MarshalResponse marshals the API response to JSON.
func (r APIResponse) MarshalJSON() ([]byte, error) {
	type Alias APIResponse
	return json.Marshal(Alias(r))
}
