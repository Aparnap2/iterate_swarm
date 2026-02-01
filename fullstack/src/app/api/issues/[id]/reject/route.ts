// Reject Issue
import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/server/db';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const reason = body.reason;

    const issue = await prisma.issue.findUnique({
      where: { id },
    });

    if (!issue) {
      return NextResponse.json(
        { error: 'Issue not found' },
        { status: 404 }
      );
    }

    if (issue.status === 'published') {
      return NextResponse.json(
        { error: 'Cannot reject a published issue' },
        { status: 400 }
      );
    }

    // Update issue status atomically only if not already published
    const updated = await prisma.issue.updateMany({
      where: {
        id,
        status: { not: 'published' },
      },
      data: {
        status: 'rejected',
        body: reason ? `**Rejected**: ${reason}\n\n---\n\n${issue.body}` : issue.body,
      },
    });

    if (updated.count === 0) {
      return NextResponse.json(
        { error: 'Issue was already processed or published' },
        { status: 409 }
      );
    }

    return NextResponse.json({
      status: 'rejected',
      issueId: id,
    });
  } catch (error) {
    console.error('Error rejecting issue:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
