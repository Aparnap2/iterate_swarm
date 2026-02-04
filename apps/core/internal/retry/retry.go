package retry

import (
	"context"
	"fmt"
	"math"
	"math/rand"
	"time"
)

// RetryConfig configures retry behavior.
type RetryConfig struct {
	MaxRetries        int           // Maximum number of retries
	InitialDelay      time.Duration // Initial delay between retries
	MaxDelay          time.Duration // Maximum delay between retries
	BackoffMultiplier float64       // Multiplier for exponential backoff
	Jitter            time.Duration // Random jitter added to delay
	RetryOnError      []error       // Specific errors to retry on
	RetryOnStatusCodes []int        // HTTP status codes to retry on
}

// DefaultRetryConfig returns a sensible default configuration.
func DefaultRetryConfig() *RetryConfig {
	return &RetryConfig{
		MaxRetries:        3,
		InitialDelay:      1 * time.Second,
		MaxDelay:          30 * time.Second,
		BackoffMultiplier: 2.0,
		Jitter:            100 * time.Millisecond,
	}
}

// ShouldRetry determines if an error should trigger a retry.
func (c *RetryConfig) ShouldRetry(err error, statusCode int) bool {
	// Retry on context cancellation
	if err == context.Canceled || err == context.DeadlineExceeded {
		return true
	}

	// Retry on nil error (for status code based retries)
	if err == nil {
		// Retry on 5xx errors and specific 4xx codes
		if statusCode >= 500 {
			return true
		}
		switch statusCode {
		case 429: // Too Many Requests
			return true
		case 401, 403: // Auth errors - usually shouldn't retry
			return false
		default:
			return false
		}
	}

	// Check specific error types
	for _, retryErr := range c.RetryOnError {
		if err == retryErr {
			return true
		}
	}

	// Default: retry on most errors
	return true
}

// RetryFunc is a function that can be retried.
type RetryFunc func(attempt int) (interface{}, error)

// Retry executes a function with retry logic.
func Retry(ctx context.Context, config *RetryConfig, fn RetryFunc) (interface{}, error) {
	var lastErr error
	var result interface{}

	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		if attempt > 0 {
			// Calculate delay with exponential backoff and jitter
			delay := time.Duration(float64(config.InitialDelay) *
				math.Pow(config.BackoffMultiplier, float64(attempt-1)))
			delay = min(delay, config.MaxDelay)
			// Add jitter
			jitter := time.Duration(rand.Int63n(int64(config.Jitter) + 1))
			delay = delay + jitter

			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(delay):
			}
		}

		// Execute the function
		result, lastErr = fn(attempt)

		if lastErr == nil {
			return result, nil
		}

		// Check if we should retry
		statusCode := extractStatusCode(lastErr)
		if !config.ShouldRetry(lastErr, statusCode) {
			return result, lastErr
		}

		// Log retry attempt (if we have a logger)
		if attempt < config.MaxRetries {
			// Continue with next attempt
		}
	}

	return result, fmt.Errorf("retry failed after %d attempts: %w", config.MaxRetries+1, lastErr)
}

// extractStatusCode attempts to extract HTTP status code from error.
func extractStatusCode(err error) int {
	if err == nil {
		return 0
	}
	// Try to extract from error message
	// This is a simple heuristic - in production you'd want better error typing
	return 0
}

// SimpleRetry is a convenience function for simple retry scenarios.
func SimpleRetry(fn func() error) error {
	config := DefaultRetryConfig()

	var lastErr error
	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		if attempt > 0 {
			delay := time.Duration(float64(config.InitialDelay) *
				math.Pow(config.BackoffMultiplier, float64(attempt-1)))
			delay = min(delay, config.MaxDelay)
			jitter := time.Duration(rand.Int63n(int64(config.Jitter) + 1))
			time.Sleep(delay + jitter)
		}

		lastErr = fn()
		if lastErr == nil {
			return nil
		}
	}

	return fmt.Errorf("retry failed after %d attempts: %w", config.MaxRetries+1, lastErr)
}
