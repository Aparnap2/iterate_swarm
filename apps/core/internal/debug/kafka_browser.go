package debug

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/segmentio/kafka-go"

	"iterateswarm-core/internal/redpanda"
)

// TopicMetadata represents Kafka topic metadata.
type TopicMetadata struct {
	Name              string            `json:"name"`
	Partitions        int               `json:"partitions"`
	ReplicationFactor int               `json:"replication_factor"`
	MessagesCount     int64             `json:"messages_count"`
	PartitionsInfo    []PartitionInfo   `json:"partitions_info,omitempty"`
}

// PartitionInfo represents metadata for a single partition.
type PartitionInfo struct {
	PartitionID      int       `json:"partition_id"`
	LeaderID         int       `json:"leader_id"`
	LeaderHost       string    `json:"leader_host,omitempty"`
	LeaderPort       int       `json:"leader_port,omitempty"`
	ReplicaCount     int       `json:"replica_count"`
	ISRCount         int       `json:"isr_count"`
	OfflineReplicas  int       `json:"offline_replicas,omitempty"`
}

// KafkaMessage represents a Kafka message for the API.
type KafkaMessage struct {
	Topic     string            `json:"topic"`
	Partition int               `json:"partition"`
	Offset    int64             `json:"offset"`
	Key       string            `json:"key,omitempty"`
	Value     string            `json:"value"`
	Headers   map[string]string `json:"headers,omitempty"`
	Timestamp time.Time         `json:"timestamp"`
}

// ListKafkaTopics returns a list of all Kafka topics with metadata.
func ListKafkaTopics(ctx context.Context, client *redpanda.Client) ([]TopicMetadata, error) {
	// Connect to Kafka to get list of topics (use internal port for Docker)
	conn, err := kafka.Dial("tcp", "localhost:19092")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Kafka: %w", err)
	}
	defer conn.Close()

	// Get all topics
	partitions, err := conn.ReadPartitions()
	if err != nil {
		return nil, fmt.Errorf("failed to read partitions: %w", err)
	}

	// Group partitions by topic
	topicMap := make(map[string][]kafka.Partition)
	for _, p := range partitions {
		topicMap[p.Topic] = append(topicMap[p.Topic], p)
	}

	// Build topic metadata
	topics := make([]TopicMetadata, 0, len(topicMap))
	for topicName, parts := range topicMap {
		topicMeta := TopicMetadata{
			Name:              topicName,
			Partitions:        len(parts),
			ReplicationFactor: getReplicationFactor(parts),
			PartitionsInfo:    make([]PartitionInfo, len(parts)),
		}

		for i, p := range parts {
			topicMeta.PartitionsInfo[i] = PartitionInfo{
				PartitionID:     p.ID,
				LeaderID:        p.Leader.ID,
				LeaderHost:      p.Leader.Host,
				LeaderPort:      p.Leader.Port,
				ReplicaCount:    len(p.Replicas),
				ISRCount:        len(p.Isr),
				OfflineReplicas: len(p.OfflineReplicas),
			}
		}

		topics = append(topics, topicMeta)
	}

	return topics, nil
}

// getReplicationFactor returns the replication factor for a topic.
func getReplicationFactor(partitions []kafka.Partition) int {
	if len(partitions) == 0 {
		return 0
	}
	return len(partitions[0].Replicas)
}

