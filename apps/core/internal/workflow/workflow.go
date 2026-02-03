package workflow

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// FeedbackInput is the input to the FeedbackWorkflow.
type FeedbackInput struct {
	Text      string
	Source    string
	UserID    string
	ChannelID string
	RepoOwner string
	RepoName  string
}

// FeedbackWorkflow is the main workflow for processing feedback.
func FeedbackWorkflow(ctx workflow.Context, input FeedbackInput) error {
	// Set activity options
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 2 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	// Channel for receiving signals (user approval)
	signalChan := workflow.GetSignalChannel(ctx, "user-action")

	var analyzeResult *AnalyzeFeedbackOutput

	// Step 1: Analyze feedback with AI
	err := workflow.ExecuteActivity(ctx, "AnalyzeFeedback", AnalyzeFeedbackInput{
		Text:      input.Text,
		Source:    input.Source,
		UserID:    input.UserID,
		ChannelID: input.ChannelID,
	}).Get(ctx, &analyzeResult)
	if err != nil {
		return err
	}

	// If duplicate, skip to end
	if analyzeResult.IsDuplicate {
		return nil
	}

	// Step 2: Send approval request to Discord
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

	// Step 3: Wait for user approval (signal with timeout)
	// Use workflow.AwaitWithTimeout for signal + timeout
	var signalValue interface{}
	signalReceived := false

	// Wait for signal with 5 minute timeout
	_, _ = workflow.AwaitWithTimeout(ctx, 5*time.Minute, func() bool {
		// Check if we have a signal
		received := signalChan.ReceiveAsync(&signalValue)
		if received {
			signalReceived = true
			return true
		}
		return false
	})

	// Check if we received a signal or timed out
	approved := false
	if signalReceived {
		if s, ok := signalValue.(string); ok {
			approved = s == "approve"
		}
	}

	// Step 4: Handle approval/rejection
	if !approved {
		return nil
	}

	// Step 5: Create GitHub issue
	err = workflow.ExecuteActivity(ctx, "CreateGitHubIssue", CreateGitHubIssueInput{
		Title:    analyzeResult.Title,
		Body:     analyzeResult.Description,
		Labels:   analyzeResult.Labels,
		RepoOwner: input.RepoOwner,
		RepoName:  input.RepoName,
	}).Get(ctx, nil)

	return err
}
