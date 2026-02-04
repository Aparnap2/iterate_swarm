package logging

import (
	"context"
	"log/slog"
	"os"
	"time"
)

// Logger provides structured logging for IterateSwarm.
type Logger struct {
	*slog.Logger
}

// NewLogger creates a new structured logger.
func NewLogger(service string) *Logger {
	// Create JSON handler for production, text handler for development
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
		AddSource: false,
	})

	logger := slog.New(handler)
	logger = logger.With("service", service, "environment", "development")

	return &Logger{logger}
}

// With creates a new logger with additional context.
func (l *Logger) With(args ...any) *Logger {
	return &Logger{l.Logger.With(args...)}
}

// Info logs an info message with structured context.
func (l *Logger) Info(msg string, args ...any) {
	l.Logger.Info(msg, args...)
}

// Error logs an error message with structured context.
func (l *Logger) Error(msg string, err error, args ...any) {
	allArgs := append(args, "error", err.Error())
	l.Logger.Error(msg, allArgs...)
}

// Debug logs a debug message with structured context.
func (l *Logger) Debug(msg string, args ...any) {
	l.Logger.Debug(msg, args...)
}

// Warn logs a warning message with structured context.
func (l *Logger) Warn(msg string, args ...any) {
	l.Logger.Warn(msg, args...)
}

// LogActivity logs activity execution metrics.
func (l *Logger) LogActivity(ctx context.Context, activity string, duration time.Duration, success bool, args ...any) {
	l.Logger.Info("activity completed",
		append([]any{
			"activity", activity,
			"duration_ms", duration.Milliseconds(),
			"success", success,
		}, args...)...,
	)
}

// LogWorkflow logs workflow execution metrics.
func (l *Logger) LogWorkflow(ctx context.Context, workflowID string, status string, args ...any) {
	l.Logger.Info("workflow event",
		append([]any{
			"workflow_id", workflowID,
			"status", status,
		}, args...)...,
	)
}

// LogAPICall logs external API calls.
func (l *Logger) LogAPICall(ctx context.Context, provider string, endpoint string, duration time.Duration, statusCode int, success bool) {
	l.Logger.Info("api call",
		"provider", provider,
		"endpoint", endpoint,
		"duration_ms", duration.Milliseconds(),
		"status_code", statusCode,
		"success", success,
	)
}
