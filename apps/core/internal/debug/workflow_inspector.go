package debug

import (
	"context"
	"time"

	"iterateswarm-core/internal/temporal"
)

// WorkflowSummary represents a workflow summary for listing.
type WorkflowSummary struct {
	WorkflowID    string        `json:"workflow_id"`
	RunID         string        `json:"run_id"`
	WorkflowType  string        `json:"workflow_type"`
	Status        string        `json:"status"`
	StartTime     time.Time     `json:"start_time"`
	CloseTime     time.Time     `json:"close_time,omitempty"`
	Duration      time.Duration `json:"duration"`
	TaskQueue     string        `json:"task_queue"`
	HistoryLength int64         `json:"history_length"`
}

// WorkflowDetails represents detailed workflow information.
type WorkflowDetails struct {
	WorkflowSummary
	Input      interface{}      `json:"input,omitempty"`
	Result     interface{}      `json:"result,omitempty"`
	Error      string           `json:"error,omitempty"`
	Activities []ActivityDetail  `json:"activities"`
}

// ActivityDetail represents detailed activity information.
type ActivityDetail struct {
	ActivityID    string        `json:"activity_id"`
	ActivityType  string        `json:"activity_type"`
	Status        string        `json:"status"`
	ScheduledTime time.Time     `json:"scheduled_time"`
	StartedTime   time.Time     `json:"started_time,omitempty"`
	CompletedTime time.Time     `json:"completed_time,omitempty"`
	FailedTime    time.Time     `json:"failed_time,omitempty"`
	Attempt       int32         `json:"attempt"`
	MaxAttempts   int32         `json:"max_attempts"`
	Duration      time.Duration `json:"duration,omitempty"`
}

// ListWorkflows returns a list of workflows with optional filtering.
// Note: Full listing requires workflowservice access. This returns an informational message.
func ListWorkflows(ctx context.Context, c *temporal.Client, statusFilter, workflowType string, limit int) ([]WorkflowSummary, error) {
	// The client SDK does not expose workflow listing.
	// For production, use Temporal CLI: tctl workflow list
	// or enable workflowservice access for admin operations.
	return []WorkflowSummary{}, nil
}

// GetWorkflowDetails returns detailed information about a specific workflow.
func GetWorkflowDetails(ctx context.Context, c *temporal.Client, workflowID string) (*WorkflowDetails, error) {
	// Get workflow run
	run := c.Client.GetWorkflow(ctx, workflowID, "")

	details := &WorkflowDetails{
		WorkflowSummary: WorkflowSummary{
			WorkflowID: run.GetID(),
			RunID:      run.GetRunID(),
		},
		Activities: make([]ActivityDetail, 0),
	}

	// Get workflow result (this also retrieves status info)
	var result interface{}
	err := run.Get(ctx, &result)
	if err != nil {
		details.Error = err.Error()
		details.Status = "failed"
	} else {
		details.Result = result
		details.Status = "completed"
	}

	return details, nil
}

// GetWorkflowEvents returns the event history for a workflow.
// Note: Full history access requires workflowservice. This is a placeholder.
func GetWorkflowEvents(ctx context.Context, c *temporal.Client, workflowID string) ([]WorkflowEvent, error) {
	// The client SDK does not expose direct history access.
	// For production, use: temporalctl workflow show <id>
	return []WorkflowEvent{}, nil
}

// WorkflowEvent represents a workflow event.
type WorkflowEvent struct {
	EventID      int64           `json:"event_id"`
	EventType    string          `json:"event_type"`
	Timestamp    time.Time       `json:"timestamp"`
	ActivityID   string          `json:"activity_id,omitempty"`
	ActivityType string          `json:"activity_type,omitempty"`
	Duration     time.Duration   `json:"duration,omitempty"`
}

// ExtractActivities extracts activity information from workflow events.
func ExtractActivities(events []WorkflowEvent) []ActivityDetail {
	activities := make(map[string]*ActivityDetail)

	for _, e := range events {
		switch e.EventType {
		case "ActivityTaskScheduled":
			activities[e.ActivityID] = &ActivityDetail{
				ActivityID:    e.ActivityID,
				ActivityType: e.ActivityType,
				ScheduledTime: e.Timestamp,
				Status:        "scheduled",
			}
		case "ActivityTaskStarted":
			if a, ok := activities[e.ActivityID]; ok {
				a.StartedTime = e.Timestamp
				a.Status = "running"
			}
		case "ActivityTaskCompleted":
			if a, ok := activities[e.ActivityID]; ok {
				a.CompletedTime = e.Timestamp
				a.Status = "completed"
				a.Duration = a.CompletedTime.Sub(a.ScheduledTime)
			}
		case "ActivityTaskFailed":
			if a, ok := activities[e.ActivityID]; ok {
				a.FailedTime = e.Timestamp
				a.Status = "failed"
				a.Duration = a.FailedTime.Sub(a.ScheduledTime)
			}
		}
	}

	// Convert map to slice
	result := make([]ActivityDetail, 0, len(activities))
	for _, a := range activities {
		result = append(result, *a)
	}

	return result
}