// GetKafkaTopicMessages returns messages from a specific Kafka topic with pagination.
func GetKafkaTopicMessages(ctx context.Context, client *redpanda.Client, topicName string, offset, limit int) ([]KafkaMessage, error) {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:19092"},
		Topic:    topicName,
		GroupID:  "debug-browser",
		MinBytes: 10e3,
		MaxBytes: 10e6,
	})
	defer reader.Close()

	messages := make([]KafkaMessage, 0, limit)

	for i := 0; i < limit; i++ {
		kafkaMsg, err := reader.FetchMessage(ctx)
		if err != nil {
			if err == context.DeadlineExceeded || err == context.Canceled {
				break
			}
			// Continue on error, don't fail the entire request
			continue
		}

		// Skip messages before offset
		if kafkaMsg.Offset < int64(offset) {
			continue
		}

		msg := KafkaMessage{
			Topic:     kafkaMsg.Topic,
			Partition: kafkaMsg.Partition,
			Offset:    kafkaMsg.Offset,
			Timestamp: kafkaMsg.Time,
		}

		if len(kafkaMsg.Key) > 0 {
			msg.Key = string(kafkaMsg.Key)
		}

		if len(kafkaMsg.Value) > 0 {
			msg.Value = string(kafkaMsg.Value)
		}

		if len(kafkaMsg.Headers) > 0 {
			msg.Headers = make(map[string]string)
			for _, h := range kafkaMsg.Headers {
				msg.Headers[h.Key] = string(h.Value)
			}
		}

		messages = append(messages, msg)
	}

	return messages, nil
}

// PublishTestMessage publishes a test message to a Kafka topic.
func PublishTestMessage(ctx context.Context, client *redpanda.Client, topic, message string) error {
	if topic == "" {
		topic = "feedback-events"
	}

	event := map[string]interface{}{
		"test_id":     fmt.Sprintf("test-%d", time.Now().UnixNano()),
		"message":     message,
		"source":      "lite-debug",
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
	}

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal test message: %w", err)
	}

	// Use the existing client's Publish method (configured for localhost:9094)
	// Note: Only publishes to the default topic configured in the client
	if err := client.Publish(data); err != nil {
		return fmt.Errorf("failed to publish test message: %w", err)
	}

	return nil
}

// Event represents a Redpanda event for the API.
type Event struct {
	Topic     string            `json:"topic"`
	Partition int               `json:"partition"`
	Offset    int64             `json:"offset"`
	Key       string            `json:"key,omitempty"`
	Value     string            `json:"value"`
	Headers   map[string]string `json:"headers,omitempty"`
	Timestamp time.Time         `json:"timestamp"`
}

// ListRecentEvents returns recent events from Redpanda.
func ListRecentEvents(ctx context.Context, client *redpanda.Client, limit int) ([]Event, error) {
	// Connect to Kafka to list topics
	conn, err := kafka.Dial("tcp", "localhost:19092")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Kafka: %w", err)
	}
	defer conn.Close()

	// Get all topics
	partitions, err := conn.ReadPartitions()
	if err != nil {
		return nil, fmt.Errorf("failed to read partitions: %w", err)
	}

	// Get unique topics
	topicSet := make(map[string]bool)
	for _, p := range partitions {
		topicSet[p.Topic] = true
	}

	events := make([]Event, 0, limit)

	// Read messages from each topic
	for topic := range topicSet {
		reader := kafka.NewReader(kafka.ReaderConfig{
			Brokers:  []string{"localhost:19092"},
			Topic:    topic,
			GroupID:  "debug-events-consumer",
			MinBytes: 10e3,
			MaxBytes: 10e6,
		})

		for i := 0; i < limit/len(topicSet)+1; i++ {
			kafkaMsg, err := reader.FetchMessage(ctx)
			if err != nil {
				if err == context.DeadlineExceeded || err == context.Canceled {
					break
				}
				continue
			}

			event := Event{
				Topic:     kafkaMsg.Topic,
				Partition: kafkaMsg.Partition,
				Offset:    kafkaMsg.Offset,
				Timestamp: kafkaMsg.Time,
			}

			if len(kafkaMsg.Key) > 0 {
				event.Key = string(kafkaMsg.Key)
			}

			if len(kafkaMsg.Value) > 0 {
				event.Value = string(kafkaMsg.Value)
			}

			if len(kafkaMsg.Headers) > 0 {
				event.Headers = make(map[string]string)
				for _, h := range kafkaMsg.Headers {
					event.Headers[h.Key] = string(h.Value)
				}
			}

			events = append(events, event)

			if len(events) >= limit {
				reader.Close()
				return events[:limit], nil
			}
		}

		reader.Close()
	}

	return events, nil
}
