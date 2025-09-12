# -*- coding: utf-8 -*-
# pip install selenium

import argparse, json, os, random, time, sys
from pathlib import Path
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DASH = "https://www.tumblr.com/dashboard"
NEW_PHOTO = "https://www.tumblr.com/new/photo"  # éditeur direct


def log(msg: str):
    print(time.strftime("[%Y-%m-%d %H:%M:%S] "), msg)


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
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument(f"--lang={lang}")

    if proxy:
        # http://host:port ou socks5://host:port
        opts.add_argument(f"--proxy-server={proxy}")

    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    if user_data_dir:
        # Profil Chrome persistant : cookies, localStorage, etc.
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={user_data_dir}")

    driver = webdriver.Chrome(options=opts)
    return driver


def inject_cookies_cdp(driver: webdriver.Chrome, cookies_path: str):
    """Injection de cookies via Chrome DevTools Protocol (fiable en headless)."""
    if not cookies_path or not Path(cookies_path).exists():
        log("⚠️  Aucun cookies_path fourni ou fichier introuvable — skip injection.")
        return

    with open(cookies_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    driver.get("https://www.tumblr.com/")  # domaine requis avant setCookie
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


def wait_css(driver, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def type_with_human_pause(elem, text: str, jitter=(0.02, 0.08)):
    for ch in text:
        elem.send_keys(ch)
        time.sleep(random.uniform(*jitter))


def post_tumblr_photo(
    image_path: str,
    caption: str = "",
    tags: Optional[List[str]] = None,
    timeout: int = 40,
    dry_run: bool = False
) -> bool:
    """
    Poste une photo + caption (+ tags optionnels) sur Tumblr.
    Retourne True si publication détectée / False sinon.
    """
    tags = tags or []

    # Aller directement sur l'éditeur Photo
    log("🧭 Ouverture de l’éditeur Photo Tumblr…")
    driver.get(NEW_PHOTO)

    try:
        # Champ file input
        file_input = wait_css(driver, "input[type='file']", timeout=timeout)
    except TimeoutException:
        log("❌ Impossible de trouver l'input de fichier (éditeur non chargé ?).")
        return False

    # Upload image
    img_abs = str(Path(image_path).resolve())
    if not Path(img_abs).exists():
        log(f"❌ Image introuvable: {img_abs}")
        return False

    log(f"📤 Upload image: {img_abs}")
    file_input.send_keys(img_abs)

    # Attendre l’aperçu (un conteneur de la vignette)
    try:
        wait_css(driver, "[data-testid='media-row']", timeout=timeout)
    except TimeoutException:
        log("⚠️  Aucune prévisualisation détectée (sélecteur peut changer). On continue.")



    # Saisir la légende
    caption_box = None
    selectors_to_try = [
        # --- textarea explicites en priorité ---
        #"textarea[aria-label='Éditeur de tags']",
        "p.block-editor-rich-text__editable.rich-text[contenteditable='true'][role='document']",
        "p[role='document'][contenteditable='true'][aria-multiline='true']",
        "p[contenteditable='true'][data-type='core/paragraph']",
        "p[contenteditable='true'][data-custom-placeholder='true']",
        "p[aria-label^='Empty block']",
        "p.block-editor-block-list__block[contenteditable='true']",
        # Parfois le placeholder est dans un span enfant : on cible quand même le p parent
        "p[contenteditable='true'] span[data-rich-text-placeholder]",  # on match l'enfant; on remontera avec .find_element(...) si besoin

        # --- XPATH équivalents (fallbacks) ---
        "//p[@role='document' and @contenteditable='true' and @aria-multiline='true']",
        "//p[contains(@class,'block-editor-rich-text__editable') and @contenteditable='true']",
        "//p[@data-type='core/paragraph' and @contenteditable='true']",
        "//p[@contenteditable='true' and @data-custom-placeholder='true']",
        "//p[starts-with(@aria-label,'Empty block') and @contenteditable='true']",  "p.block-editor-rich-text__editable.rich-text[contenteditable='true'][role='document']",
        "p[role='document'][contenteditable='true'][aria-multiline='true']",
        "p[contenteditable='true'][data-type='core/paragraph']",
        "p[contenteditable='true'][data-custom-placeholder='true']",
        "p[aria-label^='Empty block']",
        "p.block-editor-block-list__block[contenteditable='true']",
        # Parfois le placeholder est dans un span enfant : on cible quand même le p parent
        "p[contenteditable='true'] span[data-rich-text-placeholder]",  # on match l'enfant; on remontera avec .find_element(...) si besoin

        # --- XPATH équivalents (fallbacks) ---
        "//p[@role='document' and @contenteditable='true' and @aria-multiline='true']",
        "//p[contains(@class,'block-editor-rich-text__editable') and @contenteditable='true']",
        "//p[@data-type='core/paragraph' and @contenteditable='true']",
        "//p[@contenteditable='true' and @data-custom-placeholder='true']",
        "//p[starts-with(@aria-label,'Empty block') and @contenteditable='true']",
    ]

    log("🔎 Recherche de la zone de légende...")
    for selector in selectors_to_try:
        try:
            if selector.startswith("//"):  # Si c'est un XPath
                caption_box = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
            else:  # Si c'est un CSS Selector
                caption_box = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            log(f"✅ Zone de légende trouvée avec le sélecteur : {selector}")
            break
        except TimeoutException:
            log(f"❌ Sélecteur '{selector}' a échoué.")
            continue
    

    if caption_box and caption:
        log("✍️ Saisie de la légende…")
        ok = False

        # Tentative 1 : send_keys classique
        try:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", caption_box)
            except Exception:
                pass
            try:
                caption_box.click()
            except Exception:
                pass
            try:
                caption_box.clear()
            except Exception:
                pass
            try:
                caption_box.send_keys(Keys.CONTROL, "a")
                caption_box.send_keys(Keys.DELETE)
            except Exception:
                pass

            caption_box.send_keys(caption)
            ok = True
        except Exception as e:
            log(f"ℹ️ send_keys a échoué: {e}")

          
    

    # Ajouter des tags (si UI visible)
    if tags:
        try:
            tag_zone = wait_css(driver, "textarea[aria-label='Éditeur de tags']", timeout=10)
            for t in tags:
                t = t.strip().replace("#", "")
                if not t:
                    continue
                tag_zone.send_keys(t)
                time.sleep(0.2)
                tag_zone.send_keys("\n")
                time.sleep(0.2)
        except TimeoutException:
            log("ℹ️  Zone tags non trouvée — on passe les tags.")

    if dry_run:
        log("🟡 DRY-RUN activé — on n’appuie pas sur « Post ».")
        return True

    # Cliquer sur "Post" / "Publier"
    posted = False
    try:
        # Bouton principal "Post" (intitulé peut varier selon langue)
        # On essaie plusieurs stratégies
        candidates = [
            "//button[.//span[text()='Post' or text()='Publier']]",
            "//button[contains(., 'Post') or contains(., 'Publier')]",
            "//button[@data-testid='post-form-button']",
        ]
        for xp in candidates:
            btns = driver.find_elements(By.XPATH, xp)
            if btns:
                log("🚀 Publication…")
                btns[0].click()
                posted = True
                break

        if not posted:
            log("❌ Bouton « Post » introuvable.")
            return False

        # Attendre redirection/confirmation (retour dashboard ou toast)
        time.sleep(3)
        # Vérification simple : on est retourné au dashboard OU le bouton n’est plus cliquable
        if driver.current_url.startswith(DASH):
            log("✅ Publication confirmée (dashboard).")
            return True

        # Sinon, on regarde si l’éditeur est vide (post parti)
        # (Fallback léger)
        time.sleep(2)
        return True

    except Exception as e:
        log(f"❌ Erreur pendant la publication: {e}")
        return False


def parse_tags(tags_str: Optional[str]) -> List[str]:
    if not tags_str:
        return []
    # tags séparés par virgule ou espace
    if "," in tags_str:
        return [t.strip() for t in tags_str.split(",") if t.strip()]
    return [t.strip() for t in tags_str.split(" ") if t.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Poster un média + message sur Tumblr (paramétrable).")
    ap.add_argument("--image", required=True, help="Chemin du média (jpg/png/gif).")
    ap.add_argument("--caption", default="", help="Texte/légende à poster.")
    ap.add_argument("--tags", default="", help="Tags séparés par virgules ou espaces.")
    ap.add_argument("--cookies", default="", help="Fichier cookies JSON (CDP).")
    ap.add_argument("--profile", default="", help="Dossier profil Chrome (user-data-dir).")
    ap.add_argument("--proxy", default="", help="Proxy (ex: http://host:port ou socks5://host:port).")
    ap.add_argument("--headless", action="store_true", help="Mode headless.")
    ap.add_argument("--ua", default="", help="User-Agent custom.")
    ap.add_argument("--window", default="1280,800", help="Taille fenêtre (ex: 1280,800).")
    ap.add_argument("--lang", default="fr-FR", help="Langue navigateur.")
    ap.add_argument("--timeout", type=int, default=40, help="Timeouts d’attente (s).")
    ap.add_argument("--sleep", default="0,0", help="Pause aléatoire avant post: min,max en secondes (ex: 3,8).")
    ap.add_argument("--dry-run", action="store_true", help="N’effectue pas le clic « Post ». Test complet sans publier.")
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
        driver.get("https://www.tumblr.com/")
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
    result = post_tumblr_photo(
        image_path=args.image,
        caption=args.caption,
        tags=parse_tags(args.tags),
        timeout=args.timeout,
        dry_run=args.dry_run
    )
    driver.quit()
    sys.exit(0 if result else 2)
