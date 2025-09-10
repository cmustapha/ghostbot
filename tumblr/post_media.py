# -*- coding: utf-8 -*-
# pip install selenium

import argparse, json, os, random, sys, time
from pathlib import Path
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DASH = "https://www.tumblr.com/dashboard"
NEW_PHOTO = "https://www.tumblr.com/new/photo"  # éditeur direct

# ----------------------------- Utils log -------------------------------------
def log(msg: str):
    print(time.strftime("[%Y-%m-%d %H:%M:%S] "), msg)

# ------------------------ Selenium driver builder -----------------------------
def build_driver(
    headless: bool = True,
    proxy: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_data_dir: Optional[str] = None,
    window_size: str = "1280,800",
    lang: str = "fr-FR"
) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument(f"--lang={lang}")
    # UA + Proxy + Profil
    if proxy:
        # ex: http://host:port ou socks5://host:port
        opts.add_argument(f"--proxy-server={proxy}")
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")
    if user_data_dir:
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={user_data_dir}")

    driver = webdriver.Chrome(options=opts)
    return driver

# ---------------------- Cookies via Chrome DevTools ---------------------------
def inject_cookies_cdp(driver: webdriver.Chrome, cookies_path: str):
    """Injection fiable de cookies via CDP (fonctionne en headless)."""
    if not cookies_path or not Path(cookies_path).exists():
        log("⚠️  Aucun cookies_path fourni ou fichier introuvable — skip injection.")
        return
    with open(cookies_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    # Charger le domaine avant setCookie
    driver.get("https://www.tumblr.com/")
    driver.execute_cdp_cmd("Network.enable", {})

    for c in cookies:
        dom = c.get("domain", "").lstrip(".")
        payload = {
            "name": c["name"],
            "value": c["value"],
            "domain": dom,
            "path": c.get("path", "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        ss = c.get("sameSite")
        if ss:
            ss_norm = ss.capitalize()
            if ss_norm == "None":
                payload["sameSite"] = "None"
                payload["secure"] = True
            elif ss_norm in ("Lax", "Strict"):
                payload["sameSite"] = ss_norm
        if "expiry" in c:
            payload["expires"] = float(c["expiry"])
        driver.execute_cdp_cmd("Network.setCookie", payload)

# -------------------------- Wait helpers --------------------------------------
def wait_css(driver, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )

def visible_css(driver, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )

def click_if_present(driver, css, timeout=4):
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, css))
        )
        el.click()
        return True
    except Exception:
        return False

def wait_js_true(driver, script: str, timeout=20, poll=0.5):
    """Attend qu'un script JS retourne true."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if driver.execute_script(f"return !!({script});"):
                return True
        except Exception:
            pass
        time.sleep(poll)
    raise TimeoutException(f"wait_js_true timeout for: {script}")

# --------------------- Caption (iframe-aware + fallback) ----------------------
CAPTION_SELECTORS = [
    "[data-testid='caption-editor'] div[contenteditable='true']",
    "div[contenteditable='true'][data-placeholder]",
    "div[role='textbox']",
    "[contenteditable='true']",
]

def switch_into_editor_iframe(driver) -> bool:
    """Essaie d’entrer dans un iframe d’éditeur si présent."""
    driver.switch_to.default_content()
    frames = driver.find_elements(By.CSS_SELECTOR, "iframe")
    for fr in frames:
        try:
            driver.switch_to.frame(fr)
            if driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], [data-testid='post-form']"):
                return True
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
    return False

def find_caption_box(driver):
    # 1) main document
    for sel in CAPTION_SELECTORS:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            return elems[0]
    # 2) tenter dans un iframe
    if switch_into_editor_iframe(driver):
        for sel in CAPTION_SELECTORS:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                return elems[0]
        driver.switch_to.default_content()
    return None

def type_with_human_pause(elem, text: str, jitter=(0.02, 0.08)):
    for ch in text:
        elem.send_keys(ch)
        time.sleep(random.uniform(*jitter))

def set_caption_safely(driver, caption: str) -> bool:
    """Essaie d'écrire la légende, sinon fallback JS avec events."""
    box = find_caption_box(driver)
    if not box:
        return False
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", box)
        try:
            box.click()
        except Exception:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(box).click().perform()
        type_with_human_pause(box, caption)
        typed = (box.get_attribute("innerText") or box.text or "").strip()
        if typed:
            return True
    except Exception:
        pass
    # Fallback JS
    try:
        driver.execute_script("""
            const el = arguments[0], t = arguments[1];
            el.focus();
            if ('innerHTML' in el) el.innerHTML = '';
            const tn = document.createTextNode(t);
            el.appendChild(tn);
            el.dispatchEvent(new InputEvent('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        """, box, caption)
        typed = (box.get_attribute("innerText") or box.text or "").strip()
        return bool(typed)
    except Exception:
        return False
    finally:
        driver.switch_to.default_content()

