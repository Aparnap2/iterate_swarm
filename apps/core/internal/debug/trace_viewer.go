package debug

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"iterateswarm-core/internal/logging"
)

// Trace represents a distributed trace.
type Trace struct {
	TraceID       string      `json:"trace_id"`
	Spans         []Span      `json:"spans"`
	Duration      time.Duration `json:"duration"`
	StartTime     time.Time   `json:"start_time"`
	EndTime       time.Time   `json:"end_time"`
	ServiceName   string      `json:"service_name"`
	Status        string      `json:"status"`
}

// Span represents a single trace span.
type Span struct {
	SpanID        string            `json:"span_id"`
	TraceID       string            `json:"trace_id"`
	ParentSpanID  string            `json:"parent_span_id,omitempty"`
	OperationName string            `json:"operation_name"`
	ServiceName   string            `json:"service_name"`
	StartTime     time.Time         `json:"start_time"`
	EndTime       time.Time         `json:"end_time"`
	Duration      time.Duration     `json:"duration"`
	Tags          map[string]string `json:"tags,omitempty"`
	Logs          []SpanLog         `json:"logs,omitempty"`
	References    []SpanReference  `json:"references,omitempty"`
	Children      []string          `json:"children,omitempty"`
}

// SpanLog represents a log entry in a span.
type SpanLog struct {
	Timestamp time.Time         `json:"timestamp"`
	Message   string            `json:"message"`
	Fields    map[string]string `json:"fields,omitempty"`
}

// SpanReference represents a reference to another span.
type SpanReference struct {
	RefType string `json:"ref_type"`
	TraceID string `json:"trace_id"`
	SpanID  string `json:"span_id"`
}

// TraceDetail represents detailed trace information for the API.
type TraceDetail struct {
	TraceID      string          `json:"trace_id"`
	Spans        []Span          `json:"spans"`
	SpanCount    int             `json:"span_count"`
	Duration     string          `json:"duration"`
	StartTime    string          `json:"start_time"`
	Services     []string        `json:"services"`
	Status       string          `json:"status"`
	Errors       []string        `json:"errors,omitempty"`
}

// JaegerTraceResponse represents the response from Jaeger API.
type JaegerTraceResponse struct {
	Data   []JaegerTrace `json:"data"`
	Total  int           `json:"total"`
	Limit  int           `json:"limit"`
	Offset int           `json:"offset"`
}

// JaegerTrace represents a trace from Jaeger.
type JaegerTrace struct {
	TraceID   string     `json:"traceID"`
	Spans     []JaegerSpan `json:"spans"`
	Processes map[string]JaegerProcess `json:"processes"`
	Warnings  []string   `json:"warnings,omitempty"`
}

// JaegerSpan represents a span from Jaeger.
type JaegerSpan struct {
	TraceID    string         `json:"traceID"`
	SpanID     string         `json:"spanID"`
	ParentSpanID string       `json:"parentSpanID,omitempty"`
	OperationName string     `json:"operationName"`
	References []JaegerRef   `json:"references,omitempty"`
	StartTime  int64          `json:"startTime"`
	Duration   int64          `json:"duration"`
	Tags       []JaegerTag   `json:"tags,omitempty"`
	Logs       []JaegerLog   `json:"logs,omitempty"`
	Process    JaegerProcess `json:"process,omitempty"`
}

// JaegerRef represents a span reference in Jaeger.
type JaegerRef struct {
	RefType    string `json:"refType"`
	TraceID    string `json:"traceID"`
	SpanID     string `json:"spanID"`
}

// JaegerTag represents a tag in Jaeger.
type JaegerTag struct {
	Key   string      `json:"key"`
	Value interface{} `json:"value"`
	Type  string      `json:"type,omitempty"`
}

// JaegerLog represents a log entry in Jaeger.
type JaegerLog struct {
	Timestamp int64       `json:"timestamp"`
	Fields    []JaegerLogField `json:"fields"`
}

