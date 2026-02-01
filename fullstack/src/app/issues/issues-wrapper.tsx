'use client';

import { useState, useEffect, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { IssuesList, ReviewPanel } from './issue-client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';
import { DraftIssue, approveIssue, rejectIssue } from '@/app/actions/issues';
import { toast } from 'sonner';

interface IssuesWrapperProps {
  issues: DraftIssue[];
}

export function IssuesWrapper({ issues: initialIssues }: IssuesWrapperProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get('selected');
  const [mounted, setMounted] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [issues, setIssues] = useState(initialIssues);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Sync local state when server data changes (e.g., after revalidation)
  useEffect(() => {
    setIssues(initialIssues);
  }, [initialIssues]);

  const selectedIssue = selectedId
    ? issues.find((i) => i.id === selectedId) || (issues.length > 0 ? issues[0] : null)
    : (issues.length > 0 ? issues[0] : null);

  const handleSelect = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('selected', id);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  const handleApprove = async (issueId: string) => {
    const result = await approveIssue(issueId);
    if (result.success) {
      toast.success('Issue approved and published!');
      startTransition(() => {
        setIssues((prev) => prev.filter((i) => i.id !== issueId));
      });
    } else {
      toast.error(result.error || 'Failed to approve issue');
    }
  };

  const handleReject = async (issueId: string) => {
    const result = await rejectIssue(issueId, 'Rejected by reviewer');
    if (result.success) {
      toast.success('Issue rejected');
      startTransition(() => {
        setIssues((prev) => prev.filter((i) => i.id !== issueId));
      });
    } else {
      toast.error(result.error || 'Failed to reject issue');
    }
  };

  // Format date consistently to avoid hydration mismatch
  const formatDate = (date: Date | string) => {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
      month: '2-digit',
      day: '2-digit',
      year: 'numeric',
    });
  };

  if (issues.length === 0) {
    return (
      <div className="min-h-screen bg-stone-50">
        <header className="bg-white border-b border-stone-200 px-6 py-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-sm text-stone-600 hover:text-stone-900"
              >
                ← Back
              </Link>
              <h1 className="text-xl font-bold text-stone-900">Issue Triage</h1>
            </div>
            <div className="text-sm text-stone-500">
              0 draft issues to review
            </div>
          </div>
        </header>
        <div className="max-w-7xl mx-auto p-6">
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-stone-500 mb-4">
                No draft issues to review. Feedback will appear here after AI
                processing.
              </p>
              <Link href="/" className="text-stone-900 hover:underline">
                Go to Dashboard
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-sm text-stone-600 hover:text-stone-900"
            >
              ← Back
            </Link>
            <h1 className="text-xl font-bold text-stone-900">Issue Triage</h1>
          </div>
          <div className="text-sm text-stone-500">
            {issues.length} draft issue{issues.length !== 1 ? 's' : ''} to review
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-3">
            <Card className="h-[calc(100vh-180px)]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Draft Issues
                </CardTitle>
              </CardHeader>
              <IssuesList
                issues={issues}
                selectedId={selectedIssue?.id}
                onSelect={handleSelect}
              />
            </Card>
          </div>

          <div className="col-span-9">
            {selectedIssue ? (
              <Card className="h-[calc(100vh-180px)] overflow-hidden flex flex-col border border-stone-200 shadow-sm bg-white">
                <CardHeader className="border-b border-stone-200 py-4 shrink-0 bg-stone-50">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold text-stone-800">Review Issue</CardTitle>
                    <span className="text-xs text-stone-500">
                      Created {mounted ? formatDate(selectedIssue.createdAt) : ''}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-hidden">
                  <ReviewPanel
                    issue={selectedIssue}
                    onApprove={() => handleApprove(selectedIssue.id)}
                    onReject={() => handleReject(selectedIssue.id)}
                  />
                </CardContent>
              </Card>
            ) : (
              <Card className="h-[calc(100vh-180px)] flex items-center justify-center border border-stone-200 shadow-sm bg-white">
                <p className="text-stone-500">Select an issue to review</p>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