# ------------------------- Poster un média Tumblr -----------------------------
CONSENT_SELECTORS = [
    "button[aria-label='Accept all']",
    "[data-testid='cookie-accept-all']",
    "button[aria-label='Tout accepter']",
]

POST_BUTTON_XP = [
    "//button[@data-testid='post-form-button']",
    "//button[.//span[normalize-space()='Post' or normalize-space()='Publier']]",
    "//button[contains(.,'Post') or contains(.,'Publier')]",
]

def parse_tags(tags_str: Optional[str]) -> List[str]:
    if not tags_str:
        return []
    if "," in tags_str:
        return [t.strip() for t in tags_str.split(",") if t.strip()]
    return [t.strip() for t in tags_str.split(" ") if t.strip()]

def post_tumblr_photo(
    driver: webdriver.Chrome,
    image_path: str,
    caption: str = "",
    tags: Optional[List[str]] = None,
    timeout: int = 50,
    dry_run: bool = False
) -> bool:
    tags = tags or []

    # 1) Ouvrir l’éditeur
    log("🧭 Ouverture de l’éditeur Photo Tumblr…")
    driver.get(NEW_PHOTO)

    # 2) Fermer consent/cookies si présent
    for sel in CONSENT_SELECTORS:
        if click_if_present(driver, sel, timeout=2):
            log("✅ Consentement cookies accepté.")
            break

    # 3) Trouver ou rendre visible l'input file
    try:
        try:
            file_input = visible_css(driver, "input[type='file']", timeout=timeout)
        except TimeoutException:
            log("⚙️  Input file non visible, on le force via JS.")
            driver.execute_script("""
                const inp = document.querySelector("input[type='file']");
                if (inp) { inp.style.display='block'; inp.style.opacity=1; inp.removeAttribute('hidden'); }
            """)
            file_input = visible_css(driver, "input[type='file']", timeout=10)

        img_abs = str(Path(image_path).resolve())
        if not Path(img_abs).exists():
            log(f"❌ Image introuvable: {img_abs}")
            return False

        log(f"📤 Upload image: {img_abs}")
        file_input.send_keys(img_abs)
    except Exception as e:
        log(f"❌ Impossible d'uploader l'image: {e}")
        return False

    # 4) Attendre une vraie prévisualisation (JS heuristique)
    try:
        wait_js_true(driver,
            "document.querySelectorAll(\"[data-testid='media-row'], [data-testid='attachment'], [data-testid='post-form'] img, [data-testid='post-form'] video\").length > 0",
            timeout=30, poll=0.5
        )
        log("🖼️  Prévisualisation détectée (JS).")
    except TimeoutException:
        try:
            wait_js_true(driver,
                """
                (function(){
                  const form = document.querySelector('[data-testid="post-form"]') || document.body;
                  const imgs = form.querySelectorAll('img');
                  for (const im of imgs) {
                     const w = (im.naturalWidth||0), h=(im.naturalHeight||0);
                     if (w*h > 5000) return true;
                  }
                  return false;
                })()
                """,
                timeout=40, poll=0.5
            )
            log("🖼️  Prévisualisation détectée (heuristique).")
        except TimeoutException:
            log("⚠️  Pas de preview détectée, on continue quand même.")

    # 5) Légende (iframe-aware + fallback)
    if caption:
        if set_caption_safely(driver, caption):
            log("✍️  Légende insérée.")
        else:
            log("⚠️  Zone de légende introuvable / non éditable — on publie sans texte.")

    # 6) Tags si l’UI existe
    if tags:
        try:
            click_if_present(driver, "[data-testid='post-form-tags'] button", timeout=2)
            tag_input = visible_css(driver, "[data-testid='post-form-tags'] input", timeout=6)
            for t in tags:
                t = t.strip().lstrip("#")
                if not t:
                    continue
                tag_input.send_keys(t)
                time.sleep(0.2)
                tag_input.send_keys(Keys.ENTER)
                time.sleep(0.2)
            log(f"🏷️  {len(tags)} tag(s) ajouté(s).")
        except Exception:
            log("ℹ️  Zone tags non trouvée — on passe les tags.")

    if dry_run:
        log("🟡 DRY-RUN activé — on n’appuie pas sur « Post ».")
        return True

    # 7) Publication
    try:
        posted = False
        for xp in POST_BUTTON_XP:
            btns = driver.find_elements(By.XPATH, xp)
            if btns:
                log("🚀 Publication…")
                btns[0].click()
                posted = True
                break
        if not posted:
            log("❌ Bouton « Post » introuvable.")
            return False

        # 8) Confirmation (retour dashboard ou disparition de l’éditeur)
        WebDriverWait(driver, 20).until(
            lambda d: d.current_url.startswith(DASH) or not d.find_elements(By.CSS_SELECTOR, "[data-testid='post-form']")
        )
        log("✅ Publication confirmée.")
        return True
    except Exception as e:
        log(f"❌ Erreur pendant la publication: {e}")
        return False