// JaegerLogField represents a field in a log entry.
type JaegerLogField struct {
	Key   string `json:"key"`
	Value string `json:"value"`
	Type  string `json:"type,omitempty"`
}

// JaegerProcess represents a process in Jaeger.
type JaegerProcess struct {
	ServiceName string      `json:"serviceName"`
	Tags        []JaegerTag `json:"tags,omitempty"`
}

// GetTraceDetails retrieves trace details from Jaeger.
func GetTraceDetails(ctx context.Context, jaegerURL, traceID string) (*TraceDetail, error) {
	if jaegerURL == "" {
		jaegerURL = "http://localhost:16686"
	}

	url := fmt.Sprintf("%s/api/traces/%s", jaegerURL, traceID)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch trace: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jaeger API error: %s", string(body))
	}

	var jaegerResp JaegerTraceResponse
	if err := json.NewDecoder(resp.Body).Decode(&jaegerResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if len(jaegerResp.Data) == 0 {
		return nil, fmt.Errorf("trace not found: %s", traceID)
	}

	return convertJaegerTrace(jaegerResp.Data[0]), nil
}

// convertJaegerTrace converts a Jaeger trace to our TraceDetail format.
func convertJaegerTrace(jaegerTrace JaegerTrace) *TraceDetail {
	detail := &TraceDetail{
		TraceID:   jaegerTrace.TraceID,
		Spans:     make([]Span, 0, len(jaegerTrace.Spans)),
		Services:  make([]string, 0),
		Status:    "ok",
		Errors:    make([]string, 0),
	}

	serviceSet := make(map[string]bool)
	var minTime, maxTime time.Time

	for _, jaegerSpan := range jaegerTrace.Spans {
		span := Span{
			SpanID:        jaegerSpan.SpanID,
			TraceID:       jaegerSpan.TraceID,
			ParentSpanID:  jaegerSpan.ParentSpanID,
			OperationName: jaegerSpan.OperationName,
			StartTime:     time.UnixMicro(jaegerSpan.StartTime),
			Duration:      time.Duration(jaegerSpan.Duration) * time.Microsecond,
		}

		if jaegerSpan.Process.ServiceName != "" {
			span.ServiceName = jaegerSpan.Process.ServiceName
			if !serviceSet[jaegerSpan.Process.ServiceName] {
				serviceSet[jaegerSpan.Process.ServiceName] = true
				detail.Services = append(detail.Services, jaegerSpan.Process.ServiceName)
			}
		}

		// Convert tags
		span.Tags = make(map[string]string)
		for _, tag := range jaegerSpan.Tags {
			if tag.Value != nil {
				span.Tags[tag.Key] = fmt.Sprintf("%v", tag.Value)
				if tag.Key == "error" && tag.Value == true {
					detail.Status = "error"
					detail.Errors = append(detail.Errors, span.OperationName)
				}
			}
		}

		// Convert logs
		span.Logs = make([]SpanLog, 0)
		for _, log := range jaegerSpan.Logs {
			logEntry := SpanLog{
				Timestamp: time.UnixMicro(log.Timestamp),
				Fields:    make(map[string]string),
			}
			for _, field := range log.Fields {
				logEntry.Fields[field.Key] = field.Value
				if field.Key == "message" {
					logEntry.Message = field.Value
				}
			}
			span.Logs = append(span.Logs, logEntry)
		}

		// Convert references
		for _, ref := range jaegerSpan.References {
			span.References = append(span.References, SpanReference{
				RefType: ref.RefType,
				TraceID: ref.TraceID,
				SpanID:  ref.SpanID,
			})
		}

		span.EndTime = span.StartTime.Add(span.Duration)

		detail.Spans = append(detail.Spans, span)

		// Track min/max times
		if minTime.IsZero() || span.StartTime.Before(minTime) {
			minTime = span.StartTime
		}
		if maxTime.IsZero() || span.EndTime.After(maxTime) {
			maxTime = span.EndTime
		}
	}

	if !minTime.IsZero() && !maxTime.IsZero() {
		detail.Duration = maxTime.Sub(minTime).String()
		detail.StartTime = minTime.Format(time.RFC3339)
	}

	detail.SpanCount = len(detail.Spans)

	return detail
}

