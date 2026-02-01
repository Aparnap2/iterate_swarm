// Discord Webhook Endpoint
// Receives feedback from Discord and queues for processing

import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import prisma from '@/server/db';
import { sendFeedbackEvent } from '@/server/lib/kafka';
import { v4 as uuidv4 } from 'uuid';

const DISCORD_WEBHOOK_SECRET = process.env.DISCORD_WEBHOOK_SECRET;

function verifyDiscordSignature(request: NextRequest, body: string): boolean {
  if (!DISCORD_WEBHOOK_SECRET) {
    console.error('DISCORD_WEBHOOK_SECRET not configured');
    return false;
  }

  const signature = request.headers.get('x-signature-ed25519');
  const timestamp = request.headers.get('x-signature-timestamp');

  if (!signature || !timestamp) {
    return false;
  }

  const message = timestamp + body;
  const expectedSignature = crypto
    .createHmac('sha256', DISCORD_WEBHOOK_SECRET)
    .update(message)
    .digest('hex');

  try {
    return crypto.timingSafeEqual(
      Buffer.from(signature, 'hex'),
      Buffer.from(expectedSignature, 'hex')
    );
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bodyString = JSON.stringify(body);

    // Verify Discord signature
    if (!verifyDiscordSignature(request, bodyString)) {
      return NextResponse.json(
        { error: 'Invalid signature' },
        { status: 401 }
      );
    }

    // Extract content from Discord message
    const content = body.content?.trim() || '';
    const author = body.author?.username || 'unknown';
    const channelId = body.channel_id || 'unknown';

    if (!content) {
      return NextResponse.json(
        { error: 'No content in message' },
        { status: 400 }
      );
    }

    // Generate feedback ID
    const feedbackId = uuidv4();
    const formattedContent = `[Discord] ${author}: ${content}`;

    // Save to database
    const feedback = await prisma.feedbackItem.create({
      data: {
        id: feedbackId,
        content: formattedContent,
        source: 'discord',
        status: 'pending',
      },
    });

    // Send to Kafka for AI processing
    await sendFeedbackEvent(
      feedbackId,
      formattedContent,
      'discord',
    );

    return NextResponse.json({
      success: true,
      feedbackId: feedback.id,
      message: 'Feedback queued for processing',
    }, { status: 202 });
  } catch (error) {
    console.error('Discord webhook error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
