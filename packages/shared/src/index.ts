import { z } from 'zod';

// ========================
// Feedback Types
// ========================

export const FeedbackSourceSchema = z.enum(['discord', 'slack', 'manual']);
export type FeedbackSource = z.infer<typeof FeedbackSourceSchema>;

export const FeedbackStatusSchema = z.enum([
  'pending',
  'processing',
  'completed',
  'ignored',
]);
export type FeedbackStatus = z.infer<typeof FeedbackStatusSchema>;

export const FeedbackItemSchema = z.object({
  id: z.string().uuid(),
  content: z.string().min(1),
  source: FeedbackSourceSchema,
  status: FeedbackStatusSchema.default('pending'),
  classification: z.enum(['bug', 'feature', 'question']).optional(),
  severity: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  createdAt: z.date(),
  processedAt: z.date().optional(),
});
export type FeedbackItem = z.infer<typeof FeedbackItemSchema>;

// ========================
// Issue Types
// ========================

export const IssueStatusSchema = z.enum(['draft', 'approved', 'rejected', 'published']);
export type IssueStatus = z.infer<typeof IssueStatusSchema>;

export const IssueSchema = z.object({
  id: z.string().uuid(),
  feedbackId: z.string().uuid(),
  title: z.string().min(1).max(255),
  body: z.string().min(1),
  status: IssueStatusSchema.default('draft'),
  githubUrl: z.string().url().optional(),
  labels: z.array(z.string()).default([]),
  classification: z.enum(['bug', 'feature', 'question']).optional(),
  severity: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  reproductionSteps: z.array(z.string()).default([]),
  affectedComponents: z.array(z.string()).default([]),
  acceptanceCriteria: z.array(z.string()).default([]),
  createdAt: z.date(),
  updatedAt: z.date(),
});
export type Issue = z.infer<typeof IssueSchema>;

// ========================
// Kafka Event Payloads
// ========================

export const FeedbackReceivedEventSchema = z.object({
  event: z.literal('feedback/received'),
  data: z.object({
    id: z.string().uuid(),
    content: z.string().min(1),
    source: FeedbackSourceSchema,
    timestamp: z.string().datetime(),
  }),
});
export type FeedbackReceivedEvent = z.infer<typeof FeedbackReceivedEventSchema>;

// ========================
// Internal API Payloads
// ========================

export const SaveIssueRequestSchema = z.object({
  feedbackId: z.string().uuid(),
  title: z.string().min(1).max(255),
  body: z.string().min(1),
  classification: z.enum(['bug', 'feature', 'question']),
  severity: z.enum(['low', 'medium', 'high', 'critical']),
  reproductionSteps: z.array(z.string()).default([]),
  affectedComponents: z.array(z.string()).default([]),
  acceptanceCriteria: z.array(z.string()).default([]),
  labels: z.array(z.string()).default([]),
  confidence: z.number().min(0).max(1),
});
export type SaveIssueRequest = z.infer<typeof SaveIssueRequestSchema>;

export const SaveIssueResponseSchema = z.object({
  success: z.boolean(),
  issueId: z.string().uuid().optional(),
  error: z.string().optional(),
});
export type SaveIssueResponse = z.infer<typeof SaveIssueResponseSchema>;

// ========================
// API Response Types
// ========================

export const IssueListResponseSchema = z.object({
  issues: z.array(IssueSchema),
  total: z.number(),
});
export type IssueListResponse = z.infer<typeof IssueListResponseSchema>;

export const ApproveResponseSchema = z.object({
  status: z.literal('published'),
  url: z.string().url(),
  issueId: z.string().uuid(),
});
export type ApproveResponse = z.infer<typeof ApproveResponseSchema>;
