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
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(scrollWidth, 'document must not overflow horizontally').toBeLessThanOrEqual(innerWidth);
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
    await expect(page.getByRole('region', { name: 'Run settings' })).toBeVisible();

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

  test('collapses the sidebar behind a keyboard-operable toggle', async ({ page }) => {
    await gotoWorkspace(page);

    const nav = page.getByRole('navigation', { name: 'Office Agent capabilities' });
    const toggle = page.getByRole('button', { name: /capabilities/i });

    // Sidebar starts collapsed; the toggle is visible and reports collapsed.
    await expect(nav).toBeHidden();
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');

    // Click opens it: aria-expanded flips and the rail becomes visible.
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(nav).toBeVisible();

    // Keyboard closes it: focus the toggle and press Enter.
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(nav).toBeHidden();

    await expectNoHorizontalOverflow(page);
  });

  test('keeps composer, result, actions, and execution details usable', async ({ page }) => {
    await gotoWorkspace(page);

    // Composer and Run Settings remain visible and usable.
    await expect(page.getByRole('textbox', { name: REQUEST_LABEL })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Run settings' })).toBeVisible();

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
