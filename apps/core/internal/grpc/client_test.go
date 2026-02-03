package grpc

import (
	"context"
	"testing"

	pb "github.com/Aparnap2/iterate_swarm/gen/go/ai/v1"
)

// MockAgentServiceClient is a mock implementation for testing
type MockAgentServiceClient struct {
	AnalyzeFeedbackFunc func(ctx context.Context, in *pb.AnalyzeFeedbackRequest) (*pb.AnalyzeFeedbackResponse, error)
}

func (m *MockAgentServiceClient) AnalyzeFeedback(ctx context.Context, in *pb.AnalyzeFeedbackRequest) (*pb.AnalyzeFeedbackResponse, error) {
	if m.AnalyzeFeedbackFunc != nil {
		return m.AnalyzeFeedbackFunc(ctx, in)
	}
	return &pb.AnalyzeFeedbackResponse{
		IsDuplicate: false,
		Reasoning:   "mock response",
		Spec: &pb.IssueSpec{
			Title:       "Mock Title",
			Severity:    pb.Severity_SEVERITY_MEDIUM,
			Type:        pb.IssueType_ISSUE_TYPE_BUG,
			Description: "Mock description",
			Labels:      []string{"test"},
		},
	}, nil
}

// Test Helpers

func createTestRequest(text, source, userID string) *pb.AnalyzeFeedbackRequest {
	return &pb.AnalyzeFeedbackRequest{
		Text:   text,
		Source: source,
		UserId: userID,
	}
}

func createTestResponse() *pb.AnalyzeFeedbackResponse {
	return &pb.AnalyzeFeedbackResponse{
		IsDuplicate: false,
		Reasoning:   "Test reasoning",
		Spec: &pb.IssueSpec{
			Title:       "Test Issue",
			Severity:    pb.Severity_SEVERITY_HIGH,
			Type:        pb.IssueType_ISSUE_TYPE_BUG,
			Description: "Test description",
			Labels:      []string{"bug", "urgent"},
		},
	}
}

// Tests

func TestAnalyzeFeedbackRequest(t *testing.T) {
	req := createTestRequest("Test feedback", "discord", "user123")

	if req.Text != "Test feedback" {
		t.Errorf("Expected text 'Test feedback', got '%s'", req.Text)
	}
	if req.Source != "discord" {
		t.Errorf("Expected source 'discord', got '%s'", req.Source)
	}
	if req.UserId != "user123" {
		t.Errorf("Expected user_id 'user123', got '%s'", req.UserId)
	}
}

func TestAnalyzeFeedbackResponse(t *testing.T) {
	resp := createTestResponse()

	if resp.IsDuplicate {
		t.Error("Expected IsDuplicate to be false")
	}
	if resp.Reasoning != "Test reasoning" {
		t.Errorf("Expected reasoning 'Test reasoning', got '%s'", resp.Reasoning)
	}
	if resp.Spec.Title != "Test Issue" {
		t.Errorf("Expected title 'Test Issue', got '%s'", resp.Spec.Title)
	}
	if resp.Spec.Severity != pb.Severity_SEVERITY_HIGH {
		t.Errorf("Expected severity HIGH, got %v", resp.Spec.Severity)
	}
	if resp.Spec.Type != pb.IssueType_ISSUE_TYPE_BUG {
		t.Errorf("Expected type BUG, got %v", resp.Spec.Type)
	}
	if len(resp.Spec.Labels) != 2 {
		t.Errorf("Expected 2 labels, got %d", len(resp.Spec.Labels))
	}
}

func TestIssueSpecCreation(t *testing.T) {
	spec := &pb.IssueSpec{
		Title:       "Critical Bug",
		Severity:    pb.Severity_SEVERITY_CRITICAL,
		Type:        pb.IssueType_ISSUE_TYPE_BUG,
		Description: "A critical security vulnerability",
		Labels:      []string{"security", "critical", "bug"},
	}

	if spec.Severity != pb.Severity_SEVERITY_CRITICAL {
		t.Error("Expected CRITICAL severity")
	}
	if spec.Type != pb.IssueType_ISSUE_TYPE_BUG {
		t.Error("Expected BUG type")
	}
	if len(spec.Labels) != 3 {
		t.Errorf("Expected 3 labels, got %d", len(spec.Labels))
	}
}

