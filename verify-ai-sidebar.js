const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('http://localhost:3001');
  await page.waitForLoadState('networkidle');
  await page.getByText('AI 搜索').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'test-results/ai-sidebar-initial.png' });

  // Click new chat on empty session — should not create duplicate
  await page.click('.ai-search__new-chat');
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'test-results/ai-sidebar-no-duplicate.png' });

  // Send message via example
  await page.click('.ai-search__examples button');
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'test-results/ai-sidebar-with-message.png' });

  // Now new chat should work
  await page.click('.ai-search__new-chat');
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'test-results/ai-sidebar-switched.png' });

  // Switch back to first session
  await page.locator('.ai-search__history-item').nth(1).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'test-results/ai-sidebar-back-to-first.png' });

  await browser.close();
  console.log('Done');
})();
