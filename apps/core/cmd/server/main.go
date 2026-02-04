package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"

	"iterateswarm-core/internal/api"
	"iterateswarm-core/internal/redpanda"
	"iterateswarm-core/internal/temporal"
)

func main() {
	// Command line flags
	redpandaBrokers := flag.String("redpanda", "localhost:19092", "Redpanda brokers")
	temporalAddr := flag.String("temporal", "localhost:7233", "Temporal address")
	namespace := flag.String("namespace", "default", "Temporal namespace")
	port := flag.String("port", "3000", "HTTP server port")
	topic := flag.String("topic", "feedback-events", "Kafka topic")

	flag.Parse()

	log.Println("Starting IterateSwarm Core Server...")

	// Initialize Redpanda client
	redpandaClient, err := redpanda.NewClient([]string{*redpandaBrokers}, *topic)
	if err != nil {
		log.Fatalf("Failed to connect to Redpanda: %v", err)
	}
	defer redpandaClient.Close()
	log.Println("Connected to Redpanda")

	// Initialize Temporal client
	temporalClient, err := temporal.NewClient(*temporalAddr, *namespace)
	if err != nil {
		log.Fatalf("Failed to connect to Temporal: %v", err)
	}
	defer temporalClient.Close()
	log.Println("Connected to Temporal")

	// Create Fiber app
	app := fiber.New(fiber.Config{
		AppName:      "IterateSwarm Core",
		ErrorHandler: errorHandler,
	})

	// Middleware
	app.Use(recover.New())
	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} - ${method} ${path} (${latency})\n",
	}))
	app.Use(cors.New())

	// Create handler
	handler := api.NewHandler(redpandaClient, temporalClient)

	// Routes
	app.Get("/health", handler.HandleHealth)
	app.Get("/health/details", handler.HandleDetailedHealth)
	app.Post("/webhooks/discord", handler.HandleDiscordWebhook)
	app.Post("/webhooks/interaction", handler.HandleInteraction)
	app.Get("/test/kafka", handler.HandleKafkaTest)

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-quit
		log.Println("Shutting down server...")
		if err := app.Shutdown(); err != nil {
			log.Printf("Error during shutdown: %v", err)
		}
	}()

	// Start server
	addr := ":" + *port
	log.Printf("Server listening on %s", addr)
	if err := app.Listen(addr); err != nil {
		log.Printf("Server error: %v", err)
	}
}

func errorHandler(c *fiber.Ctx, err error) error {
	log.Printf("Error: %v", err)
	code := fiber.StatusInternalServerError
	if e, ok := err.(*fiber.Error); ok {
		code = e.Code
	}
	return c.Status(code).JSON(map[string]string{
		"error": err.Error(),
	})
}
