'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DraftIssue, approveIssue, updateIssue, rejectIssue } from '@/app/actions/issues';
import { Badge } from '../../../components/ui/badge';
import { Button } from '../../../components/ui/button';
import { Textarea } from '../../../components/ui/textarea';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Alert, AlertDescription } from '../../../components/ui/alert';
import { Toaster } from 'sonner';
import { toast } from 'sonner';
import { Loader2, Check, X, ExternalLink, AlertTriangle } from 'lucide-react';

interface IssuesListProps {
  issues: DraftIssue[];
  selectedId?: string;
  onSelect: (id: string) => void;
}

export function IssuesList({ issues, selectedId, onSelect }: IssuesListProps) {
  if (issues.length === 0) {
    return (
      <div className="p-4 text-center text-stone-500">
        No draft issues to review
      </div>
    );
  }

  return (
    <ScrollArea className="h-[calc(100vh-200px)]">
      <div className="space-y-2 p-4">
        {issues.map((issue) => (
          <button
            key={issue.id}
            onClick={() => onSelect(issue.id)}
            className={`w-full text-left p-3 rounded-lg border transition-colors ${
              selectedId === issue.id
                ? 'bg-stone-900 text-white border-stone-900'
                : 'bg-white hover:bg-stone-50 border-stone-200'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{issue.title}</p>
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  <Badge
                    variant={issue.classification === 'bug' ? 'destructive' : 'secondary'}
                    className={`text-xs ${
                      selectedId === issue.id
                        ? 'bg-white/20 text-white border-white/30'
                        : ''
                    }`}
                  >
                    {issue.classification}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      selectedId === issue.id
                        ? 'border-white/30 text-white/80'
                        : ''
                    }`}
                  >
                    {issue.severity}
                  </Badge>
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </ScrollArea>
  );
}

interface ReviewPanelProps {
  issue: DraftIssue;
  onApprove: () => void;
  onReject: () => void;
}

export function ReviewPanel({ issue, onApprove, onReject }: ReviewPanelProps) {
  const [title, setTitle] = useState(issue.title);
  const [body, setBody] = useState(issue.body);
  const [isApproving, setIsApproving] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);

  // Sync state when issue prop changes
  useEffect(() => {
    setTitle(issue.title);
    setBody(issue.body);
  }, [issue.id, issue.title, issue.body]);

  const handleUpdate = async () => {
    setIsUpdating(true);
    try {
      const result = await updateIssue(issue.id, { title, body });
      if (result.success) {
        toast.success('Issue updated');
        onApprove(); // Use callback instead of router.refresh()
      } else {
        toast.error(result.error || 'Failed to update');
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      const result = await approveIssue(issue.id);
      if (result.success) {
        toast.success('Issue published to GitHub!', {
          description: result.url,
          action: result.url
            ? {
                label: 'View',
                onClick: () => window.open(result.url!, '_blank'),
              }
            : undefined,
        });
        onApprove();
      } else {
        toast.error(result.error || 'Failed to publish');
      }
    } catch (error) {
      toast.error('An error occurred while publishing');
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast.error('Please provide a reason for rejection');
      return;
    }
    setIsRejecting(true);
    try {
      const result = await rejectIssue(issue.id, rejectReason);
      if (result.success) {
        toast.success('Issue rejected');
        setShowRejectConfirm(false);
        setRejectReason('');
        onReject();
      } else {
        toast.error(result.error || 'Failed to reject');
      }
    } catch (error) {
      toast.error('An error occurred while rejecting');
    } finally {
      setIsRejecting(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Toaster position="top-right" />

      {/* Original Feedback */}
      <div className="px-6 pt-4 pb-2">
        <Alert className="bg-amber-50 border-amber-200">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
          <AlertDescription className="text-amber-900">
            <span className="font-medium">Original Feedback:</span>{' '}
            {issue.feedback.content}
          </AlertDescription>
        </Alert>
      </div>

      {/* Edit Form */}
      <div className="flex-1 grid grid-cols-2 gap-4 min-h-0 px-6 py-4">
        {/* Edit Mode */}
        <Card className="flex flex-col overflow-hidden border border-stone-200">
          <CardHeader className="py-3 border-b bg-stone-50 shrink-0">
            <CardTitle className="text-sm font-medium text-stone-700">Edit (Markdown)</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="p-4 space-y-4">
                <div>
                  <label className="text-xs font-semibold text-stone-600 mb-2 block">
                    Title
                  </label>
                  <Textarea
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="resize-none font-medium bg-white border-stone-300 text-stone-900 placeholder:text-stone-400"
                    rows={2}
                  />
                </div>
                <div className="flex-1">
                  <label className="text-xs font-semibold text-stone-600 mb-2 block">
                    Body
                  </label>
                  <Textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    className="resize-none font-mono text-sm bg-white border-stone-300 text-stone-900 placeholder:text-stone-400 min-h-[300px]"
                    rows={15}
                  />
                </div>
                <Button
                  onClick={handleUpdate}
                  disabled={isUpdating || (title === issue.title && body === issue.body)}
                  variant="outline"
                  size="sm"
                  className="w-full mt-4"
                >
                  {isUpdating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </Button>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Preview Mode */}
        <Card className="flex flex-col overflow-hidden border border-stone-200">
          <CardHeader className="py-3 border-b bg-stone-50 shrink-0">
            <CardTitle className="text-sm font-medium text-stone-700">Preview</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="p-4 prose prose-sm max-w-none text-stone-800">
                <h1 className="text-xl font-bold text-stone-900 mb-4">{title}</h1>
                <div className="text-stone-700">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {body}
                  </ReactMarkdown>
                </div>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-4 px-6 py-4 border-t bg-white shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{issue.classification}</Badge>
          <Badge variant="outline">{issue.severity}</Badge>
          <Badge variant="outline">
            {issue.labels.length} label{issue.labels.length !== 1 ? 's' : ''}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setShowRejectConfirm(true)}
            disabled={isApproving || isRejecting}
          >
            <X className="mr-2 h-4 w-4" />
            Reject
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isApproving || isRejecting}
            className="bg-green-600 hover:bg-green-700"
          >
            {isApproving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Publishing...
              </>
            ) : (
              <>
                <Check className="mr-2 h-4 w-4" />
                Approve & Publish
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Reject Confirmation Dialog */}
      {showRejectConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Reject Issue</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-stone-600">
                Please provide a reason for rejecting this issue. This will be
                added to the issue body.
              </p>
              <Textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejection..."
                rows={4}
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowRejectConfirm(false);
                    setRejectReason('');
                  }}
                  disabled={isRejecting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleReject}
                  disabled={isRejecting || !rejectReason.trim()}
                >
                  {isRejecting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Rejecting...
                    </>
                  ) : (
                    'Reject'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
