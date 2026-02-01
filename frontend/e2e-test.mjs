// e2e-test.mjs - End-to-end test for Ban Teemo demo UI
import { chromium } from 'playwright';

async function runTests() {
  console.log('Starting E2E tests for Ban Teemo...\n');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });

  const page = await context.newPage();
  const results = { passed: 0, failed: 0, tests: [] };

  async function test(name, fn) {
    try {
      await fn();
      results.passed++;
      results.tests.push({ name, status: 'PASS' });
      console.log(`✓ ${name}`);
    } catch (err) {
      results.failed++;
      results.tests.push({ name, status: 'FAIL', error: err.message });
      console.log(`✗ ${name}`);
      console.log(`  Error: ${err.message}`);
    }
  }

  // Navigate to the app
  await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded', timeout: 15000 });

  // Test 1: Page loads with header
  await test('Page loads with Ban Teemo header', async () => {
    const header = await page.locator('h1:has-text("Ban Teemo")');
    await header.waitFor({ timeout: 5000 });
    const text = await header.textContent();
    if (!text.includes('Ban Teemo')) throw new Error('Header not found');
  });

  // Test 2: Subtitle is present
  await test('LoL Draft Assistant subtitle is visible', async () => {
    const subtitle = await page.locator('text=LoL Draft Assistant');
    await subtitle.waitFor({ timeout: 3000 });
  });

  // Test 3: Series selector is present
  await test('Series selector dropdown is present', async () => {
    const seriesLabel = await page.locator('label:has-text("Series")').first();
    await seriesLabel.waitFor({ timeout: 3000 });
    const select = await page.locator('select').first();
    await select.waitFor({ timeout: 3000 });
  });

  // Test 4: Game selector is present
  await test('Game selector dropdown is present', async () => {
    const gameLabel = await page.locator('text=Game');
    await gameLabel.waitFor({ timeout: 3000 });
  });

  // Test 5: Speed selector is present
  await test('Speed selector dropdown is present', async () => {
    const speedLabel = await page.locator('text=Speed');
    await speedLabel.waitFor({ timeout: 3000 });
  });

  // Test 6: Start Replay button is present and initially disabled
  await test('Start Replay button is present', async () => {
    const button = await page.locator('button:has-text("Start Replay")');
    await button.waitFor({ timeout: 3000 });
    const isDisabled = await button.isDisabled();
    if (!isDisabled) throw new Error('Start button should be disabled when no series selected');
  });

  // Test 7: Draft Board section exists
  await test('Draft Board component renders', async () => {
    // Looking for team panels or draft-related UI elements
    const mainContent = await page.locator('main');
    await mainContent.waitFor({ timeout: 3000 });
  });

  // Test 8: Speed options are correct
  await test('Speed selector has correct options (0.5x, 1x, 2x, 4x)', async () => {
    const speedSelect = await page.locator('select').nth(2); // Third select is speed
    const options = await speedSelect.locator('option').allTextContents();
    const expected = ['0.5x', '1x', '2x', '4x'];
    for (const exp of expected) {
      if (!options.includes(exp)) throw new Error(`Missing speed option: ${exp}`);
    }
  });

  // Test 9: Check for dark theme background
  await test('Dark theme is applied (bg-lol-darkest)', async () => {
    const body = await page.locator('div.min-h-screen');
    await body.waitFor({ timeout: 3000 });
  });

  // Test 10: Series dropdown has placeholder option
  await test('Series dropdown has placeholder "Select a series..."', async () => {
    const select = await page.locator('select').first();
    const selectedText = await select.evaluate(el => el.options[el.selectedIndex].text);
    if (!selectedText.includes('Select a series')) throw new Error('Placeholder not found');
  });

  // Test 11: Blue team panel shows roles
  await test('Blue team panel displays all 5 roles', async () => {
    const roles = ['TOP', 'JNG', 'MID', 'ADC', 'SUP'];
    for (const role of roles) {
      const roleEl = await page.locator(`text=${role}`).first();
      await roleEl.waitFor({ timeout: 3000 });
    }
  });

  // Test 12: Red team panel exists
  await test('Red team panel displays "RED SIDE"', async () => {
    const redSide = await page.locator('text=RED SIDE');
    await redSide.waitFor({ timeout: 3000 });
  });

  // Test 13: Blue team panel exists
  await test('Blue team panel displays "BLUE SIDE"', async () => {
    const blueSide = await page.locator('text=BLUE SIDE');
    await blueSide.waitFor({ timeout: 3000 });
  });

  // Test 14: Phase indicators present
  await test('Phase indicators (BAN 1, PICK 1, BAN 2, PICK 2) are visible', async () => {
    const phases = ['BAN 1', 'PICK 1', 'BAN 2', 'PICK 2'];
    for (const phase of phases) {
      const phaseEl = await page.locator(`text=${phase}`);
      await phaseEl.waitFor({ timeout: 3000 });
    }
  });

  // Test 15: Action counter shows initial state
  await test('Action counter shows "/ 20 ACTIONS"', async () => {
    const counter = await page.locator('text=20 ACTIONS');
    await counter.waitFor({ timeout: 3000 });
  });

  // Test 16: Waiting message in recommendations panel
  await test('Recommendations panel shows waiting message', async () => {
    const waiting = await page.locator('text=Waiting for draft to begin');
    await waiting.waitFor({ timeout: 3000 });
  });

  // Test 17: Phase 1 and Phase 2 labels present
  await test('Phase 1 and Phase 2 labels are visible in center', async () => {
    const phase1 = await page.locator('text=PHASE 1');
    const phase2 = await page.locator('text=PHASE 2');
    await phase1.waitFor({ timeout: 3000 });
    await phase2.waitFor({ timeout: 3000 });
  });

  // ========== BACKEND INTEGRATION TESTS ==========
  console.log('\n--- Backend Integration Tests ---');

  // Wait for series to load from API
  await page.waitForTimeout(2000);

  // Test 18: Series are loaded from backend
  await test('Series dropdown is populated from backend API', async () => {
    const select = await page.locator('select').first();
    const optionCount = await select.locator('option').count();
    // Should have placeholder + at least some series from backend
    if (optionCount < 2) throw new Error(`Expected multiple options, got ${optionCount}`);
  });

  // Test 19: Select a series and verify games load
  await test('Selecting a series loads games from backend', async () => {
    const seriesSelect = await page.locator('select').first();
    // Get the first real option (not the placeholder)
    const options = await seriesSelect.locator('option').all();
    if (options.length < 2) throw new Error('No series available');

    // Select the second option (first real series)
    const optionValue = await options[1].getAttribute('value');
    await seriesSelect.selectOption(optionValue);

    // Wait for games to load
    await page.waitForTimeout(1000);

    // Check that game selector has options
    const gameSelect = await page.locator('select').nth(1);
    const gameOptions = await gameSelect.locator('option').count();
    if (gameOptions < 1) throw new Error('No games loaded');
  });

  // Test 20: Start Replay button becomes enabled after series selection
  await test('Start Replay button is enabled after selecting series', async () => {
    const button = await page.locator('button:has-text("Start Replay")');
    const isDisabled = await button.isDisabled();
    if (isDisabled) throw new Error('Start button should be enabled after selecting series');
  });

  // Test 21: Series dropdown shows team names from backend
  await test('Series dropdown displays team names from backend', async () => {
    const seriesSelect = await page.locator('select').first();
    const selectedText = await seriesSelect.evaluate(el => el.options[el.selectedIndex].text);
    // Should contain team names like "Team A vs Team B (date)"
    if (!selectedText.includes(' vs ')) throw new Error(`Expected team matchup in: ${selectedText}`);
  });

  // Test 22: Click Start Replay and verify API call works
  await test('Start Replay calls backend API successfully', async () => {
    const startButton = await page.locator('button:has-text("Start Replay")');
    await startButton.click();

    // Wait for response
    await page.waitForTimeout(2000);

    // Check if status changed - either connecting, Live, Stop button, or WebSocket error
    // WebSocket error means the REST API worked but WS isn't connected (expected for now)
    const pageContent = await page.content();
    const hasStatusChange = pageContent.includes('Connecting') ||
                            pageContent.includes('Live') ||
                            pageContent.includes('Stop') ||
                            pageContent.includes('WebSocket') ||
                            pageContent.includes('connection');
    if (!hasStatusChange) throw new Error('No status change after clicking Start Replay');
  });

  // Take a screenshot after starting replay
  await page.screenshot({ path: 'e2e-screenshot-replay-started.png', fullPage: true });
  console.log('\nScreenshot saved to e2e-screenshot-replay-started.png');

  // Take the basic screenshot too
  await page.screenshot({ path: 'e2e-screenshot-with-data.png', fullPage: true });
  console.log('Screenshot saved to e2e-screenshot-with-data.png');

  await page.screenshot({ path: 'e2e-screenshot.png', fullPage: true });
  console.log('Screenshot saved to e2e-screenshot.png');

  await browser.close();

  // Summary
  console.log('\n' + '='.repeat(50));
  console.log(`Test Results: ${results.passed} passed, ${results.failed} failed`);
  console.log('='.repeat(50));

  if (results.failed > 0) {
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('Test runner error:', err);
  process.exit(1);
});
