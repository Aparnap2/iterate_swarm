#!/usr/bin/env python
"""Integration test for Kafka producer with local Kafka broker."""

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from src.core.config import settings
from src.services.kafka import StandardKafkaService
from src.schemas.ingestion import FeedbackItem, FeedbackSource


async def test_kafka_producer():
    """Test sending a message to local Kafka."""
    print("Testing Kafka producer with local Kafka...")
    print(f"  Kafka URL: {settings.kafka_rest_url}")
    print(f"  Topic: {settings.kafka_topic_feedback}")

    async with StandardKafkaService() as kafka:
        # Create a test feedback item
        feedback = FeedbackItem(
            id=uuid4(),
            source=FeedbackSource.MANUAL,
            raw_content="Integration test: The login button is broken",
            timestamp=datetime.now(timezone.utc),
            metadata={"test": True},
        )

        print(f"  Sending feedback: {feedback.raw_content[:50]}...")

        result = await kafka.publish(
            topic=settings.kafka_topic_feedback,
            data=feedback.to_kafka_message(),
            message_id=str(feedback.id),
        )

        print(f"  Result: {result}")
        print("  ✅ Message sent successfully!")
        return True


async def read_from_kafka():
    """Read messages from Kafka to verify."""
    print("\nReading messages from Kafka...")
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_feedback,
        bootstrap_servers="localhost:9093",
        auto_offset_reset="earliest",
        group_id="test-consumer",
    )

    await consumer.start()
    print("  Consumer started. Waiting for messages...")

    try:
        # Wait up to 5 seconds for a message
        msg = await asyncio.wait_for(consumer.getone(), timeout=5.0)
        print(f"  Received: {msg.value.decode('utf-8')[:100]}...")
        print("  ✅ Message received!")
        return True
    except asyncio.TimeoutError:
        print("  ⚠️  No messages received (timeout)")
        return False
    finally:
        await consumer.stop()


if __name__ == "__main__":
    try:
        success = asyncio.run(test_kafka_producer())
        if success:
            asyncio.run(read_from_kafka())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
