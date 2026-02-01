import { Suspense } from 'react';
import { getDrafts } from '@/app/actions/issues';
import { IssuesWrapper } from './issues-wrapper';
import { ErrorBoundary } from '@/components/error-boundary';
import { Card, CardContent } from '@/components/ui/card';

export const dynamic = 'force-dynamic';

interface IssuesPageProps {
  searchParams: Promise<{ selected?: string }>;
}

function IssuesLoadingSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <div className="col-span-3">
        <Card className="h-[calc(100vh-180px)]">
          <CardContent className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-stone-100 rounded-lg animate-pulse" />
            ))}
          </CardContent>
        </Card>
      </div>
      <div className="col-span-9">
        <Card className="h-[calc(100vh-180px)]">
          <CardContent className="p-6">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-stone-100 rounded w-1/3" />
              <div className="h-32 bg-stone-100 rounded" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function EmptyIssuesState() {
  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold text-stone-900">Issue Triage</h1>
          <div className="text-sm text-stone-500">0 draft issues</div>
        </div>
      </header>
      <div className="max-w-7xl mx-auto p-6">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-stone-500 mb-4">
              No draft issues to review. Feedback will appear here after AI processing.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default async function IssuesPage({ searchParams }: IssuesPageProps) {
  await searchParams;

  return (
    <ErrorBoundary
      fallback={
        <div className="min-h-screen bg-stone-50 p-8">
          <div className="max-w-7xl mx-auto">
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-red-600 mb-4">
                  Unable to connect to the database. Please check your connection.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      }
    >
      <Suspense fallback={<IssuesLoadingSkeleton />}>
        <IssuesPageContent />
      </Suspense>
    </ErrorBoundary>
  );
}

async function IssuesPageContent() {
  const issues = await getDrafts();

  if (issues.length === 0) {
    return <EmptyIssuesState />;
  }

  return <IssuesWrapper issues={issues} />;
}
