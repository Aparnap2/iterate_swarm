// Issues API - List all issues
import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/server/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status') || 'draft';

    const issues = await prisma.issue.findMany({
      where: { status },
      orderBy: { createdAt: 'desc' },
      include: {
        feedback: true,
      },
    });

    return NextResponse.json({
      issues,
      total: issues.length,
    });
  } catch (error) {
    console.error('Error listing issues:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
