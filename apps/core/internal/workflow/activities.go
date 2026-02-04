package workflow

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"iterateswarm-core/internal/grpc"
	"iterateswarm-core/internal/logging"
	"iterateswarm-core/internal/retry"

	"github.com/bwmarrin/discordgo"
	"github.com/google/go-github/v50/github"
	"golang.org/x/oauth2"
)

// Activities contains the workflow activities.
type Activities struct {
	aiClient *grpc.Client
	logger   *logging.Logger
}

// NewActivities creates a new Activities instance.
func NewActivities(aiClient *grpc.Client) *Activities {
	return &Activities{
		aiClient: aiClient,
		logger:   logging.NewLogger("workflow"),
	}
}

// AnalyzeFeedbackInput is the input for the AnalyzeFeedback activity.
type AnalyzeFeedbackInput struct {
	Text      string
	Source    string
	UserID    string
	ChannelID string
}

// AnalyzeFeedbackOutput is the output from the AnalyzeFeedback activity.
type AnalyzeFeedbackOutput struct {
	IsDuplicate   bool
	Reasoning    string
	Title        string
	Severity     string
	IssueType    string
	Description  string
	Labels       []string
	Confidence   float64
}

// AnalyzeFeedback calls the Python AI service to analyze feedback.
func (a *Activities) AnalyzeFeedback(ctx context.Context, input AnalyzeFeedbackInput) (*AnalyzeFeedbackOutput, error) {
	startTime := time.Now()
	a.logger.Info("analyzing feedback",
		"source", input.Source,
		"user_id", input.UserID,
		"text_length", len(input.Text),
	)

	resp, err := a.aiClient.AnalyzeFeedback(ctx, input.Text, input.Source, input.UserID)
	if err != nil {
		a.logger.Error("analyze feedback failed", err,
			"source", input.Source,
			"user_id", input.UserID,
		)
		return nil, err
	}

	output := &AnalyzeFeedbackOutput{
		IsDuplicate:  resp.IsDuplicate,
		Reasoning:    resp.Reasoning,
		Title:        resp.Spec.Title,
		Severity:     grpc.GetSeverity(resp),
		IssueType:    grpc.GetIssueType(resp),
		Description:  resp.Spec.Description,
		Labels:       resp.Spec.Labels,
		Confidence:   0.85,
	}

	duration := time.Since(startTime)
	a.logger.LogActivity(ctx, "AnalyzeFeedback", duration, true,
		"is_duplicate", output.IsDuplicate,
		"issue_type", output.IssueType,
		"severity", output.Severity,
	)

	return output, nil
}

// SendDiscordApprovalInput is the input for the SendDiscordApproval activity.
type SendDiscordApprovalInput struct {
	ChannelID     string
	IssueTitle    string
	IssueBody     string
	IssueLabels   []string
	Severity      string
	IssueType     string
	WorkflowRunID string
}

// severityColor maps severity levels to Discord embed colors.
var severityColor = map[string]int{
	"critical":    0xff0000,
	"high":        0xff6600,
	"medium":      0xffff00,
	"low":         0x00ff00,
	"unspecified": 0x808080,
}

// issueTypeEmoji maps issue types to emojis.
var issueTypeEmoji = map[string]string{
	"bug":        "🐛",
	"feature":    "✨",
	"question":   "❓",
	"unspecified": "📝",
}

