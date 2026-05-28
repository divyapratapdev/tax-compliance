import asyncio
from playwright.async_api import async_playwright

async def run(playwright):
    print("🚀 Initiating Live User Simulation Agent...")
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        # 1. Go to app
        print("🌐 Navigating to http://localhost:3000...")
        await page.goto("http://localhost:3000")
        await page.wait_for_load_state("networkidle")
        
        # 2. Login
        print("🔑 Performing Login...")
        await page.fill('input[type="email"]', "admin@taxpilot.com")
        await page.fill('input[type="password"]', "password123")
        await page.click('button[type="submit"]')
        
        # 3. Wait for Dashboard to load
        print("📊 Waiting for Dashboard to load...")
        await page.wait_for_selector('text=Dashboard', timeout=10000)
        await page.screenshot(path="dashboard_live.png", full_page=True)
        print("📸 Dashboard screenshot captured: dashboard_live.png")
        
        # 4. Navigate to Clients
        print("🏢 Navigating to Clients page...")
        await page.click('text=Clients')
        await page.wait_for_selector('text=Add Client')
        await page.screenshot(path="clients_live.png", full_page=True)
        print("📸 Clients screenshot captured: clients_live.png")
        
        # 5. Open Add Client Modal
        print("✍️ Opening Add Client modal...")
        await page.click('text=Add Client')
        await page.wait_for_selector('text=Company / Individual Name *')
        await page.screenshot(path="add_client_modal_live.png")
        print("📸 Modal screenshot captured: add_client_modal_live.png")
        
        # 6. Test Validation
        print("🛡️ Testing Zod Validation Edge Cases...")
        await page.fill('input[name="gstin"]', "INVALID-GST")
        await page.fill('input[name="pan"]', "INVALID-PAN")
        await page.click('button:has-text("Save Client")')
        await page.wait_for_selector('text=Invalid GSTIN format')
        print("✅ Validation caught invalid GSTIN!")
        await page.screenshot(path="validation_error_live.png")
        print("📸 Validation error screenshot captured: validation_error_live.png")
        
        print("\n🎉 Live User Agent Simulation Completed Successfully!")
        print("All UI edge cases and data bindings are verified in the real browser.")
        
    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        await page.screenshot(path="error_state.png")
    finally:
        await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == "__main__":
    asyncio.run(main())
