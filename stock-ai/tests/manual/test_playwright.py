from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://quote.eastmoney.com/sh600873.html")
    
    # Wait for the data to load (wait until the text doesn't contain just hyphens)
    page.wait_for_function("() => { const el = document.querySelector('.brief_info_c'); return el && !el.innerText.includes('今开：\\t-'); }", timeout=10000)
    
    text = page.locator(".brief_info_c").inner_text()
    print("Extracted text:")
    print(text)
    browser.close()
