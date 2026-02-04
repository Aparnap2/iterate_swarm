package redpanda

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

// Client wraps the Kafka client.
type Client struct {
	writer *kafka.Writer
	reader *kafka.Reader
	topic  string
}

// NewClient creates a new Kafka client.
func NewClient(brokers []string, topic string) (*Client, error) {
	log.Printf("Connecting to Kafka at %v", brokers)

	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.LeastBytes{},
		BatchTimeout: 10 * time.Millisecond,
	}

	// Ensure topic exists by creating it if needed
	conn, err := kafka.Dial("tcp", brokers[0])
	if err != nil {
		log.Printf("Warning: Could not connect to Kafka: %v", err)
	} else {
		controller, err := conn.Controller()
		if err != nil {
			log.Printf("Warning: Could not get controller: %v", err)
		} else {
			controllerConn, err := kafka.Dial("tcp", fmt.Sprintf("%s:%d", controller.Host, controller.Port))
			if err != nil {
				log.Printf("Warning: Could not connect to controller: %v", err)
			} else {
				topicConfigs := []kafka.TopicConfig{
					{
						Topic:             topic,
						NumPartitions:     1,
						ReplicationFactor: 1,
					},
				}
				err = controllerConn.CreateTopics(topicConfigs...)
				if err != nil {
					log.Printf("Topic creation result: %v", err)
				}
				controllerConn.Close()
			}
		}
		conn.Close()
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  brokers,
		Topic:    topic,
		GroupID:  "iterateswarm-consumer",
		MinBytes: 10e3, // 10KB
		MaxBytes: 10e6, // 10MB
	})

	return &Client{
		writer: writer,
		reader: reader,
		topic:  topic,
	}, nil
}

// Publish sends a message to the configured topic.
func (c *Client) Publish(value []byte) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	msg := kafka.Message{
		Value: value,
		Key:   []byte(time.Now().Format(time.RFC3339)),
	}

	err := c.writer.WriteMessages(ctx, msg)
	if err != nil {
		log.Printf("Failed to publish message: %v", err)
		return err
	}

	log.Printf("Message published to %s", c.topic)
	return nil
}

// PublishToTopic sends a message to a specific topic (overrides configured topic).
func (c *Client) PublishToTopic(topic string, value []byte) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	msg := kafka.Message{
		Topic: topic,
		Value: value,
		Key:   []byte(time.Now().Format(time.RFC3339)),
	}

	err := c.writer.WriteMessages(ctx, msg)
	if err != nil {
		log.Printf("Failed to publish message: %v", err)
		return err
	}

	log.Printf("Message published to %s", topic)
	return nil
}

// PublishFeedback sends a feedback event.
func (c *Client) PublishFeedback(data []byte) error {
	return c.Publish(data)
}

// Consume consumes messages from a topic.
func (c *Client) Consume(ctx context.Context, topic string) <-chan kafka.Message {
	records := make(chan kafka.Message, 100)

	go func() {
		defer close(records)

		for {
			select {
			case <-ctx.Done():
				return
			default:
				msg, err := c.reader.FetchMessage(ctx)
				if err != nil {
					if ctx.Err() != nil {
						return
					}
					log.Printf("Consumer error: %v", err)
					continue
				}
				records <- msg
			}
		}
	}()

	return records
}

// Close closes the client.
func (c *Client) Close() error {
	if c.reader != nil {
		c.reader.Close()
	}
	if c.writer != nil {
		return c.writer.Close()
	}
	return nil
}

// Health checks if the client is healthy.
func (c *Client) Health(ctx context.Context) error {
	conn, err := kafka.Dial("tcp", "localhost:19092")
	if err != nil {
		return err
	}
	defer conn.Close()
	return nil
}
