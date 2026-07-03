import argparse
import csv
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


DOWNLOAD_BUTTON_XPATHS = [
    # Bouton principal Download
    "//button[contains(normalize-space(.), 'Download')]",
    "//a[contains(normalize-space(.), 'Download')]",

    # Aria-label
    "//button[contains(@aria-label, 'Download')]",
    "//a[contains(@aria-label, 'Download')]",

    # Au cas où l'interface est en français
    "//button[contains(normalize-space(.), 'Télécharger')]",
    "//a[contains(normalize-space(.), 'Télécharger')]",
    "//button[contains(@aria-label, 'Télécharger')]",
    "//a[contains(@aria-label, 'Télécharger')]",
]

COOKIE_BUTTON_XPATHS = [
    "//button[contains(normalize-space(.), 'Accept')]",
    "//button[contains(normalize-space(.), 'Accept all')]",
    "//button[contains(normalize-space(.), 'I agree')]",
    "//button[contains(normalize-space(.), \"J'accepte\")]",
    "//button[contains(normalize-space(.), 'Accepter')]",
    "//button[contains(normalize-space(.), 'Tout accepter')]",
]


def safe_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_len].strip(" ._") or "pixabay_sfx"


def read_links(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    rows = []
    try:
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames and "url" in [h.lower() for h in reader.fieldnames]:
            # Retrouver les noms exacts des colonnes
            field_map = {h.lower(): h for h in reader.fieldnames}
            url_col = field_map["url"]
            title_col = field_map.get("title")

            for row in reader:
                url = (row.get(url_col) or "").strip()
                title = (row.get(title_col) or "").strip() if title_col else ""
                if url.startswith("https://pixabay.com/sound-effects/"):
                    rows.append({"title": title, "url": url})
    except Exception:
        pass

    # Fallback si le fichier n'est pas lu comme CSV
    if not rows:
        for url in re.findall(r"https://pixabay\.com/sound-effects/[^\s,\"]+", text):
            rows.append({"title": "", "url": url.strip()})

    # Supprimer doublons en gardant l'ordre
    seen = set()
    unique = []
    for item in rows:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique


def make_driver(download_dir: Path):
    options = EdgeOptions()
    options.add_argument("--start-maximized")

    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    return webdriver.Edge(options=options)


def click_first_available(driver, xpaths, timeout=8):
    wait = WebDriverWait(driver, timeout)

    last_error = None
    for xpath in xpaths:
        try:
            elem = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                elem,
            )
            time.sleep(0.4)
            try:
                elem.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", elem)
            return True
        except Exception as e:
            last_error = e

    return False


def accept_cookies_if_present(driver):
    try:
        click_first_available(driver, COOKIE_BUTTON_XPATHS, timeout=3)
    except Exception:
        pass


def list_finished_files(download_dir: Path):
    files = []
    for p in download_dir.iterdir():
        if p.is_file() and not p.name.endswith((".crdownload", ".tmp", ".part")):
            files.append(p)
    return set(files)


def wait_for_download(download_dir: Path, before_files: set, timeout=90):
    start = time.time()

    while time.time() - start < timeout:
        current_finished = list_finished_files(download_dir)
        new_files = list(current_finished - before_files)

        active = list(download_dir.glob("*.crdownload")) + list(download_dir.glob("*.tmp")) + list(download_dir.glob("*.part"))

        if new_files and not active:
            newest = max(new_files, key=lambda p: p.stat().st_mtime)
            return newest

        time.sleep(1)

    return None


def rename_downloaded_file(file_path: Path, title: str, url: str):
    if not file_path or not file_path.exists():
        return file_path

    parsed = urlparse(url)
    url_id_match = re.search(r"-(\d+)/?$", parsed.path)
    url_id = url_id_match.group(1) if url_id_match else "unknown"

    base = safe_filename(title) if title else safe_filename(Path(parsed.path).stem)
    ext = file_path.suffix or ".mp3"

    target = file_path.with_name(f"{base} - {url_id}{ext}")

    if target.exists():
        return file_path

    try:
        file_path.rename(target)
        return target
    except Exception:
        return file_path


def download_one(driver, item, download_dir: Path, timeout: int):
    title = item.get("title") or ""
    url = item["url"]

    before = list_finished_files(download_dir)

    print(f"\nOuverture : {title or url}")
    print(url)

    driver.get(url)
    time.sleep(3)
    accept_cookies_if_present(driver)

    # Premier clic Download
    clicked = click_first_available(driver, DOWNLOAD_BUTTON_XPATHS, timeout=12)
    if not clicked:
        print("Bouton Download introuvable. La page a peut-être changé.")
        return False

    # Parfois Pixabay ouvre une fenêtre modale avec un deuxième bouton Download.
    time.sleep(2)

    downloaded = wait_for_download(download_dir, before, timeout=8)
    if downloaded:
        final_file = rename_downloaded_file(downloaded, title, url)
        print(f"Téléchargé : {final_file.name}")
        return True

    # Deuxième clic éventuel dans la modale.
    click_first_available(driver, DOWNLOAD_BUTTON_XPATHS, timeout=6)

    downloaded = wait_for_download(download_dir, before, timeout=timeout)
    if downloaded:
        final_file = rename_downloaded_file(downloaded, title, url)
        print(f"Téléchargé : {final_file.name}")
        return True

    print("Aucun fichier détecté après le clic.")
    print("Si Pixabay demande une connexion, un captcha ou une confirmation manuelle, fais-la dans Edge puis relance le script.")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", default="Texte collé(149).txt", help="Fichier contenant page,title,url")
    parser.add_argument("--out", default="pixabay_downloads", help="Dossier de téléchargement")
    parser.add_argument("--delay-min", type=float, default=8.0, help="Délai minimum entre deux SFX")
    parser.add_argument("--delay-max", type=float, default=18.0, help="Délai maximum entre deux SFX")
    parser.add_argument("--start", type=int, default=1, help="Commencer au numéro N, 1 = début")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de téléchargements, 0 = tous")
    parser.add_argument("--timeout", type=int, default=90, help="Temps max d'attente d'un téléchargement")
    args = parser.parse_args()

    links_path = Path(args.links)
    download_dir = Path(args.out)
    download_dir.mkdir(parents=True, exist_ok=True)

    if not links_path.exists():
        print(f"Fichier introuvable : {links_path}")
        print("Astuce : renomme ton fichier en links.csv ou donne son chemin avec --links")
        sys.exit(1)

    items = read_links(links_path)
    if not items:
        print("Aucun lien Pixabay trouvé dans le fichier.")
        sys.exit(1)

    start_index = max(args.start - 1, 0)
    items = items[start_index:]

    if args.limit and args.limit > 0:
        items = items[:args.limit]

    print(f"{len(items)} lien(s) à traiter.")
    print(f"Dossier de sortie : {download_dir.resolve()}")

    driver = make_driver(download_dir)

    ok = 0
    failed = 0

    try:
        for i, item in enumerate(items, start=args.start):
            print(f"\n===== {i} / {args.start + len(items) - 1} =====")

            success = download_one(driver, item, download_dir, args.timeout)
            if success:
                ok += 1
            else:
                failed += 1

            delay = random.uniform(args.delay_min, args.delay_max)
            print(f"Pause de {delay:.1f} secondes...")
            time.sleep(delay)

    finally:
        driver.quit()

    print("\nTerminé.")
    print(f"Réussis : {ok}")
    print(f"Échecs : {failed}")
    print(f"Dossier : {download_dir.resolve()}")


if __name__ == "__main__":
    main()