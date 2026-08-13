import { expect, test } from '@playwright/test';

test('fresh user builds an actionable candidate profile with the onboarding agent', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'The complete onboarding mutation flow runs once; responsive rendering is covered separately.');
  await page.goto('/signup');
  await page.getByLabel('Email address').fill(`onboarding.${Date.now()}@example.com`);
  await page.getByLabel('Password', { exact: true }).fill('Build-My-Career-Profile-2026');
  await page.getByLabel('Confirm password').fill('Build-My-Career-Profile-2026');
  await page.getByRole('button', { name: /Create workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Meet your Profile Steward' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('onboarding-welcome-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(dialog).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath('onboarding-welcome-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await dialog.getByRole('button', { name: /Build my candidate profile/ }).click();
  await dialog.getByRole('button', { name: /answer from scratch/i }).click();

  await dialog.getByLabel('Your professional headline').fill('Product-minded platform engineer');
  await dialog.getByLabel(/Roles you want next/).fill('Staff Platform Engineer, Engineering Lead');
  await dialog.getByLabel(/Industries or domains/).fill('Developer tools, AI infrastructure');
  await dialog.getByRole('button', { name: /Continue/ }).click();

  await dialog.getByLabel('Current location').fill('Toronto, Canada');
  await dialog.getByLabel(/Authorized to work in/).fill('Canada');
  await dialog.getByRole('button', { name: /Remote/ }).click();
  await dialog.getByLabel(/Minimum compensation/).fill('150000');
  await dialog.getByRole('button', { name: /Save my boundaries/ }).click();

  await dialog.getByLabel(/Core skills and capabilities/).fill('Python, Platform architecture, Technical leadership');
  await dialog.getByLabel(/What are you trusted/).fill('Building dependable systems and helping teams make clear, pragmatic technical decisions.');
  await dialog.getByRole('button', { name: /Add these strengths/ }).click();

  await dialog.getByLabel('Name this accomplishment').fill('Improved deployment recovery');
  await dialog.getByLabel(/What was the situation/).fill('Led a reliability program across the platform that reduced deployment recovery time by 40 percent and made releases safer for multiple teams.');
  await dialog.getByRole('button', { name: /Save this proof point/ }).click();

  await dialog.getByRole('button', { name: 'High ownership', exact: true }).click();
  await dialog.getByRole('button', { name: 'Calm collaboration', exact: true }).click();
  await dialog.getByRole('button', { name: 'Always-on culture', exact: true }).click();
  await dialog.getByRole('button', { name: /Use these preferences/ }).click();

  const summary = dialog.getByLabel('Your professional through-line');
  await expect(summary).not.toHaveValue('');
  await dialog.getByRole('button', { name: /This represents me/ }).click();

  await expect(dialog.getByRole('heading', { name: 'Your candidate profile is ready' })).toBeVisible();
  await expect(dialog.locator('.readiness-ring strong')).toHaveText('100%');
  await page.screenshot({ path: testInfo.outputPath('onboarding-ready.png'), fullPage: true });
  await dialog.getByRole('button', { name: /Activate my job search/ }).click();
  await expect(dialog).toBeHidden();

  await page.goto('/profile');
  await expect(page.getByText('90%', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Professional headline')).toHaveValue('Product-minded platform engineer');
});
