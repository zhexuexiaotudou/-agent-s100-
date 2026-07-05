import { expect, test, type APIRequestContext } from "@playwright/test";

const baseURL = process.env.DIGUA_MM_BASE_URL || "http://127.0.0.1:8791";
const channel = process.env.PLAYWRIGHT_CHANNEL || "msedge";

test.use({ channel });

test("multimodal search UI supports login, rebuild, query, and evidence inspection", async ({ page, request }) => {
  const suffix = Date.now().toString(36);
  const username = `mm_admin_${suffix}`;
  const password = `mm_${suffix}_pass_123`;

  const createUser = await request.post(`${baseURL}/api/identity/create-user`, {
    data: { username, password, role: "admin" },
  });
  expect(createUser.ok()).toBeTruthy();

  const rebuild = await request.post(`${baseURL}/api/multimodal-index/rebuild`, {
    data: { max_files: 80 },
    headers: await authHeaders(request, username, password),
  });
  expect(rebuild.ok()).toBeTruthy();
  const rebuildPayload = await rebuild.json();
  expect(rebuildPayload.ok).toBeTruthy();
  expect(rebuildPayload.image_embeddings).toBeGreaterThan(0);

  await page.goto(`${baseURL}/multimodal-search`);
  await page.getByLabel("User").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.locator("#mm-auth-state")).toContainText(`Signed in: ${username}`);

  await page.getByLabel("Query").fill("white image");
  await page.getByLabel("Mode").selectOption("image");
  await page.getByRole("button", { name: "Search" }).click();

  await expect(page.locator("#mm-status-text")).toContainText(/Results ready|Results with limits/);
  await expect(page.locator("#mm-results .mm-result").first()).toBeVisible();
  await expect(page.locator("#mm-evidence")).toContainText("Evidence");
  await expect(page.locator("#mm-evidence")).toContainText("Path hash");
  await expect(page.locator("#mm-evidence")).not.toContainText("F:\\");
  await expect(page.locator("#mm-evidence")).not.toContainText("/mnt/");
});

async function authHeaders(request: APIRequestContext, username: string, password: string) {
  const login = await request.post(`${baseURL}/api/identity/login`, {
    data: { username, password },
  });
  expect(login.ok()).toBeTruthy();
  const payload = await login.json();
  const token = payload.token || payload.data?.token;
  expect(token).toBeTruthy();
  return { Authorization: `Bearer ${token}` };
}
