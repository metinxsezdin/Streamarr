import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.firefox.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.dizibox.live/all-creatures-great-and-small-6-sezon-3-bolum-izle/")
    page.locator("#video-area iframe").content_frame.locator("#Player iframe").content_frame.get_by_text("Videoyu Başlat").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
