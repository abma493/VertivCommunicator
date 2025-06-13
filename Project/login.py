from common.common_imports import *
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from logger import Logger
from playwright.async_api import Page

# Playwright setup function
async def setup(web: str):
    try:
        playwright = await async_playwright().start()
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context() 
        page = await context.new_page()
        try:
            await page.goto(web, timeout=default_timeout)
        except PlaywrightTimeoutError as e:
            Logger.log(f"Failed to load page: {e}")
            await browser.close()
            await playwright.stop()
            return None, None, None
        
        # Wait for body to ensure page is loaded
        try:
            await page.wait_for_selector("body", timeout=default_timeout)
        except PlaywrightTimeoutError:
            Logger.log("Page failed to load completely.")
            await browser.close()
            await playwright.stop()
            return None, None, None
            
        return page, browser, playwright
        
    except Exception as e:
        Logger.log(f"Error during setup: {e}")
        return None, None, None

# Login function
async def login(page: Page, user: str, passwd: str) -> bool:
    try:
        # Username field
        user_field = await page.wait_for_selector("#username", state="visible", timeout=default_timeout)
        await user_field.click()
        await user_field.fill("")  # Clear the field
        
        # Password field
        pswd_field = await page.wait_for_selector("#password", state="visible", timeout=default_timeout)
        await pswd_field.click()
        await pswd_field.fill("")  # Clear the field
        
        # Enter credentials
        await user_field.fill(user)
        await pswd_field.fill(passwd)
        
        # Click login button
        login_button = await page.wait_for_selector("#login", state="visible", timeout=default_timeout)
        await login_button.click()
             
        # Check for login error
        try:
            await page.wait_for_selector("#loginError", timeout=5000)
            return False
        except:
            pass
        
        return True
        
    except PlaywrightTimeoutError:
        Logger.log("Login failed - Timeout while parsing elements\nCheck your network/VPN.")
        return False
    except Exception as e:
        Logger.log(f"Login failed with error: {e}")
        return False