const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../.tmp/slides-grab-runtime/node_modules/playwright');

const appUrl = process.env.APP_URL || 'http://127.0.0.1:8765';
const outputDir = path.resolve(__dirname, 'assets', 'current');

async function capture(page, filename) {
  await page.screenshot({ path: path.join(outputDir, filename), animations: 'disabled' });
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1536, height: 960 },
    deviceScaleFactor: 1.5,
    locale: 'ko-KR',
    colorScheme: 'light',
  });
  const page = await context.newPage();
  const browserErrors = [];
  page.on('pageerror', error => browserErrors.push(error.message));

  try {
    await page.goto(appUrl, { waitUntil: 'networkidle', timeout: 60000 });
    await page.locator('#loadClassroomButton').waitFor({ state: 'visible' });
    await capture(page, 'current-home.png');

    await page.locator('#loadClassroomButton').click();
    await page.locator('#sampleBanner:not(.hidden)').waitFor({ timeout: 30000 });
    await page.locator('#dashboard:not(.hidden)').waitFor({ timeout: 30000 });
    await page.waitForFunction(() => document.querySelector('#selectionCount')?.textContent.includes('2'));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    await capture(page, 'current-sample.png');

    await page.locator('[data-tab="compare"]').click();
    await page.waitForTimeout(500);
    await page.locator('#tabContent').scrollIntoViewIfNeeded();
    await capture(page, 'current-compare.png');

    await page.locator('[data-tab="strategy"]').click();
    await page.locator('.strategy-brief').waitFor({ timeout: 30000 });
    await page.locator('.strategy-hero').scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await capture(page, 'current-strategy.png');

    await page.locator('[data-question]').first().click();
    await page.locator('#runAiButton').click();
    await page.waitForFunction(() => {
      const node = document.querySelector('#aiResult');
      return node && node.dataset.state && node.dataset.state !== 'loading';
    }, { timeout: 30000 });
    await page.locator('.prompt-box').scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await capture(page, 'current-ai.png');

    const health = await page.request.get(`${appUrl}/api/health`);
    const healthPayload = await health.json();
    const bootstrap = await page.request.get(`${appUrl}/api/classroom/bootstrap`);
    const bootstrapPayload = await bootstrap.json();
    const manifest = {
      captured_at: new Date().toISOString(),
      app_url: appUrl,
      app_id: healthPayload?.app?.id,
      build_id: healthPayload?.app?.build_id,
      classroom: {
        enabled: bootstrapPayload?.sample?.enabled,
        network_requests: bootstrapPayload?.sample?.network_requests,
        contains_real_company_data: bootstrapPayload?.sample?.contains_real_company_data,
        contains_personal_data: bootstrapPayload?.sample?.contains_personal_data,
      },
      files: fs.readdirSync(outputDir).filter(name => name.endsWith('.png')).sort(),
      browser_errors: browserErrors,
    };
    fs.writeFileSync(path.join(outputDir, 'capture-manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
    if (browserErrors.length) throw new Error(`Browser errors: ${browserErrors.join('; ')}`);
    if (manifest.app_id !== 'kr.opendart.dart-hr-briefing') throw new Error(`Unexpected app id: ${manifest.app_id}`);
    if (manifest.classroom.network_requests !== 0 || manifest.classroom.contains_real_company_data !== false || manifest.classroom.contains_personal_data !== false) {
      throw new Error(`Classroom contract failed: ${JSON.stringify(manifest.classroom)}`);
    }
    console.log(JSON.stringify(manifest, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
