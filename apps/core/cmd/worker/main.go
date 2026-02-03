package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.temporal.io/sdk/worker"

	"iterateswarm-core/internal/grpc"
	"iterateswarm-core/internal/temporal"
	"iterateswarm-core/internal/workflow"
)

func main() {
	// Command line flags
	temporalAddr := flag.String("temporal", "localhost:7233", "Temporal address")
	namespace := flag.String("namespace", "default", "Temporal namespace")
	aiGRPCAddr := flag.String("ai-grpc", "localhost:50051", "Python AI service gRPC address")
	taskQueue := flag.String("queue", "feedback-queue", "Task queue name")

	flag.Parse()

	log.Println("Starting IterateSwarm Worker...")

	// Initialize Temporal client
	temporalClient, err := temporal.NewClient(*temporalAddr, *namespace)
	if err != nil {
		log.Fatalf("Failed to connect to Temporal: %v", err)
	}
	defer temporalClient.Close()
	log.Println("Connected to Temporal")

	// Initialize gRPC client for AI service
	aiClient, err := grpc.NewClientWithoutBlock(*aiGRPCAddr)
	if err != nil {
		log.Printf("Warning: Failed to connect to AI gRPC server: %v", err)
		log.Println("Worker will start, but AI calls will fail until AI service is available")
	} else {
		defer aiClient.Close()
		log.Println("Connected to AI gRPC service")
	}

	// Create Temporal worker
	w := worker.New(temporalClient.Client, *taskQueue, worker.Options{})

	// Register workflow and activities
	w.RegisterWorkflow(workflow.FeedbackWorkflow)

	activities := workflow.NewActivities(aiClient)
	w.RegisterActivity(activities.AnalyzeFeedback)
	w.RegisterActivity(activities.SendDiscordApproval)
	w.RegisterActivity(activities.CreateGitHubIssue)

	log.Printf("Worker listening on task queue: %s", *taskQueue)

	// Start worker in goroutine
	errCh := make(chan error, 1)
	go func() {
		err := w.Run(worker.InterruptCh())
		if err != nil {
			errCh <- err
		}
	}()

	// Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case <-quit:
		log.Println("Shutting down worker...")
	case err := <-errCh:
		log.Printf("Worker error: %v", err)
	}

	// Give activities time to complete
	_, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	log.Println("Worker stopped")
}
