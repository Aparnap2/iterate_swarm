package workflow

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"iterateswarm-core/internal/grpc"

	"github.com/bwmarrin/discordgo"
	"github.com/google/go-github/v50/github"
	"golang.org/x/oauth2"
)

// Activities contains the workflow activities.
type Activities struct {
	aiClient *grpc.Client
}

// NewActivities creates a new Activities instance.
func NewActivities(aiClient *grpc.Client) *Activities {
	return &Activities{aiClient: aiClient}
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
	IsDuplicate    bool
	Reasoning      string
	Title          string
	Severity       string
	IssueType      string
	Description    string
	Labels         []string
	Confidence     float64
}

// AnalyzeFeedback calls the Python AI service to analyze feedback.
func (a *Activities) AnalyzeFeedback(ctx context.Context, input AnalyzeFeedbackInput) (*AnalyzeFeedbackOutput, error) {
	log.Printf("Analyzing feedback: text=%s, source=%s, user=%s", input.Text, input.Source, input.UserID)

	resp, err := a.aiClient.AnalyzeFeedback(ctx, input.Text, input.Source, input.UserID)
	if err != nil {
		log.Printf("AnalyzeFeedback failed: %v", err)
		return nil, err
	}

	output := &AnalyzeFeedbackOutput{
		IsDuplicate: resp.IsDuplicate,
		Reasoning:   resp.Reasoning,
		Title:       resp.Spec.Title,
		Severity:    grpc.GetSeverity(resp),
		IssueType:   grpc.GetIssueType(resp),
		Description: resp.Spec.Description,
		Labels:      resp.Spec.Labels,
		Confidence:  0.85, // TODO: Get actual confidence from response
	}

	log.Printf(
		"AnalyzeFeedback complete: is_duplicate=%v, type=%s, severity=%s",
		output.IsDuplicate,
		output.IssueType,
		output.Severity,
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
	"critical": 0xff0000, // Red
	"high":     0xff6600, // Orange
	"medium":   0xffff00, // Yellow
	"low":      0x00ff00, // Green
	"unspecified": 0x808080, // Gray
}

// issueTypeEmoji maps issue types to emojis.
var issueTypeEmoji = map[string]string{
	"bug":       "🐛",
	"feature":   "✨",
	"question":  "❓",
	"unspecified": "📝",
}

// SendDiscordApproval sends an approval request to Discord with Approve/Reject buttons.
func (a *Activities) SendDiscordApproval(ctx context.Context, input SendDiscordApprovalInput) error {
	log.Printf(
		"Sending Discord approval request: channel=%s, title=%s",
		input.ChannelID,
		input.IssueTitle,
	)

	// Get Discord bot token from environment
	discordToken := os.Getenv("DISCORD_BOT_TOKEN")
	if discordToken == "" {
		log.Printf("DISCORD_BOT_TOKEN not set, skipping Discord notification")
		return nil // Don't fail the workflow if Discord is not configured
	}

	// Create Discord session
	dg, err := discordgo.New("Bot " + discordToken)
	if err != nil {
		log.Printf("Failed to create Discord session: %v", err)
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
		Label:    "✅ Approve",
		Style:    discordgo.SuccessButton,
		CustomID: fmt.Sprintf("approve_%s", input.WorkflowRunID),
	}

	// Create reject button
	rejectBtn := discordgo.Button{
		Label:    "❌ Reject",
		Style:    discordgo.DangerButton,
		CustomID: fmt.Sprintf("reject_%s", input.WorkflowRunID),
	}

	// Send message to channel
	channel, err := dg.Channel(input.ChannelID)
	if err != nil {
		log.Printf("Failed to get Discord channel: %v", err)
		return fmt.Errorf("failed to get Discord channel: %w", err)
	}

	log.Printf("Sending Discord approval request to channel: %s", channel.Name)

	// Use webhook followup for sending messages with components
	// First we need to create a message reference
	msg, err := dg.ChannelMessageSendComplex(input.ChannelID, &discordgo.MessageSend{
		Embeds:     []*discordgo.MessageEmbed{embed},
		Components: []discordgo.MessageComponent{discordgo.ActionsRow{Components: []discordgo.MessageComponent{approveBtn, rejectBtn}}},
	})
	if err != nil {
		log.Printf("Failed to send Discord message: %v", err)
		return fmt.Errorf("failed to send Discord message: %w", err)
	}

	log.Printf("Discord approval request sent successfully: message_id=%s", msg.ID)
	return nil
}

// CreateGitHubIssueInput is the input for the CreateGitHubIssue activity.
type CreateGitHubIssueInput struct {
	Title       string
	Body        string
	Labels      []string
	RepoOwner   string
	RepoName    string
	Assignee    string
}

// CreateGitHubIssue creates a GitHub issue when approved.
func (a *Activities) CreateGitHubIssue(ctx context.Context, input CreateGitHubIssueInput) (string, error) {
	log.Printf(
		"Creating GitHub issue: title=%s, repo=%s/%s",
		input.Title,
		input.RepoOwner,
		input.RepoName,
	)

	// Get GitHub token from environment
	githubToken := os.Getenv("GITHUB_TOKEN")
	if githubToken == "" {
		log.Printf("GITHUB_TOKEN not set, skipping GitHub issue creation")
		return "", nil // Don't fail the workflow if GitHub is not configured
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

	// Create the issue
	issue, _, err := client.Issues.Create(ctx, owner, repo, issueRequest)
	if err != nil {
		log.Printf("Failed to create GitHub issue: %v", err)
		return "", fmt.Errorf("failed to create GitHub issue: %w", err)
	}

	issueURL := issue.GetHTMLURL()
	log.Printf("GitHub issue created successfully: url=%s, number=%d", issueURL, issue.GetNumber())

	return issueURL, nil
}

// truncateString truncates a string to the specified max length.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
