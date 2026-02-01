// Kafka Producer using kafkajs
// Configured for Aiven Kafka with SSL/SASL support

import { Kafka, Producer, logLevel } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'iterateswarm-web',
  brokers: process.env.KAFKA_BROKERS?.split(',') ?? ['localhost:9092'],
  logLevel: logLevel.WARN,
  ssl: process.env.KAFKA_SSL === 'true' ? {
    rejectUnauthorized: true,
  } : false,
  sasl: process.env.KAFKA_USERNAME && process.env.KAFKA_PASSWORD ? {
    mechanism: 'scram-sha-512',
    username: process.env.KAFKA_USERNAME,
    password: process.env.KAFKA_PASSWORD,
  } : undefined,
});

let producer: Producer | null = null;
let producerPromise: Promise<Producer> | null = null;

export async function getKafkaProducer(): Promise<Producer> {
  if (!producer) {
    if (!producerPromise) {
      producerPromise = (async () => {
        const newProducer = kafka.producer({
          allowAutoTopicCreation: true,
          transactionTimeout: 30000,
        });

        await newProducer.connect();
        console.log('Kafka producer connected');
        return newProducer;
      })();
    }
    producer = await producerPromise;
  }

  return producer;
}

export async function disconnectProducer(): Promise<void> {
  if (producer) {
    await producer.disconnect();
    producer = null;
    producerPromise = null;
    console.log('Kafka producer disconnected');
  }
}

export async function sendFeedbackEvent(
  feedbackId: string,
  content: string,
  source: string,
): Promise<void> {
  const prod = await getKafkaProducer();

  await prod.send({
    topic: process.env.KAFKA_TOPIC_FEEDBACK ?? 'feedback-received',
    messages: [
      {
        key: feedbackId,
        value: JSON.stringify({
          event: 'feedback/received',
          data: {
            id: feedbackId,
            content,
            source,
            timestamp: new Date().toISOString(),
          },
        }),
        headers: {
          'content-type': 'application/json',
          'source': source,
        },
      },
    ],
  });

  console.log(`Sent feedback event for ${feedbackId}`);
}

export default kafka;
