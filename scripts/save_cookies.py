# pip install selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json, sys, time

LOGIN_URL = "https://www.tumblr.com/login"
DASHBOARD_URL_PREFIX = "https://www.tumblr.com/dashboard"
COOKIES_PATH = "cookies/tumblr_ghost01.json"

def is_logged_in(driver):
    # 1) Test par URL
    if driver.current_url.startswith(DASHBOARD_URL_PREFIX):
        return True
    # 2) Test par élément présent uniquement après login
    try:
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='post-type-selector']"))
        )
        return True
    except:
        return False

def main():
    opts = Options()
    # lance en mode visible pour se connecter
    # opts.add_argument("--headless=new")  # ne PAS headless pour ce login
    opts.add_argument("--window-size=1280,800")
    driver = webdriver.Chrome(options=opts)
    driver.get(LOGIN_URL)

    print("➡️ Connecte-toi manuellement (email, mot de passe, 2FA s'il y a).")
    print("   Le script attendra automatiquement le dashboard.")
    # Boucle d'attente de login (max ~5 minutes)
    T0 = time.time()
    TIMEOUT = 300
    while time.time() - T0 < TIMEOUT:
        time.sleep(2)
        if is_logged_in(driver):
            break

    if not is_logged_in(driver):
        print("❌ Pas connecté après attente. Réessaie sans fermer la fenêtre.")
        input("Quand tu es connecté, appuie sur Entrée pour retester… ")
        if not is_logged_in(driver):
            print("❌ Toujours pas connecté. Abandon.")
            driver.quit()
            sys.exit(1)

    # On est loggé, on sauvegarde
    cookies = driver.get_cookies()
    with open(COOKIES_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookies de session sauvegardés → {COOKIES_PATH}")
    driver.quit()

if __name__ == "__main__":
    main()
