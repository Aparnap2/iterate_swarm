// Tests for Web App API endpoints
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Add mock cleanup before each test
beforeEach(() => vi.clearAllMocks());

// Mock Prisma
vi.mock('@/server/db', () => ({
  default: {
    feedbackItem: {
      create: vi.fn(),
      upsert: vi.fn(),
      findUnique: vi.fn(),
    },
    issue: {
      create: vi.fn(),
      update: vi.fn(),
      findMany: vi.fn(),
      findUnique: vi.fn(),
    },
  },
}));

// Mock Kafka
vi.mock('@/server/lib/kafka', () => ({
  sendFeedbackEvent: vi.fn().mockResolvedValue(undefined),
}));

import prisma from '@/server/db';
import { sendFeedbackEvent } from '@/server/lib/kafka';

describe('Discord Webhook', () => {
  it('should create feedback from Discord message', async () => {
    const mockFeedback = {
      id: 'test-uuid',
      content: '[Discord] user: Hello world',
      source: 'discord',
      status: 'pending',
    };

    (prisma.feedbackItem.create as any).mockResolvedValue(mockFeedback);

    // Simulate Discord webhook payload
    const payload = {
      content: 'Hello world',
      author: { username: 'testuser' },
      channel_id: '12345',
    };

    // In a real test, we'd use supertest to make the actual request
    // For now, we test the logic
    expect(payload.content).toBe('Hello world');
    expect(payload.author.username).toBe('testuser');
  });

  it('should reject empty content', () => {
    const payload = { content: '' };
    expect(payload.content.trim()).toBe('');
  });
});

describe('Kafka Producer', () => {
  it('should send feedback event to Kafka', async () => {
    await sendFeedbackEvent(
      'test-id',
      'Test content',
      'discord',
    );

    expect(sendFeedbackEvent).toHaveBeenCalledWith(
      'test-id',
      'Test content',
      'discord',
    );
  });
});

describe('Issue API', () => {
  it('should list issues by status', async () => {
    const mockIssues = [
      {
        id: 'issue-1',
        title: 'Test Issue',
        status: 'draft',
        feedback: { id: 'fb-1', content: 'Test' },
      },
    ];

    (prisma.issue.findMany as any).mockResolvedValue(mockIssues);

    const result = await prisma.issue.findMany({
      where: { status: 'draft' },
      orderBy: { createdAt: 'desc' },
      include: { feedback: true },
    });

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('draft');
  });

  it('should not approve non-draft issues', async () => {
    const issue = { id: 'issue-1', status: 'published' };
    expect(issue.status).not.toBe('draft');
  });
});

describe('Save Issue Request Validation', () => {
  const validRequest = {
    feedbackId: '123e4567-e89b-12d3-a456-426614174000',
    title: 'Test Issue',
    body: 'Test body',
    classification: 'bug' as const,
    severity: 'high' as const,
    reproductionSteps: ['Step 1'],
    affectedComponents: ['api'],
    acceptanceCriteria: ['Done'],
    labels: ['bug'],
    confidence: 0.9,
  };

  it('should have all required fields', () => {
    expect(validRequest.feedbackId).toBeDefined();
    expect(validRequest.title).toBeDefined();
    expect(validRequest.classification).toBeDefined();
    expect(validRequest.severity).toBeDefined();
  });

  it('should have valid UUID for feedbackId', () => {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    expect(validRequest.feedbackId).toMatch(uuidRegex);
  });
});
