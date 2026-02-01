import { test, expect } from '@playwright/test';

test.describe('Triage Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the issues page before each test
    await page.goto('/issues');
    // Wait for page to be fully loaded
    await page.waitForLoadState('domcontentloaded');
    // Wait for either the draft-count indicator OR the empty-state element using Promise.race
    await Promise.race([
      page.waitForSelector('text=/\\d+ draft issue/', { timeout: 10000 }),
      page.waitForSelector('text=/No draft issues to review/i', { timeout: 10000 }),
    ]);
  });

  test('should navigate to /issues and load successfully', async ({ page }) => {
    // Check that the page loads successfully
    await expect(page).toHaveURL(/.*issues/);

    // Verify the page title or header is visible
    await expect(page.getByRole('heading', { name: /Issue Triage/i })).toBeVisible();
  });

  test('should display the issues list or empty state', async ({ page }) => {
    // The page should show either the issue list or an empty state message
    // Check for Draft Issues text OR empty state text using count() instead of isVisible()
    const hasDraftIssues = (await page.getByText('Draft Issues').count()) > 0;

    const hasEmptyState = (await page.getByText(/No draft issues to review/i).count()) > 0;

    // At least one should be present
    expect(hasDraftIssues || hasEmptyState).toBe(true);
  });

  test('should show header with issue count', async ({ page }) => {
    // Check header exists with proper styling
    const header = page.locator('header').first();
    await expect(header).toBeVisible();

    // Check for issue count text
    const issueCount = page.locator('text=/\\d+ draft issue/');
    await expect(issueCount.first()).toBeVisible();
  });

  test('should have Approve button visible when issues exist', async ({ page }) => {
    // Check if there are issues
    const hasDraftIssues = (await page.getByText('Draft Issues').count()) > 0;

    if (hasDraftIssues) {
      // Issues exist - verify buttons are present using getByText
      const approveCount = await page.getByText('Approve & Publish').count();
      const rejectCount = await page.getByText('Reject').count();
      expect(approveCount).toBeGreaterThan(0);
      expect(rejectCount).toBeGreaterThan(0);
    } else {
      // No issues - verify empty state is shown
      await expect(
        page.getByText(/No draft issues/i)
      ).toBeVisible();
    }
  });

  test('should have Reject button visible when issues exist', async ({ page }) => {
    const hasDraftIssues = (await page.getByText('Draft Issues').count()) > 0;

    if (hasDraftIssues) {
      const rejectCount = await page.getByText('Reject').count();
      expect(rejectCount).toBeGreaterThan(0);
    } else {
      // Empty state - no reject button needed
      await expect(
        page.getByText(/No draft issues/i)
      ).toBeVisible();
    }
  });

  test('should have Back navigation link', async ({ page }) => {
    // Check for Back link in header
    const backLink = page.locator('a:has-text("Back")').first();
    await expect(backLink).toBeVisible();

    // Verify it points to home page
    await expect(backLink).toHaveAttribute('href', '/');
  });
});