// SearchTraces searches for traces by service and operation.
func SearchTraces(ctx context.Context, jaegerURL, service, operation string, limit int) ([]TraceSummary, error) {
	if jaegerURL == "" {
		jaegerURL = "http://localhost:16686"
	}

	url := fmt.Sprintf("%s/api/traces?service=%s", jaegerURL, service)
	if operation != "" {
		url += fmt.Sprintf("&operation=%s", operation)
	}
	if limit > 0 {
		url += fmt.Sprintf("&limit=%d", limit)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch traces: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jaeger API error: %s", string(body))
	}

	var jaegerResp JaegerTraceResponse
	if err := json.NewDecoder(resp.Body).Decode(&jaegerResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	summaries := make([]TraceSummary, 0, len(jaegerResp.Data))
	for _, t := range jaegerResp.Data {
		summary := TraceSummary{
			TraceID:   t.TraceID,
			SpanCount: len(t.Spans),
			Services:  make([]string, 0),
		}

		for _, span := range t.Spans {
			if span.Process.ServiceName != "" {
				found := false
				for _, s := range summary.Services {
					if s == span.Process.ServiceName {
						found = true
						break
					}
				}
				if !found {
					summary.Services = append(summary.Services, span.Process.ServiceName)
				}
			}

			if summary.OperationName == "" {
				summary.OperationName = span.OperationName
				summary.StartTime = time.UnixMicro(span.StartTime).Format(time.RFC3339)
				summary.Duration = time.Duration(span.Duration) * time.Microsecond
			}
		}

		summaries = append(summaries, summary)
	}

	return summaries, nil
}

// TraceSummary represents a summary of a trace for listing.
type TraceSummary struct {
	TraceID      string   `json:"trace_id"`
	SpanCount    int      `json:"span_count"`
	OperationName string  `json:"operation_name"`
	StartTime    string  `json:"start_time"`
	Duration     time.Duration `json:"duration"`
	Services     []string `json:"services"`
}

// ListServices lists available services from Jaeger.
func ListServices(ctx context.Context, jaegerURL string) ([]string, error) {
	if jaegerURL == "" {
		jaegerURL = "http://localhost:16686"
	}

	url := fmt.Sprintf("%s/api/services", jaegerURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch services: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jaeger API error: %s", string(body))
	}

	var result struct {
		Data []struct {
			Name string `json:"name"`
		} `json:"data"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	services := make([]string, 0, len(result.Data))
	for _, s := range result.Data {
		services = append(services, s.Name)
	}

	return services, nil
}

// CorrelateTraceID correlates a trace ID across different services.
func CorrelateTraceID(ctx context.Context, traceID string) (*Trace, error) {
	logger := logging.NewLogger("trace-correlation")
	logger.Info("correlating trace", "trace_id", traceID)

	// Get trace details from Jaeger
	trace, err := GetTraceDetails(ctx, "", traceID)
	if err != nil {
		return nil, err
	}

	// Build trace tree with parent-child relationships
	spansByID := make(map[string]*Span)
	for i := range trace.Spans {
		spansByID[trace.Spans[i].SpanID] = &trace.Spans[i]
	}

	// Build hierarchy
	for i := range trace.Spans {
		span := &trace.Spans[i]
		if span.ParentSpanID != "" {
			if parent, ok := spansByID[span.ParentSpanID]; ok {
				parent.Children = append(parent.Children, span.SpanID)
			}
		}
	}

	return &Trace{
		TraceID: trace.TraceID,
		Spans:   trace.Spans,
		Status:  trace.Status,
	}, nil
}