// SendDiscordApproval sends an approval request to Discord with Approve/Reject buttons.
func (a *Activities) SendDiscordApproval(ctx context.Context, input SendDiscordApprovalInput) error {
	startTime := time.Now()
	a.logger.Info("sending discord approval request",
		"channel_id", input.ChannelID,
		"issue_title", input.IssueTitle,
		"workflow_run_id", input.WorkflowRunID,
	)

	// Get Discord bot token from environment
	discordToken := os.Getenv("DISCORD_BOT_TOKEN")
	if discordToken == "" {
		a.logger.Warn("discord token not configured, skipping notification")
		return nil
	}

	// Create Discord session with retry
	var dg *discordgo.Session
	err := retry.SimpleRetry(func() error {
		var createErr error
		dg, createErr = discordgo.New("Bot " + discordToken)
		return createErr
	})
	if err != nil {
		a.logger.Error("failed to create discord session", err)
		return fmt.Errorf("failed to create Discord session: %w", err)
	}

	// Get color for severity
	color := severityColor[strings.ToLower(input.Severity)]
	if color == 0 {
		color = severityColor["unspecified"]
	}

	// Get emoji for issue type
	emoji := issueTypeEmoji[strings.ToLower(input.IssueType)]
	if emoji == "" {
		emoji = issueTypeEmoji["unspecified"]
	}

	// Create embed for the issue proposal
	embed := &discordgo.MessageEmbed{
		Title:       fmt.Sprintf("%s New Issue Proposed: %s", emoji, input.IssueTitle),
		Description: truncateString(input.IssueBody, 4000),
		Color:       color,
		Fields: []*discordgo.MessageEmbedField{
			{
				Name:   "Severity",
				Value:  strings.ToUpper(input.Severity),
				Inline: true,
			},
			{
				Name:   "Type",
				Value:  strings.ToUpper(input.IssueType),
				Inline: true,
			},
			{
				Name:   "Labels",
				Value:  strings.Join(input.IssueLabels, ", "),
				Inline: true,
			},
			{
				Name:   "Workflow ID",
				Value:  input.WorkflowRunID,
				Inline: false,
			},
		},
		Footer: &discordgo.MessageEmbedFooter{
			Text: "IterateSwarm AI ChatOps",
		},
		Timestamp: time.Now().Format(time.RFC3339),
	}

	// Create approve button
	approveBtn := discordgo.Button{
		Label:    "Approve",
		Style:    discordgo.SuccessButton,
		CustomID: fmt.Sprintf("approve_%s", input.WorkflowRunID),
	}

	// Create reject button
	rejectBtn := discordgo.Button{
		Label:    "Reject",
		Style:    discordgo.DangerButton,
		CustomID: fmt.Sprintf("reject_%s", input.WorkflowRunID),
	}

	// Get channel info and send message with retry
	var channel *discordgo.Channel
	err = retry.SimpleRetry(func() error {
		var channelErr error
		channel, channelErr = dg.Channel(input.ChannelID)
		return channelErr
	})
	if err != nil {
		a.logger.Error("failed to get discord channel", err, "channel_id", input.ChannelID)
		return fmt.Errorf("failed to get Discord channel: %w", err)
	}

	a.logger.Info("sending to discord channel", "channel_name", channel.Name)

	var msg *discordgo.Message
	err = retry.SimpleRetry(func() error {
		var sendErr error
		msg, sendErr = dg.ChannelMessageSendComplex(input.ChannelID, &discordgo.MessageSend{
			Embeds:     []*discordgo.MessageEmbed{embed},
			Components: []discordgo.MessageComponent{discordgo.ActionsRow{Components: []discordgo.MessageComponent{approveBtn, rejectBtn}}},
		})
		return sendErr
	})
	if err != nil {
		a.logger.Error("failed to send discord message", err, "channel_id", input.ChannelID)
		return fmt.Errorf("failed to send Discord message: %w", err)
	}

	duration := time.Since(startTime)
	a.logger.LogActivity(ctx, "SendDiscordApproval", duration, true,
		"message_id", msg.ID,
		"channel_id", input.ChannelID,
	)

	return nil
}

// CreateGitHubIssueInput is the input for the CreateGitHubIssue activity.
type CreateGitHubIssueInput struct {
	Title     string
	Body      string
	Labels    []string
	RepoOwner string
	RepoName  string
	Assignee  string
}

// CreateGitHubIssue creates a GitHub issue when approved.
func (a *Activities) CreateGitHubIssue(ctx context.Context, input CreateGitHubIssueInput) (string, error) {
	startTime := time.Now()
	a.logger.Info("creating github issue",
		"title", input.Title,
		"repo_owner", input.RepoOwner,
		"repo_name", input.RepoName,
	)

	// Get GitHub token from environment
	githubToken := os.Getenv("GITHUB_TOKEN")
	if githubToken == "" {
		a.logger.Warn("github token not configured, skipping issue creation")
		return "", nil
	}

	// Create OAuth2 client for GitHub authentication
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: githubToken},
	)
	tc := oauth2.NewClient(ctx, ts)
	client := github.NewClient(tc)

	// Get repository owner from environment if not provided
	owner := input.RepoOwner
	if owner == "" {
		owner = os.Getenv("GITHUB_OWNER")
	}
	if owner == "" {
		return "", fmt.Errorf("GITHUB_OWNER not set and RepoOwner not provided")
	}

	// Get repository name from environment if not provided
	repo := input.RepoName
	if repo == "" {
		repo = os.Getenv("GITHUB_REPO")
	}
	if repo == "" {
		return "", fmt.Errorf("GITHUB_REPO not set and RepoName not provided")
	}

	// Prepare issue request
	issueLabels := &input.Labels
	if issueLabels == nil || len(*issueLabels) == 0 {
		defaultLabels := []string{"ai-generated"}
		issueLabels = &defaultLabels
	}

	issueRequest := &github.IssueRequest{
		Title:  &input.Title,
		Body:   &input.Body,
		Labels: issueLabels,
	}

	// Add assignee if provided
	if input.Assignee != "" {
		issueRequest.Assignee = &input.Assignee
	}

	// Create the issue with retry
	var issue *github.Issue
	err := retry.SimpleRetry(func() error {
		var createErr error
		issue, _, createErr = client.Issues.Create(ctx, owner, repo, issueRequest)
		return createErr
	})
	if err != nil {
		a.logger.Error("failed to create github issue", err,
			"owner", owner,
			"repo", repo,
		)
		return "", fmt.Errorf("failed to create GitHub issue: %w", err)
	}

	issueURL := issue.GetHTMLURL()
	duration := time.Since(startTime)
	a.logger.LogActivity(ctx, "CreateGitHubIssue", duration, true,
		"issue_url", issueURL,
		"issue_number", issue.GetNumber(),
	)

	return issueURL, nil
}

// truncateString truncates a string to the specified max length.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