# --------------------------------- Main --------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Poster un média + message sur Tumblr (paramétrable).")
    ap.add_argument("--image", required=True, help="Chemin du média (jpg/png/gif).")
    ap.add_argument("--caption", default="", help="Texte/légende à poster.")
    ap.add_argument("--tags", default="", help="Tags séparés par virgules ou espaces.")
    ap.add_argument("--cookies", default="", help="Fichier cookies JSON (injection CDP).")
    ap.add_argument("--profile", default="", help="Dossier profil Chrome (user-data-dir).")
    ap.add_argument("--proxy", default="", help="Proxy (http://host:port ou socks5://host:port).")
    ap.add_argument("--headless", action="store_true", help="Mode headless.")
    ap.add_argument("--ua", default="", help="User-Agent custom.")
    ap.add_argument("--window", default="1280,800", help="Taille fenêtre, ex: 1280,800.")
    ap.add_argument("--lang", default="fr-FR", help="Langue navigateur.")
    ap.add_argument("--timeout", type=int, default=50, help="Timeout d’attente (s).")
    ap.add_argument("--sleep", default="0,0", help="Pause aléatoire avant post: min,max en s (ex: 3,9).")
    ap.add_argument("--dry-run", action="store_true", help="Test complet sans publier.")
    args = ap.parse_args()

    # Build driver
    driver = build_driver(
        headless=args.headless,
        proxy=args.proxy or None,
        user_agent=args.ua or None,
        user_data_dir=args.profile or None,
        window_size=args.window,
        lang=args.lang
    )

    # Cookies CDP si pas de profil
    if args.profile:
        log(f"👤 Profil Chrome: {args.profile} (cookies intégrés)")
    elif args.cookies:
        log(f"🍪 Injection cookies via CDP: {args.cookies}")
        inject_cookies_cdp(driver, args.cookies)
    else:
        log("⚠️ Ni profil, ni cookies fournis — tu risques de ne pas être connecté.")

    # Pause aléatoire optionnelle
    try:
        smin, smax = [float(x) for x in args.sleep.split(",")]
        delay = random.uniform(smin, smax)
        if delay > 0:
            log(f"⏳ Pause aléatoire avant post: {delay:.1f}s")
            time.sleep(delay)
    except Exception:
        pass

    # Lancer le post
    tags = parse_tags(args.tags)
    ok = post_tumblr_photo(
        driver=driver,
        image_path=args.image,
        caption=args.caption,
        tags=tags,
        timeout=args.timeout,
        dry_run=args.dry_run
    )
    driver.quit()
    sys.exit(0 if ok else 2)
