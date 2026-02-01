// Slack Webhook Endpoint
// Receives feedback from Slack and queues for processing

import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import prisma from '@/server/db';
import { sendFeedbackEvent } from '@/server/lib/kafka';
import { v4 as uuidv4 } from 'uuid';

const SLACK_SIGNING_SECRET = process.env.SLACK_SIGNING_SECRET;

function verifySlackSignature(request: NextRequest, body: string): boolean {
  if (!SLACK_SIGNING_SECRET) {
    console.error('SLACK_SIGNING_SECRET not configured');
    return false;
  }

  const signature = request.headers.get('x-slack-signature');
  const timestamp = request.headers.get('x-slack-request-timestamp');

  if (!signature || !timestamp) {
    return false;
  }

  // Reject requests older than 5 minutes to prevent replay attacks
  const now = Math.floor(Date.now() / 1000);
  const requestTime = parseInt(timestamp, 10);
  if (Math.abs(now - requestTime) > 300) {
    return false;
  }

  const sigBasestring = `v0:${timestamp}:${body}`;
  const mySignature = 'v0=' + crypto
    .createHmac('sha256', SLACK_SIGNING_SECRET)
    .update(sigBasestring)
    .digest('hex');

  try {
    return crypto.timingSafeEqual(
      Buffer.from(mySignature),
      Buffer.from(signature)
    );
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bodyString = JSON.stringify(body);

    // Handle Slack URL verification challenge
    if (body.type === 'url_verification') {
      return NextResponse.json({ challenge: body.challenge });
    }

    // Verify Slack signature
    if (!verifySlackSignature(request, bodyString)) {
      return NextResponse.json(
        { error: 'Invalid signature' },
        { status: 401 }
      );
    }

    // Extract content from Slack message
    const event = body.event;
    const content = event?.text?.trim() || '';
    const user = event?.user || 'unknown';

    if (!content) {
      return NextResponse.json(
        { error: 'No content in message' },
        { status: 400 }
      );
    }

    // Generate feedback ID
    const feedbackId = uuidv4();
    const formattedContent = `[Slack] <@${user}>: ${content}`;

    // Save to database
    const feedback = await prisma.feedbackItem.create({
      data: {
        id: feedbackId,
        content: formattedContent,
        source: 'slack',
        status: 'pending',
      },
    });

    // Send to Kafka for AI processing
    await sendFeedbackEvent(
      feedbackId,
      formattedContent,
      'slack',
    );

    return NextResponse.json({
      success: true,
      feedbackId: feedback.id,
      message: 'Feedback queued for processing',
    }, { status: 202 });
  } catch (error) {
    console.error('Slack webhook error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
