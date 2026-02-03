package temporal

import (
	"context"
	"log"

	"go.temporal.io/sdk/client"
)

// Client wraps the Temporal client.
type Client struct {
	Client client.Client
}

// NewClient creates a new Temporal client.
func NewClient(hostPort, namespace string) (*Client, error) {
	log.Printf("Connecting to Temporal at %s", hostPort)

	c, err := client.Dial(client.Options{
		HostPort:  hostPort,
		Namespace: namespace,
	})
	if err != nil {
		return nil, err
	}

	return &Client{Client: c}, nil
}

// StartWorkflow starts a new workflow execution.
func (c *Client) StartWorkflow(ctx context.Context, workflowID, taskQueue string, input interface{}) (client.WorkflowRun, error) {
	run, err := c.Client.ExecuteWorkflow(
		ctx,
		client.StartWorkflowOptions{
			ID:        workflowID,
			TaskQueue: taskQueue,
		},
		input,
	)
	if err != nil {
		log.Printf("Failed to start workflow: %v", err)
		return nil, err
	}

	log.Printf("Workflow started: id=%s, run_id=%s", run.GetID(), run.GetRunID())
	return run, nil
}

// SignalWorkflow sends a signal to a workflow.
func (c *Client) SignalWorkflow(workflowID, signalName string, payload interface{}) error {
	ctx := context.Background()

	err := c.Client.SignalWorkflow(ctx, workflowID, "", signalName, payload)
	if err != nil {
		log.Printf("Failed to signal workflow: %v", err)
		return err
	}

	log.Printf("Signal sent: workflow=%s, signal=%s", workflowID, signalName)
	return nil
}

// Health checks if the client is healthy.
func (c *Client) Health(ctx context.Context) error {
	_, err := c.Client.DescribeWorkflowExecution(ctx, "health-check", "")
	return err
}

// Close closes the client.
func (c *Client) Close() {
	if c.Client != nil {
		c.Client.Close()
	}
}
