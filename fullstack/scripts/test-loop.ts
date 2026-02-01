#!/usr/bin/env tsx
/**
 * Integration Test Script for IterateSwarm
 *
 * Tests the full flow:
 * 1. Simulates Discord webhook POST
 * 2. Verifies feedback is saved to database
 * 3. Polls for issue creation (simulating AI callback)
 *
 * Usage: pnpm test:loop
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const WEB_APP_URL = process.env.WEB_APP_URL || 'http://localhost:3000';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'internal-api-key-change-in-production';
const POLL_INTERVAL_MS = 2000;
const MAX_WAIT_SECONDS = 30;

interface FeedbackResponse {
  success: boolean;
  feedbackId: string;
  message: string;
}

interface SaveIssueRequest {
  feedbackId: string;
  content: string;
  title: string;
  body: string;
  classification: string;
  severity: string;
  reasoning: string;
  confidence: number;
  reproductionSteps: string[];
  affectedComponents: string[];
  acceptanceCriteria: string[];
  suggestedLabels: string[];
}

async function simulateDiscordWebhook(content: string): Promise<FeedbackResponse> {
  console.log(`\n📨 Simulating Discord webhook with content: "${content}"`);

  const response = await fetch(`${WEB_APP_URL}/api/webhooks/discord`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      author: { username: 'testuser' },
      channel_id: '12345',
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(`Webhook failed: ${JSON.stringify(data)}`);
  }

  console.log(`✅ Feedback queued with ID: ${data.feedbackId}`);
  return data;
}

async function simulateAICallback(request: SaveIssueRequest): Promise<{ success: boolean; issueId: string }> {
  console.log(`\n🤖 Simulating AI callback for feedback: ${request.feedbackId}`);

  const response = await fetch(`${WEB_APP_URL}/api/internal/save-issue`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${INTERNAL_API_KEY}`,
    },
    body: JSON.stringify(request),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(`AI callback failed: ${JSON.stringify(data)}`);
  }

  console.log(`✅ Issue created with ID: ${data.issueId}`);
  return data;
}

async function pollForIssue(feedbackId: string): Promise<boolean> {
  console.log(`\n🔍 Polling for issue creation (max ${MAX_WAIT_SECONDS}s)...`);

  const startTime = Date.now();

  while (Date.now() - startTime < MAX_WAIT_SECONDS * 1000) {
    const issue = await prisma.issue.findUnique({
      where: { feedbackId },
    });

    if (issue) {
      console.log(`✅ Issue found: ${issue.id}`);
      console.log(`   Title: ${issue.title}`);
      console.log(`   Status: ${issue.status}`);
      console.log(`   Classification: ${issue.classification}`);
      return true;
    }

    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  console.log(`❌ Timeout waiting for issue`);
  return false;
}

async function verifyDatabaseState(feedbackId: string): Promise<void> {
  console.log(`\n📊 Verifying database state for feedback: ${feedbackId}`);

  const feedback = await prisma.feedbackItem.findUnique({
    where: { id: feedbackId },
  });

  if (!feedback) {
    throw new Error('Feedback not found in database');
  }

  console.log(`✅ Feedback found:`);
  console.log(`   Content: ${feedback.content.substring(0, 50)}...`);
  console.log(`   Status: ${feedback.status}`);
  console.log(`   Source: ${feedback.source}`);
  console.log(`   Created: ${feedback.createdAt}`);

  const issue = await prisma.issue.findUnique({
    where: { feedbackId },
  });

  if (issue) {
    console.log(`✅ Issue linked:`);
    console.log(`   Title: ${issue.title}`);
    console.log(`   Status: ${issue.status}`);
    console.log(`   Classification: ${issue.classification}`);
    console.log(`   Severity: ${issue.severity}`);
  }
}

async function cleanupTestData(feedbackId: string): Promise<void> {
  console.log(`\n🧹 Cleaning up test data...`);

  await prisma.issue.deleteMany({
    where: { feedbackId },
  }).catch(() => {});

  await prisma.feedbackItem.delete({
    where: { id: feedbackId },
  }).catch(() => {});

  console.log(`✅ Cleanup complete`);
}

async function main() {
  console.log('='.repeat(60));
  console.log('  IterateSwarm Integration Test');
  console.log('='.repeat(60));
  console.log(`\n🌐 Web App URL: ${WEB_APP_URL}`);
  console.log(`⏳ Poll interval: ${POLL_INTERVAL_MS}ms`);
  console.log(`⏰ Max wait time: ${MAX_WAIT_SECONDS}s`);

  try {
    // Generate unique test content
    const testContent = `Test feedback ${Date.now()}: The login button is broken on mobile Safari`;
    const feedbackId = crypto.randomUUID();

    // Step 1: Simulate Discord webhook
    console.log('\n📝 Step 1: Simulating Discord webhook...');
    const webhookResult = await simulateDiscordWebhook(testContent);

    // Step 2: Verify feedback in database
    console.log('\n📝 Step 2: Verifying feedback in database...');
    await new Promise(resolve => setTimeout(resolve, 1000)); // Small delay for DB write
    const feedback = await prisma.feedbackItem.findUnique({
      where: { id: webhookResult.feedbackId },
    });

    if (!feedback) {
      throw new Error('Feedback not found after webhook');
    }
    console.log('✅ Feedback saved to database');

    // Step 3: Simulate AI callback (this is what the AI service would do)
    console.log('\n📝 Step 3: Simulating AI callback...');
    const aiRequest: SaveIssueRequest = {
      feedbackId: webhookResult.feedbackId,
      content: testContent,
      title: 'Fix login button on mobile Safari',
      body: `## Description\nThe login button is not responsive on mobile Safari browser.\n\n## Source\nFeedback from Discord user\n\n## Steps to Reproduce\n1. Open the app on iOS Safari\n2. Navigate to login page\n3. Tap the login button\n4. Button does not respond`,
      classification: 'bug',
      severity: 'high',
      reasoning: 'This is a critical bug affecting user ability to login on mobile devices',
      confidence: 0.95,
      reproductionSteps: [
        'Open app on iOS Safari',
        'Navigate to login page',
        'Tap the login button',
      ],
      affectedComponents: ['frontend', 'auth'],
      acceptanceCriteria: [
        'Login button responds to touch on mobile Safari',
        'User can successfully log in',
      ],
      suggestedLabels: ['bug', 'high', 'mobile', 'frontend'],
    };

    const callbackResult = await simulateAICallback(aiRequest);

    // Step 4: Verify issue was created
    console.log('\n📝 Step 4: Verifying issue creation...');
    const issueFound = await pollForIssue(webhookResult.feedbackId);

    if (!issueFound) {
      throw new Error('Issue was not created');
    }

    // Step 5: Final database verification
    console.log('\n📝 Step 5: Final database verification...');
    await verifyDatabaseState(webhookResult.feedbackId);

    // Cleanup
    console.log('\n📝 Step 6: Cleanup...');
    await cleanupTestData(webhookResult.feedbackId);

    console.log('\n' + '='.repeat(60));
    console.log('  ✅ ALL TESTS PASSED');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('\n' + '='.repeat(60));
    console.log('  ❌ TEST FAILED');
    console.log('='.repeat(60));
    console.error(error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
