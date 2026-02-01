// Internal API: Save Issue
// Called by AI Service after processing feedback
// Protected by INTERNAL_API_KEY

import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import prisma from '@/server/db';
import { sendFeedbackEvent } from '@/server/lib/kafka';

const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;

export async function POST(request: NextRequest) {
  // Verify API key is configured
  if (!INTERNAL_API_KEY) {
    console.error('INTERNAL_API_KEY not configured');
    return NextResponse.json(
      { success: false, error: 'Server misconfiguration' },
      { status: 500 }
    );
  }

  // Verify API key using constant-time comparison
  const authHeader = request.headers.get('authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return NextResponse.json(
      { success: false, error: 'Unauthorized' },
      { status: 401 }
    );
  }

  const providedKey = authHeader.slice(7);
  const keyBuffer = Buffer.from(INTERNAL_API_KEY);
  const providedBuffer = Buffer.from(providedKey);

  if (keyBuffer.length !== providedBuffer.length || !crypto.timingSafeEqual(keyBuffer, providedBuffer)) {
    return NextResponse.json(
      { success: false, error: 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const body = await request.json();

    // Validate required fields
    if (!body.feedbackId || !body.title || !body.classification || !body.severity) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Upsert feedback item and create issue draft in a single transaction
    const result = await prisma.$transaction(async (tx) => {
      // Upsert feedback item
      const feedback = await tx.feedbackItem.upsert({
        where: { id: body.feedbackId },
        update: {
          status: 'completed',
          classification: body.classification,
          severity: body.severity,
          processedAt: new Date(),
        },
        create: {
          id: body.feedbackId,
          content: body.content || '',
          source: 'unknown',
          status: 'completed',
          classification: body.classification,
          severity: body.severity,
          processedAt: new Date(),
        },
      });

      // Create issue draft
      const issue = await tx.issue.create({
        data: {
          feedbackId: body.feedbackId,
          title: body.title,
          body: body.body,
          classification: body.classification,
          severity: body.severity,
          reproductionSteps: body.reproductionSteps || [],
          affectedComponents: body.affectedComponents || [],
          acceptanceCriteria: body.acceptanceCriteria || [],
          labels: body.labels || [body.classification, body.severity],
          status: 'draft',
        },
      });

      return { feedback, issue };
    });

    return NextResponse.json({
      success: true,
      issueId: result.issue.id,
      feedbackId: result.feedback.id,
    });
  } catch (error) {
    console.error('Error saving issue:', error);
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    );
  }
}
