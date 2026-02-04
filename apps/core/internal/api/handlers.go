package api

import (
	"encoding/json"
	"runtime"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"

	"iterateswarm-core/internal/logging"
	"iterateswarm-core/internal/redpanda"
	"iterateswarm-core/internal/temporal"
)

// FeedbackRequest represents a webhook request for feedback.
type FeedbackRequest struct {
	Text     string `json:"text"`
	Source   string `json:"source"`
	UserID   string `json:"user_id"`
	Username string `json:"username,omitempty"`
}

// FeedbackResponse is the response after ingesting feedback.
type FeedbackResponse struct {
	FeedbackID string `json:"feedback_id"`
	Status    string `json:"status"`
	Message   string `json:"message"`
}

// InteractionRequest represents a Discord interaction (button click).
type InteractionRequest struct {
	Type      int                    `json:"type"`
	Data      InteractionData        `json:"data"`
	ChannelID string                 `json:"channel_id"`
	User      InteractionUser        `json:"user"`
	Message   map[string]interface{} `json:"message,omitempty"`
}

// InteractionData contains the interaction data.
type InteractionData struct {
	CustomID string `json:"custom_id"`
}

// InteractionUser contains the user who triggered the interaction.
type InteractionUser struct {
	ID       string `json:"id"`
	Username string `json:"username"`
}

// Handler handles API requests.
type Handler struct {
	redpandaClient  *redpanda.Client
	temporalClient  *temporal.Client
	logger          *logging.Logger
}

// NewHandler creates a new Handler.
func NewHandler(redpandaClient *redpanda.Client, temporalClient *temporal.Client) *Handler {
	return &Handler{
		redpandaClient: redpandaClient,
		temporalClient: temporalClient,
		logger:         logging.NewLogger("api"),
	}
}

// HandleDiscordWebhook processes Discord webhook events.
func (h *Handler) HandleDiscordWebhook(c *fiber.Ctx) error {
	startTime := time.Now()
	var req FeedbackRequest

	if err := c.BodyParser(&req); err != nil {
		h.logger.Error("failed to parse request body", err, "error", err.Error())
		return c.Status(fiber.StatusBadRequest).JSON(map[string]string{
			"error": "Invalid request body",
		})
	}

	if req.Text == "" {
		return c.Status(fiber.StatusBadRequest).JSON(map[string]string{
			"error": "Missing 'text' field",
		})
	}

	// Generate feedback ID
	feedbackID := uuid.New().String()

	// Publish to Redpanda
	event := map[string]interface{}{
		"feedback_id": feedbackID,
		"text":        req.Text,
		"source":      "discord",
		"user_id":     req.UserID,
		"username":    req.Username,
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
	}

	data, err := json.Marshal(event)
	if err != nil {
		h.logger.Error("failed to marshal event", err, "feedback_id", feedbackID)
		return c.Status(fiber.StatusInternalServerError).JSON(map[string]string{
			"error": "Failed to process event",
		})
	}

	err = h.redpandaClient.Publish("feedback-events", data)
	if err != nil {
		h.logger.Error("failed to publish to redpanda", err, "feedback_id", feedbackID, "topic", "feedback-events")
		return c.Status(fiber.StatusInternalServerError).JSON(map[string]string{
			"error": "Failed to queue event",
		})
	}

	duration := time.Since(startTime)
	h.logger.Info("feedback ingested",
		"feedback_id", feedbackID,
		"source", "discord",
		"user_id", req.UserID,
		"duration_ms", duration.Milliseconds(),
	)

	return c.Status(fiber.StatusAccepted).JSON(FeedbackResponse{
		FeedbackID: feedbackID,
		Status:     "accepted",
		Message:    "Feedback is being processed",
	})
}

