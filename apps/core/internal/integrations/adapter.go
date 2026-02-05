package integrations

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// Integration represents a third-party service integration
type Integration interface {
	Name() string
	Type() string
	Send(ctx context.Context, payload interface{}) error
	Validate(payload interface{}) error
}

// WebhookConfig holds webhook configuration
type WebhookConfig struct {
	URL       string
	Secret    string
	Headers   map[string]string
	Timeout   time.Duration
	Retries   int
}

// IntegrationResponse represents the response from an integration
type IntegrationResponse struct {
	Success   bool
	Status    int
	Message   string
	Data      map[string]interface{}
	Timestamp time.Time
}

// Adapter provides a common interface for all integrations
type Adapter struct {
	client  *http.Client
	webhooks map[string]WebhookConfig
}

// NewAdapter creates a new integration adapter
func NewAdapter(timeout time.Duration) *Adapter {
	return &Adapter{
		client: &http.Client{
			Timeout: timeout,
		},
		webhooks: make(map[string]WebhookConfig),
	}
}

// RegisterWebhook registers a webhook configuration
func (a *Adapter) RegisterWebhook(name string, config WebhookConfig) {
	a.webhooks[name] = config
}

// SendWebhook sends data to a registered webhook
func (a *Adapter) SendWebhook(ctx context.Context, name string, payload interface{}) (*IntegrationResponse, error) {
	config, exists := a.webhooks[name]
	if !exists {
		return nil, fmt.Errorf("webhook %s not registered", name)
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, config.URL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	for k, v := range config.Headers {
		req.Header.Set(k, v)
	}
	req.Header.Set("X-Webhook-Source", "iterateswarm")

	resp, err := a.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		result = make(map[string]interface{})
	}

	return &IntegrationResponse{
		Success:   resp.StatusCode >= 200 && resp.StatusCode < 300,
		Status:    resp.StatusCode,
		Message:   http.StatusText(resp.StatusCode),
		Data:      result,
		Timestamp: time.Now(),
	}, nil
}

// DiscordAdapter handles Discord integrations
type DiscordAdapter struct {
	*Adapter
	webhookURL string
}

// NewDiscordAdapter creates a new Discord adapter
func NewDiscordAdapter(webhookURL string, timeout time.Duration) *DiscordAdapter {
	adapter := NewAdapter(timeout)
	adapter.RegisterWebhook("discord", WebhookConfig{
		URL:     webhookURL,
		Timeout: timeout,
	})
	return &DiscordAdapter{
		Adapter:    adapter,
		webhookURL: webhookURL,
	}
}

// Name returns the integration name
func (d *DiscordAdapter) Name() string {
	return "discord"
}

// Type returns the integration type
func (d *DiscordAdapter) Type() string {
	return "webhook"
}

// DiscordMessage represents a Discord webhook message
type DiscordMessage struct {
	Content         string                 `json:"content,omitempty"`
	Username        string                 `json:"username,omitempty"`
	AvatarURL       string                 `json:"avatar_url,omitempty"`
	Embeds          []DiscordEmbed         `json:"embeds,omitempty"`
	Components      []DiscordComponent     `json:"components,omitempty"`
	AllowedMentions DiscordAllowedMentions `json:"allowed_mentions,omitempty"`
}

type DiscordEmbed struct {
	Title       string            `json:"title,omitempty"`
	Description string            `json:"description,omitempty"`
	URL         string            `json:"url,omitempty"`
	Color       int               `json:"color,omitempty"`
	Fields      []DiscordField    `json:"fields,omitempty"`
	Footer      DiscordFooter     `json:"footer,omitempty"`
	Timestamp   string            `json:"timestamp,omitempty"`
}

type DiscordField struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Inline bool   `json:"inline,omitempty"`
}

type DiscordFooter struct {
	Text    string `json:"text"`
	IconURL string `json:"icon_url,omitempty"`
}

type DiscordAllowedMentions struct {
	Parse []string `json:"parse,omitempty"`
}

type DiscordComponent struct {
	Type       int                    `json:"type"`
	Components []DiscordButtonComponent `json:"components,omitempty"`
}

type DiscordButtonComponent struct {
	Type    int    `json:"type"`
	Style   int    `json:"style"`
	Label   string `json:"label,omitempty"`
	URL     string `json:"url,omitempty"`
	CustomID string `json:"custom_id,omitempty"`
}

// Send sends a Discord message
func (d *DiscordAdapter) Send(ctx context.Context, payload interface{}) error {
	msg, ok := payload.(DiscordMessage)
	if !ok {
		return fmt.Errorf("invalid payload type for Discord")
	}

	body, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, d.webhookURL, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := d.client.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("discord returned status %d", resp.StatusCode)
	}

	return nil
}

// Validate validates a Discord message
func (d *DiscordAdapter) Validate(payload interface{}) error {
	msg, ok := payload.(DiscordMessage)
	if !ok {
		return fmt.Errorf("payload must be DiscordMessage")
	}
	if msg.Content == "" && len(msg.Embeds) == 0 {
		return fmt.Errorf("message must have content or embeds")
	}
	return nil
}

// SlackAdapter handles Slack integrations
type SlackAdapter struct {
	*Adapter
	webhookURL string
}

// NewSlackAdapter creates a new Slack adapter
func NewSlackAdapter(webhookURL string, timeout time.Duration) *SlackAdapter {
	adapter := NewAdapter(timeout)
	adapter.RegisterWebhook("slack", WebhookConfig{
		URL:     webhookURL,
		Timeout: timeout,
	})
	return &SlackAdapter{
		Adapter:    adapter,
		webhookURL: webhookURL,
	}
}

// Name returns the integration name
func (s *SlackAdapter) Name() string {
	return "slack"
}

// Type returns the integration type
func (s *SlackAdapter) Type() string {
	return "webhook"
}

// SlackMessage represents a Slack webhook message
type SlackMessage struct {
	Channel     string              `json:"channel,omitempty"`
	Text        string              `json:"text,omitempty"`
	Blocks      []SlackBlock        `json:"blocks,omitempty"`
	Attachments []SlackAttachment   `json:"attachments,omitempty"`
	Markdown    bool                `json:"mrkdwn,omitempty"`
}

type SlackBlock struct {
	Type     string              `json:"type"`
	Text     *SlackText          `json:"text,omitempty"`
	Elements []map[string]interface{} `json:"elements,omitempty"`
}

type SlackText struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type SlackAttachment struct {
	Color      string            `json:"color,omitempty"`
	Title      string            `json:"title,omitempty"`
	Text       string            `json:"text,omitempty"`
	Fields     []SlackField      `json:"fields,omitempty"`
	Footer     string            `json:"footer,omitempty"`
	TS         int64             `json:"ts,omitempty"`
}

// Send sends a Slack message
func (s *SlackAdapter) Send(ctx context.Context, payload interface{}) error {
	msg, ok := payload.(SlackMessage)
	if !ok {
		return fmt.Errorf("invalid payload type for Slack")
	}

	body, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.webhookURL, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("slack returned status %d", resp.StatusCode)
	}

	return nil
}

// Validate validates a Slack message
func (s *SlackAdapter) Validate(payload interface{}) error {
	msg, ok := payload.(SlackMessage)
	if !ok {
		return fmt.Errorf("payload must be SlackMessage")
	}
	if msg.Text == "" && len(msg.Blocks) == 0 {
		return fmt.Errorf("message must have text or blocks")
	}
	return nil
}
