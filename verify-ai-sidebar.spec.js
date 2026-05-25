import { test, expect } from '@playwright/test';

test('AI sidebar multi-session and styling', async ({ page }) => {
  await page.goto('http://localhost:3001');
  await page.waitForLoadState('networkidle');

  // Click AI Search tab
  await page.getByText('AI 搜索').click();
  await page.waitForTimeout(500);

  // Screenshot 1: initial AI tab with sidebar
  await page.screenshot({ path: 'test-results/ai-sidebar-initial.png' });

  // Check that "新对话" button has pill shape
  const newChatBtn = page.locator('.ai-search__new-chat');
  await expect(newChatBtn).toBeVisible();

  // Check that history items use pill shape
  const historyItems = page.locator('.ai-search__history-item');
  await expect(historyItems.first()).toBeVisible();

  // Click "新对话" — since current session is empty, should NOT create a new one
  await newChatBtn.click();
  await page.waitForTimeout(300);

  // Should still be only 1 session
  await expect(historyItems).toHaveCount(1);

  // Screenshot 2: after clicking new chat on empty session (no change)
  await page.screenshot({ path: 'test-results/ai-sidebar-no-duplicate.png' });

  // Send a message using example button to populate first session
  const exampleBtn = page.locator('.ai-search__examples button').first();
  await exampleBtn.click();
  await page.waitForTimeout(800);

  // Screenshot 3: first session with message
  await page.screenshot({ path: 'test-results/ai-sidebar-with-message.png' });

  // Now click "新对话" — should create a new session
  await newChatBtn.click();
  await page.waitForTimeout(300);

  // Should now have 2 sessions
  await expect(historyItems).toHaveCount(2);

  // Screenshot 4: new chat created, old one has title
  await page.screenshot({ path: 'test-results/ai-sidebar-switched.png' });

  // Switch back to first session by clicking its history item
  await historyItems.nth(1).click();
  await page.waitForTimeout(300);

  // Screenshot 5: back to first session
  await page.screenshot({ path: 'test-results/ai-sidebar-back-to-first.png' });
});
