import { test, expect, type Page } from '@playwright/test';

/**
 * Real-browser responsive verification for the observability workspace.
 *
 * Runs against the Vite dev server in typed **mock** mode (see
 * `playwright.config.ts` `webServer.env`), so it needs no FastAPI server, no API
 * key, and no network beyond localhost. It verifies rendered geometry — column
 * vs. stacked relationships, sidebar collapse, reachable controls, safe
 * wrapping, and horizontal-overflow protection — not the mere presence of CSS.
 *
 * Locators are semantic (roles, accessible names, labels, landmarks); a stable
 * class is used only where geometry has to be read from a specific element.
 */

const REQUEST_LABEL = 'Request';
const RUN_BUTTON = 'Run request';
const STOP_BUTTON = 'Stop waiting for this request';

/** No horizontal overflow at the document level. */
async function expectNoHorizontalOverflow(page: Page) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth, 'document must not overflow horizontally').toBeLessThanOrEqual(clientWidth);
}

/** Load the workspace and wait until it is interactive (mock health resolved). */
async function gotoWorkspace(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('textbox', { name: REQUEST_LABEL })).toBeVisible();
}

test.describe('wide desktop (1440x900)', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('shows three panes side by side, toggle hidden, no overflow', async ({ page }) => {
    await gotoWorkspace(page);

    // Mock mode is genuinely active (fixtures, not a live API) — proves the
    // web server started in VITE_API_MODE=mock.
    await expect(page.getByText('Mock environment')).toBeVisible();

    // Desktop retains the complete server-policy strip and top-level refresh.
    const status = page.getByRole('list', { name: 'Runtime status' });
    for (const value of [
      'Privacy',
      'Offline restrictions',
      'LLM assist',
      'Web search',
      'Mock environment',
      'Fixtures',
    ]) {
      await expect(status.getByText(value, { exact: true })).toBeVisible();
    }
    await expect(page.getByRole('button', { name: 'Refresh runtime status' })).toBeVisible();

    const nav = page.getByRole('navigation', { name: 'Office Agent capabilities' });
    const main = page.getByRole('main');
    const aside = page.getByRole('complementary', { name: 'Execution details' });

    await expect(nav).toBeVisible();
    await expect(main).toBeVisible();
    await expect(aside).toBeVisible();

    // The narrow-screen sidebar toggle is present but hidden when all fit.
    await expect(
      page.getByRole('button', { name: 'Show capabilities', includeHidden: true }),
    ).toBeHidden();

    // Composer and Run Settings are visible and usable.
    await expect(page.getByRole('textbox', { name: REQUEST_LABEL })).toBeVisible();
    const runSettings = page.getByRole('region', { name: 'Run settings' });
    await expect(runSettings).toBeVisible();
    await expect(runSettings.getByRole('button', { name: /run settings/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );

    // Side by side: the aside starts at/after main's right edge and shares its row.
    const mainBox = await main.boundingBox();
    const asideBox = await aside.boundingBox();
    expect(mainBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    if (mainBox && asideBox) {
      expect(asideBox.x).toBeGreaterThanOrEqual(mainBox.x + mainBox.width - 2);
      const verticalOverlap =
        asideBox.y < mainBox.y + mainBox.height && mainBox.y < asideBox.y + asideBox.height;
      expect(verticalOverlap, 'aside shares the row with main').toBe(true);
    }

    await expectNoHorizontalOverflow(page);
  });
});

test.describe('medium (1000x900)', () => {
  test.use({ viewport: { width: 1000, height: 900 } });

  test('keeps the sidebar and stacks the execution aside below main', async ({ page }) => {
    await gotoWorkspace(page);

    const nav = page.getByRole('navigation', { name: 'Office Agent capabilities' });
    const main = page.getByRole('main');
    const aside = page.getByRole('complementary', { name: 'Execution details' });

    // Sidebar is still available at this breakpoint; composer + settings usable.
    await expect(nav).toBeVisible();
    await expect(page.getByRole('textbox', { name: REQUEST_LABEL })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Run settings' })).toBeVisible();

    // Stacked, not side by side: the aside sits below the main column.
    const mainBox = await main.boundingBox();
    const asideBox = await aside.boundingBox();
    expect(mainBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    if (mainBox && asideBox) {
      expect(asideBox.y).toBeGreaterThanOrEqual(mainBox.y + mainBox.height - 2);
    }

    // Execution details remain reachable.
    await aside.scrollIntoViewIfNeeded();
    await expect(aside).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });
});

test.describe('narrow / mobile (390x844)', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('opens capabilities as a keyboard-operable overlay drawer', async ({ page }) => {
    await gotoWorkspace(page);

    const nav = page.getByRole('navigation', { name: 'Office Agent capabilities' });
    const toggle = page.getByRole('button', { name: /capabilities/i });
    const main = page.getByRole('main');

    // Sidebar starts collapsed; the toggle is visible and reports collapsed.
    await expect(nav).toBeHidden();
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');

    const triggerStyle = await toggle.evaluate((element) => {
      const style = window.getComputedStyle(element);
      return {
        backgroundColor: style.backgroundColor,
        borderTopWidth: style.borderTopWidth,
        height: Number.parseFloat(style.height),
        width: Number.parseFloat(style.width),
      };
    });
    expect(triggerStyle.backgroundColor).toBe('rgba(0, 0, 0, 0)');
    expect(triggerStyle.borderTopWidth).toBe('0px');
    expect(triggerStyle.width).toBeGreaterThanOrEqual(40);
    expect(triggerStyle.width).toBeLessThanOrEqual(44);
    expect(triggerStyle.height).toBeGreaterThanOrEqual(40);
    expect(triggerStyle.height).toBeLessThanOrEqual(44);

    const mainBefore = await main.boundingBox();

    // Keyboard activation opens a fixed drawer with a backdrop and close control.
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(nav).toBeVisible();
    await expect(page.getByRole('dialog', { name: 'Capabilities' })).toBeVisible();
    await expect(page.locator('.app__sidebar-backdrop')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Close' })).toBeFocused();

    // The overlay is out of normal flow: opening it does not move the workspace.
    const mainAfter = await main.boundingBox();
    expect(mainBefore).not.toBeNull();
    expect(mainAfter).not.toBeNull();
    if (mainBefore && mainAfter) {
      expect(mainAfter.y).toBeCloseTo(mainBefore.y, 0);
    }

    // Escape closes it and returns focus to the compact trigger.
    await page.keyboard.press('Escape');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(nav).toBeHidden();
    await expect(toggle).toBeFocused();

    await expectNoHorizontalOverflow(page);
  });

  test('uses one compact status summary with an inline policy disclosure', async ({ page }) => {
    await gotoWorkspace(page);

    const header = page.locator('.app__header');
    const composer = page.locator('.composer');
    const summary = page.locator('.status-mobile__toggle');

    await expect(summary).toBeVisible();
    await expect(summary).toHaveAccessibleName(
      'Server policy: Standard. Mock runtime available. Expand details.',
    );
    await expect(summary.getByText('Standard', { exact: true })).toBeVisible();
    await expect(summary.getByText('Fixtures', { exact: true })).toHaveCount(0);
    await expect(summary.locator('.status-mobile__availability--online')).toHaveCount(0);
    await expect(summary).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByRole('list', { name: 'Runtime status' })).toHaveCount(0);
    await expect(page.locator('.status-chip')).toHaveCount(0);
    await expect(page.getByText('Observability workspace')).toBeHidden();
    const productTitle = page.locator('.app__title');
    await expect(productTitle).toHaveText('Enterprise Office Agent');
    const titleSize = await productTitle.evaluate((element) => ({
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }));
    expect(titleSize.scrollWidth).toBeLessThanOrEqual(titleSize.clientWidth + 1);

    // The persistent app bar remains one compact row and leaves the composer nearby.
    const headerBox = await header.boundingBox();
    const composerBox = await composer.boundingBox();
    expect(headerBox).not.toBeNull();
    expect(composerBox).not.toBeNull();
    if (headerBox && composerBox) {
      expect(headerBox.height).toBeLessThanOrEqual(64);
      expect(composerBox.y - (headerBox.y + headerBox.height)).toBeLessThanOrEqual(20);
    }
    const summaryBox = await summary.boundingBox();
    expect(summaryBox).not.toBeNull();
    if (summaryBox) {
      expect(summaryBox.width).toBeLessThanOrEqual(120);
    }

    const panelId = await summary.getAttribute('aria-controls');
    const toggleId = await summary.getAttribute('id');
    expect(panelId).toBeTruthy();
    expect(toggleId).toBeTruthy();
    await summary.click();
    await expect(summary).toHaveAttribute('aria-expanded', 'true');
    await expect(summary).toHaveAccessibleName(
      'Server policy: Standard. Mock runtime available. Collapse details.',
    );

    const panel = page.locator(`[id="${panelId}"]`);
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute('aria-labelledby', toggleId!);
    for (const [label, value] of [
      ['Privacy', 'Standard'],
      ['Offline restrictions', 'Off'],
      ['LLM assist', 'Off'],
      ['Web search', 'Available'],
      ['Data source', 'Fixtures'],
    ]) {
      const term = panel.locator('dt').filter({ hasText: label });
      await expect(term).toHaveText(label);
      await expect(term.locator('..').locator('dd')).toContainText(value);
    }
    await expect(panel.getByText(/Last checked:/)).toBeVisible();
    const refresh = panel.getByRole('button', { name: 'Refresh runtime status' });
    await expect(refresh).toBeVisible();
    await refresh.click();
    await expect(refresh).toBeEnabled();

    await summary.click();
    await expect(panel).toBeHidden();
    await expectNoHorizontalOverflow(page);
  });

  test('keeps composer, result, actions, and execution details usable', async ({ page }) => {
    await gotoWorkspace(page);

    // Composer remains ready while Run Settings takes its compact mobile default.
    await expect(page.getByRole('textbox', { name: REQUEST_LABEL })).toBeVisible();
    const runSettings = page.getByRole('region', { name: 'Run settings' });
    await expect(runSettings).toBeVisible();
    const settingsToggle = runSettings.getByRole('button', { name: /run settings/i });
    await expect(settingsToggle).toHaveAttribute('aria-expanded', 'false');
    await expect(runSettings.getByText('Standard · Assist Off · Web Off')).toBeVisible();
    await settingsToggle.click();
    await expect(settingsToggle).toHaveAttribute('aria-expanded', 'true');
    await expect(runSettings.getByRole('radio', { name: 'Standard' })).toBeChecked();

    // Submit a mock request and read its result.
    await page.getByRole('textbox', { name: REQUEST_LABEL }).fill('Show my open tickets');
    await page.getByRole('button', { name: RUN_BUTTON }).click();

    const results = page.getByRole('region', { name: 'Result' });
    await expect(results.getByText('Open tickets (2)')).toBeVisible();

    // Result actions stay within the viewport (do not overflow to the right).
    const innerWidth = await page.evaluate(() => window.innerWidth);
    for (const name of ['Copy result', 'Collapse result']) {
      const box = await page.getByRole('button', { name }).boundingBox();
      expect(box, `${name} action must be laid out`).not.toBeNull();
      if (box) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(innerWidth + 1);
      }
    }

    // Preformatted engine content wraps rather than scrolling horizontally.
    const content = await page.evaluate(() => {
      const el = document.querySelector('.result__content');
      return el ? { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth } : null;
    });
    expect(content, 'result content must be present').not.toBeNull();
    if (content) {
      expect(content.scrollWidth).toBeLessThanOrEqual(content.clientWidth + 1);
    }

    // Execution details are reachable below the result.
    const aside = page.getByRole('complementary', { name: 'Execution details' });
    const resultsBox = await results.boundingBox();
    const asideBox = await aside.boundingBox();
    expect(resultsBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    if (resultsBox && asideBox) {
      expect(asideBox.y).toBeGreaterThanOrEqual(resultsBox.y - 2);
    }
    await aside.scrollIntoViewIfNeeded();
    await expect(aside).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test('keeps a degraded knowledge result, caveat, and provenance readable', async ({ page }) => {
    await gotoWorkspace(page);

    await page
      .getByRole('textbox', { name: REQUEST_LABEL })
      .fill('Demo: knowledge with web search disabled');
    await page.getByRole('button', { name: RUN_BUTTON }).click();

    // The degraded notice is stable completion state: it can only render once
    // the typed mock response has arrived, so no fixed delay is needed.
    const results = page.getByRole('region', { name: 'Result' });
    const degradedNotice = results.getByRole('status').filter({ hasText: 'Degraded run' });
    await expect(degradedNotice).toBeVisible();
    await expect(degradedNotice).toContainText('web_search_disabled');
    await expect(degradedNotice).toContainText('Web search is disabled');

    // A useful local answer remains readable despite the failed fallback path.
    await expect(
      results.getByText('The local knowledge base does not cover the third-party VPN vendor advisory'),
    ).toBeVisible();

    // Structured provenance and graph observability remain reachable below the
    // result at the same narrow viewport.
    const aside = page.getByRole('complementary', { name: 'Execution details' });
    const source = aside.getByText('AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)');
    await source.scrollIntoViewIfNeeded();
    await expect(source).toBeVisible();

    const graph = aside.getByRole('heading', { name: 'Graph execution' });
    await graph.scrollIntoViewIfNeeded();
    await expect(graph).toBeVisible();
    await expect(aside.getByText('web_search_disabled_notice')).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test('keeps Stop reachable within the viewport while loading', async ({ page }) => {
    await gotoWorkspace(page);

    await page.getByRole('textbox', { name: REQUEST_LABEL }).fill('What is the VPN policy?');
    await page.getByRole('button', { name: RUN_BUTTON }).click();

    // The mock client resolves after a short delay; during it, Stop replaces Run
    // in the same slot. It must be visible and inside the viewport.
    const stop = page.getByRole('button', { name: STOP_BUTTON });
    await expect(stop).toBeVisible();

    const innerWidth = await page.evaluate(() => window.innerWidth);
    const box = await stop.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(innerWidth + 1);
    }

    await expectNoHorizontalOverflow(page);
  });
});
