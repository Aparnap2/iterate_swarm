package api

import (
	"encoding/json"
	"log"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"

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
	Status     string `json:"status"`
	Message    string `json:"message"`
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
	redpandaClient *redpanda.Client
	temporalClient *temporal.Client
}

// NewHandler creates a new Handler.
func NewHandler(redpandaClient *redpanda.Client, temporalClient *temporal.Client) *Handler {
	return &Handler{
		redpandaClient: redpandaClient,
		temporalClient: temporalClient,
	}
}

// HandleDiscordWebhook processes Discord webhook events.
func (h *Handler) HandleDiscordWebhook(c *fiber.Ctx) error {
	var req FeedbackRequest
	if err := c.BodyParser(&req); err != nil {
		log.Printf("Failed to parse request: %v", err)
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
		log.Printf("Failed to marshal event: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(map[string]string{
			"error": "Failed to process event",
		})
	}

	err = h.redpandaClient.Publish("feedback-events", data)
	if err != nil {
		log.Printf("Failed to publish to Redpanda: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(map[string]string{
			"error": "Failed to queue event",
		})
	}

	log.Printf("Feedback ingested: id=%s, source=%s", feedbackID, req.Source)

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
		log.Printf("Failed to parse interaction: %v", err)
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

	log.Printf(
		"Interaction received: custom_id=%s, user=%s, channel=%s",
		req.Data.CustomID,
		req.User.Username,
		req.ChannelID,
	)

	// Signal the workflow (simplified - in production parse custom_id)
	action := "approve"
	workflowID := ""

	err := h.temporalClient.SignalWorkflow(workflowID, "user-action", action)
	if err != nil {
		log.Printf("Failed to signal workflow: %v", err)
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

// HandleHealth returns the health status.
func (h *Handler) HandleHealth(c *fiber.Ctx) error {
	return c.JSON(map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
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
		log.Printf("Warning: Failed to publish test message: %v", err)
	}

	return c.JSON(map[string]interface{}{
		"status":  "sent",
		"message": "Test message published to feedback-events",
	})
}
