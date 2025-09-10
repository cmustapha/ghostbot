# pip install selenium
import json, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

COOKIES_PATH = "cookies/tumblr_ghost01.json"

def inject_cookies_cdp(driver, cookies):
    # Activer le réseau pour setCookie
    driver.execute_cdp_cmd("Network.enable", {})
    for c in cookies:
        dom = c.get("domain","").lstrip(".")  # CDP n’aime pas le point initial
        payload = {
            "name":  c["name"],
            "value": c["value"],
            "domain": dom,
            "path":  c.get("path","/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        # MêmeSite (respecter le couple SameSite=None + secure=True)
        ss = c.get("sameSite")
        if ss:
            ss = ss.capitalize()  # "None" / "Lax" / "Strict"
            if ss == "None":
                payload["sameSite"] = "None"
                payload["secure"] = True
            elif ss in ("Lax","Strict"):
                payload["sameSite"] = ss
        # Expiry -> CDP utilise 'expires' (secondes epoch float)
        if "expiry" in c:
            payload["expires"] = float(c["expiry"])
        driver.execute_cdp_cmd("Network.setCookie", payload)

def build_driver():
    opts = Options()
    #opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    # Idéal: figer le même User-Agent qu’au moment du login initial
    # opts.add_argument("--user-agent=Mozilla/5.0 ...")
    return webdriver.Chrome(options=opts)

if __name__ == "__main__":
    # 1) Ouvre un contexte sur le bon domaine AVANT l'injection
    driver = build_driver()
    driver.get("https://www.tumblr.com/")  # IMPORTANT
    cookies = json.load(open(COOKIES_PATH, "r"))
    inject_cookies_cdp(driver, cookies)
    time.sleep(30)
    # 2) Va sur le dashboard (devrait être déjà loggé)
    driver.get("https://www.tumblr.com/dashboard")
    time.sleep(30)
    print("URL après injection:", driver.current_url)
    html = driver.page_source
    print("Connecté ?", "dashboard" in driver.current_url or "post-type" in html)
    driver.quit()