func TestDuplicateDetectionResponse(t *testing.T) {
	resp := &pb.AnalyzeFeedbackResponse{
		IsDuplicate: true,
		Reasoning:   "Similarity score 0.92 exceeds threshold 0.85",
		Spec: &pb.IssueSpec{
			Title:       "Duplicate of #123",
			Severity:    pb.Severity_SEVERITY_LOW,
			Type:        pb.IssueType_ISSUE_TYPE_BUG,
			Description: "",
			Labels:      []string{"duplicate"},
		},
	}

	if !resp.IsDuplicate {
		t.Error("Expected IsDuplicate to be true")
	}
	if resp.Spec.Severity != pb.Severity_SEVERITY_LOW {
		t.Error("Expected LOW severity for duplicates")
	}
}

func TestFeatureRequestResponse(t *testing.T) {
	resp := &pb.AnalyzeFeedbackResponse{
		IsDuplicate: false,
		Reasoning:   "User wants dark mode",
		Spec: &pb.IssueSpec{
			Title:       "Add dark mode support",
			Severity:    pb.Severity_SEVERITY_MEDIUM,
			Type:        pb.IssueType_ISSUE_TYPE_FEATURE,
			Description: "Users want dark mode",
			Labels:      []string{"enhancement", "ui"},
		},
	}

	if resp.Spec.Type != pb.IssueType_ISSUE_TYPE_FEATURE {
		t.Errorf("Expected FEATURE type, got %v", resp.Spec.Type)
	}
	if resp.Spec.Severity != pb.Severity_SEVERITY_MEDIUM {
		t.Errorf("Expected MEDIUM severity, got %v", resp.Spec.Severity)
	}
}

func TestQuestionResponse(t *testing.T) {
	resp := &pb.AnalyzeFeedbackResponse{
		IsDuplicate: false,
		Reasoning:   "User asking how to configure",
		Spec: &pb.IssueSpec{
			Title:       "Document webhook setup",
			Severity:    pb.Severity_SEVERITY_LOW,
			Type:        pb.IssueType_ISSUE_TYPE_QUESTION,
			Description: "How to set up webhooks",
			Labels:      []string{"documentation"},
		},
	}

	if resp.Spec.Type != pb.IssueType_ISSUE_TYPE_QUESTION {
		t.Error("Expected QUESTION type")
	}
	if resp.Spec.Severity != pb.Severity_SEVERITY_LOW {
		t.Error("Expected LOW severity for questions")
	}
}

func TestSeverityEnums(t *testing.T) {
	tests := []struct {
		severity pb.Severity
		expected int32
	}{
		{pb.Severity_SEVERITY_UNSPECIFIED, 0},
		{pb.Severity_SEVERITY_LOW, 1},
		{pb.Severity_SEVERITY_MEDIUM, 2},
		{pb.Severity_SEVERITY_HIGH, 3},
		{pb.Severity_SEVERITY_CRITICAL, 4},
	}

	for _, tt := range tests {
		if int32(tt.severity) != tt.expected {
			t.Errorf("Expected %v to be %d, got %d", tt.severity, tt.expected, int32(tt.severity))
		}
	}
}

func TestIssueTypeEnums(t *testing.T) {
	tests := []struct {
		issueType pb.IssueType
		expected  int32
	}{
		{pb.IssueType_ISSUE_TYPE_UNSPECIFIED, 0},
		{pb.IssueType_ISSUE_TYPE_BUG, 1},
		{pb.IssueType_ISSUE_TYPE_FEATURE, 2},
		{pb.IssueType_ISSUE_TYPE_QUESTION, 3},
	}

	for _, tt := range tests {
		if int32(tt.issueType) != tt.expected {
			t.Errorf("Expected %v to be %d, got %d", tt.issueType, tt.expected, int32(tt.issueType))
		}
	}
}

func TestMockClient(t *testing.T) {
	client := &MockAgentServiceClient{
		AnalyzeFeedbackFunc: func(ctx context.Context, in *pb.AnalyzeFeedbackRequest) (*pb.AnalyzeFeedbackResponse, error) {
			if in.Text == "error" {
				return nil, nil
			}
			return &pb.AnalyzeFeedbackResponse{
				IsDuplicate: false,
				Reasoning:   "custom mock response",
			}, nil
		},
	}

	// Test normal response
	ctx := context.Background()
	resp, err := client.AnalyzeFeedback(ctx, createTestRequest("test", "discord", "user"))
	if err != nil {
		t.Errorf("Unexpected error: %v", err)
	}
	if resp.Reasoning != "custom mock response" {
		t.Errorf("Expected 'custom mock response', got '%s'", resp.Reasoning)
	}

	// Test error case
	resp, err = client.AnalyzeFeedback(ctx, createTestRequest("error", "discord", "user"))
	if err != nil {
		t.Errorf("Expected nil error, got: %v", err)
	}
	if resp != nil {
		t.Error("Expected nil response for error case")
	}
}
