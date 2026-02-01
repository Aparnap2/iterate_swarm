import { Suspense } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getDashboardStats, getRecentActivity } from '@/app/actions/issues';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import { ErrorBoundary } from '@/components/error-boundary';

export const dynamic = 'force-dynamic';

function StatsLoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-28 bg-stone-100 rounded-xl animate-pulse" />
      ))}
    </div>
  );
}

function ActivityLoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {[1, 2].map((i) => (
        <Card key={i}>
          <CardHeader>
            <div className="h-6 w-32 bg-stone-100 rounded animate-pulse" />
          </CardHeader>
          <CardContent className="space-y-3">
            {[1, 2, 3].map((j) => (
              <div key={j} className="h-16 bg-stone-100 rounded-lg animate-pulse" />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ServiceUnavailable() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="py-12 text-center">
          <h2 className="text-xl font-semibold text-amber-900 mb-2">
            Service Temporarily Unavailable
          </h2>
          <p className="text-amber-700">
            Unable to connect to the database. Please check your connection and try again.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default async function DashboardPage() {
  return (
    <ErrorBoundary
      fallback={
        <div className="min-h-screen bg-stone-50 p-8">
          <div className="max-w-6xl mx-auto space-y-8">
            <ServiceUnavailable />
          </div>
        </div>
      }
    >
      <Suspense fallback={<DashboardLoading />}>
        <DashboardContent />
      </Suspense>
    </ErrorBoundary>
  );
}

async function DashboardContent() {
  const [stats, activity] = await Promise.all([
    getDashboardStats(),
    getRecentActivity(),
  ]);

  return (
    <div className="min-h-screen bg-stone-50 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-stone-900">IterateSwarm</h1>
            <p className="text-stone-600 mt-1">
              AI-Powered Feedback Triage & Issue Management
            </p>
          </div>
          <Link
            href="/issues"
            className="bg-stone-900 text-white px-4 py-2 rounded-lg hover:bg-stone-800 transition-colors"
          >
            Review Issues
          </Link>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            title="Pending Feedback"
            value={stats.pendingFeedback}
            icon="📥"
            color="blue"
          />
          <StatCard
            title="Draft Issues"
            value={stats.draftIssues}
            icon="📝"
            color="amber"
            href="/issues"
          />
          <StatCard
            title="Published"
            value={stats.publishedIssues}
            icon="✅"
            color="green"
          />
          <StatCard
            title="Rejected"
            value={stats.rejectedIssues}
            icon="❌"
            color="red"
          />
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Recent Feedback */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              {activity.feedback.length === 0 ? (
                <p className="text-stone-500 text-sm">No feedback yet</p>
              ) : (
                <div className="space-y-3">
                  {activity.feedback.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-start justify-between gap-2 p-2 rounded-lg bg-stone-100"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-stone-900 truncate">
                          {item.content}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="secondary" className="text-xs">
                            {item.source}
                          </Badge>
                          <Badge
                            variant={
                              item.status === 'completed'
                                ? 'default'
                                : 'outline'
                            }
                            className="text-xs"
                          >
                            {item.status}
                          </Badge>
                        </div>
                      </div>
                      <span className="text-xs text-stone-500 whitespace-nowrap">
                        {formatDistanceToNow(new Date(item.createdAt), {
                          addSuffix: true,
                        })}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Published Issues */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Published on GitHub</CardTitle>
            </CardHeader>
            <CardContent>
              {activity.publishedIssues.length === 0 ? (
                <p className="text-stone-500 text-sm">No published issues yet</p>
              ) : (
                <div className="space-y-3">
                  {activity.publishedIssues.map((issue) => (
                    <div
                      key={issue.id}
                      className="flex items-start justify-between gap-2 p-2 rounded-lg bg-stone-100"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-stone-900 truncate font-medium">
                          {issue.title}
                        </p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {issue.labels.slice(0, 3).map((label, idx) => (
                            <Badge
                              key={`${label}-${idx}`}
                              variant="secondary"
                              className="text-xs"
                            >
                              {label}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      {issue.githubUrl && (
                        <a
                          href={issue.githubUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                        >
                          View →
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DashboardLoading() {
  return (
    <div className="min-h-screen bg-stone-50 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-9 w-48 bg-stone-200 rounded animate-pulse" />
            <div className="h-5 w-72 bg-stone-100 rounded animate-pulse" />
          </div>
          <div className="h-10 w-32 bg-stone-200 rounded animate-pulse" />
        </div>

        <StatsLoadingSkeleton />
        <ActivityLoadingSkeleton />
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  color,
  href,
}: {
  title: string;
  value: number;
  icon: string;
  color: 'blue' | 'amber' | 'green' | 'red';
  href?: string;
}) {
  const colorClasses = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    green: 'bg-green-50 border-green-200 text-green-700',
    red: 'bg-red-50 border-red-200 text-red-700',
  };

  const content = (
    <Card className={`${colorClasses[color]} border-2`}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium opacity-80">{title}</p>
            <p className="text-3xl font-bold mt-1">{value}</p>
          </div>
          <span className="text-4xl">{icon}</span>
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }

  return content;
}
