import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.firefox.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.hdfilmcehennemi.la/nobody-2-2/")
    page.get_by_role("img", name="Play icon").click()
    page.locator("iframe").content_frame.get_by_role("button", name="Play Video").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
