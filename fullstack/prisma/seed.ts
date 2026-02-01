import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database...');

  // Create test feedback
  const feedback1 = await prisma.feedbackItem.create({
    data: {
      id: 'test-feedback-1',
      content: 'Test feedback 1 - Add dark mode support',
      source: 'test',
      status: 'pending',
      classification: 'feature',
      severity: 'medium',
    },
  });

  const feedback2 = await prisma.feedbackItem.create({
    data: {
      id: 'test-feedback-2',
      content: 'Test feedback 2 - Fix performance bug with large lists',
      source: 'slack',
      status: 'pending',
      classification: 'bug',
      severity: 'high',
    },
  });

  // Create test issues (drafts) - Note: Issue has required feedbackId
  const issue1 = await prisma.issue.create({
    data: {
      id: 'test-issue-1',
      feedbackId: feedback1.id,
      title: 'Add dark mode support',
      body: '## Summary\nUsers want dark mode for better accessibility.\n\n## Details\nWhen using the app at night, the bright interface causes eye strain.\n\n## Proposed Solution\nAdd a toggle in settings to switch between light and dark themes.',
      status: 'draft',
      classification: 'feature',
      severity: 'medium',
      labels: ['enhancement', 'ui'],
      affectedComponents: ['settings', 'theme'],
      acceptanceCriteria: [
        'Dark mode toggle in settings',
        'Persists theme preference',
        'Works on all pages',
      ],
    },
  });

  const issue2 = await prisma.issue.create({
    data: {
      id: 'test-issue-2',
      feedbackId: feedback2.id,
      title: 'Fix performance bug with large lists',
      body: '## Summary\nThe list view becomes very slow when there are more than 100 items.\n\n## Steps to Reproduce\n1. Add 150 items to the system\n2. Navigate to the list view\n3. Observe 5+ second load times\n\n## Expected Behavior\nList should load in under 1 second.',
      status: 'draft',
      classification: 'bug',
      severity: 'high',
      labels: ['bug', 'performance'],
      affectedComponents: ['list-view', 'data-fetching'],
      reproductionSteps: [
        'Add 150+ items',
        'Navigate to list view',
        'Observe slow load time',
      ],
    },
  });

  console.log('Seeded 2 feedback items and 2 draft issues');
  console.log('Feedback IDs:', feedback1.id, feedback2.id);
  console.log('Issue IDs:', issue1.id, issue2.id);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