// HandleInteraction processes Discord interactions (button clicks).
func (h *Handler) HandleInteraction(c *fiber.Ctx) error {
	var req InteractionRequest
	if err := c.BodyParser(&req); err != nil {
		h.logger.Error("failed to parse interaction", err, "error", err.Error())
		return c.Status(fiber.StatusBadRequest).JSON(map[string]string{
			"error": "Invalid request body",
		})
	}

	// Handle Discord's ping interaction
	if req.Type == 1 {
		return c.JSON(map[string]interface{}{
			"type": 1,
		})
	}

	h.logger.Info("interaction received",
		"custom_id", req.Data.CustomID,
		"user_id", req.User.ID,
		"username", req.User.Username,
		"channel_id", req.ChannelID,
	)

	// Signal the workflow (parse custom_id for action and workflowID)
	parts := strings.Split(req.Data.CustomID, ":")
	action := parts[0]
	workflowID := ""
	if len(parts) > 1 {
		workflowID = parts[1]
	}

	err := h.temporalClient.SignalWorkflow(c.Context(), workflowID, "user-action", action)
	if err != nil {
		h.logger.Error("failed to signal workflow", err, "workflow_id", workflowID, "action", action)
		return c.Status(fiber.StatusInternalServerError).JSON(map[string]string{
			"error": "Failed to process action",
		})
	}

	return c.JSON(map[string]interface{}{
		"type": 4,
		"data": map[string]string{
			"content": "Action received!",
		},
	})
}

// HandleHealth returns a simple health status.
func (h *Handler) HandleHealth(c *fiber.Ctx) error {
	return c.JSON(map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// HandleDetailedHealth returns comprehensive health status with dependency checks.
func (h *Handler) HandleDetailedHealth(c *fiber.Ctx) error {
	ctx := c.Context()
	checks := make(map[string]interface{})
	allHealthy := true

	// Check Temporal
	temporalStart := time.Now()
	temporalErr := h.temporalClient.Health(ctx)
	temporalDuration := time.Since(temporalStart)
	if temporalErr != nil {
		checks["temporal"] = map[string]interface{}{
			"status":  "unhealthy",
			"error":   temporalErr.Error(),
			"latency_ms": temporalDuration.Milliseconds(),
		}
		allHealthy = false
	} else {
		checks["temporal"] = map[string]interface{}{
			"status":      "healthy",
			"latency_ms": temporalDuration.Milliseconds(),
		}
	}

	// Check Redpanda
	redpandaStart := time.Now()
	redpandaErr := h.redpandaClient.Health(ctx)
	redpandaDuration := time.Since(redpandaStart)
	if redpandaErr != nil {
		checks["redpanda"] = map[string]interface{}{
			"status":  "unhealthy",
			"error":   redpandaErr.Error(),
			"latency_ms": redpandaDuration.Milliseconds(),
		}
		allHealthy = false
	} else {
		checks["redpanda"] = map[string]interface{}{
			"status":      "healthy",
			"latency_ms": redpandaDuration.Milliseconds(),
		}
	}

	// Runtime info
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Build response
	response := map[string]interface{}{
		"status":      "healthy",
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
		"service":     "iterateswarm-core",
		"version":     "1.0.0",
		"checks":      checks,
		"runtime": map[string]interface{}{
			"goroutines": runtime.NumGoroutine(),
			"cpu_cores":  runtime.NumCPU(),
			"memory_alloc_mb":  float64(m.Alloc) / 1024 / 1024,
			"total_alloc_mb":   float64(m.TotalAlloc) / 1024 / 1024,
			"heap_alloc_mb":    float64(m.HeapAlloc) / 1024 / 1024,
		},
	}

	// Determine overall status
	if !allHealthy {
		response["status"] = "degraded"
	}

	// Return appropriate status code
	statusCode := fiber.StatusOK
	if !allHealthy {
		statusCode = fiber.StatusServiceUnavailable
	}

	return c.Status(statusCode).JSON(response)
}

// HandleKafkaTest sends a test message to Kafka (for development).
func (h *Handler) HandleKafkaTest(c *fiber.Ctx) error {
	event := map[string]interface{}{
		"feedback_id": uuid.New().String(),
		"text":        "Test feedback from API",
		"source":      "test",
		"user_id":     "test-user",
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
	}

	data, _ := json.Marshal(event)
	if err := h.redpandaClient.Publish("feedback-events", data); err != nil {
		h.logger.Warn("failed to publish test message", "error", err.Error())
	}

	return c.JSON(map[string]interface{}{
		"status":  "sent",
		"message": "Test message published to feedback-events",
	})
}
