import { test, expect } from '@playwright/test';

test.describe('Debug Triage', () => {
  test('debug hasDraftIssues', async ({ page }) => {
    await page.goto('/issues');
    
    // Wait for navigation to complete
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for the issue count to appear (indicates React has rendered)
    await page.waitForSelector('text=/\\d+ draft issue/', { timeout: 10000 });
    
    // Small additional wait for React to settle
    await page.waitForTimeout(1000);
    
    // Check if there are issues
    const draftIssuesCount = await page.getByText('Draft Issues').count();
    const hasDraftIssues = draftIssuesCount > 0;
    
    console.log('Draft Issues count:', draftIssuesCount);
    console.log('hasDraftIssues:', hasDraftIssues);
    
    // Check buttons
    const approveCount = await page.getByText('Approve & Publish').count();
    console.log('Approve count:', approveCount);
    
    const rejectCount = await page.getByText('Reject').count();
    console.log('Reject count:', rejectCount);
    
    // This should pass
    expect(hasDraftIssues).toBe(true);
    expect(approveCount).toBeGreaterThan(0);
    expect(rejectCount).toBeGreaterThan(0);
  });
});
