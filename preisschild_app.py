"""
Preisschild Generator – ofen.de (Shopware 6)
=============================================
Einmalige Einrichtung:
    pip install streamlit python-docx requests playwright beautifulsoup4
    python -m playwright install chromium

Starten:
    streamlit run preisschild_generator.py
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Pt, RGBColor, Mm
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from io import BytesIO
import re


# ─────────────────────────────────────────────────────────────
# SCRAPING – exakt auf ofen.de (Shopware 6) abgestimmt
# ─────────────────────────────────────────────────────────────

def _parse_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # ── Modellname ────────────────────────────────────────────
    # <h1 class="product-name-text">...</h1>
    modell = ""
    tag = soup.find("h1", class_="product-name-text")
    if tag:
        modell = tag.get_text(separator=" ", strip=True)
    if not modell:
        tag = soup.find("h1")
        modell = tag.get_text(separator=" ", strip=True) if tag else ""

    # ── Aktueller Preis ───────────────────────────────────────
    # <p class="product-detail-price with-list-price">289,00 €</p>
    # oder <p class="product-detail-price">289,00 €</p>
    preis_aktuell = ""
    tag = soup.find("p", class_="product-detail-price")
    if tag:
        # Nur den ersten Textknoten nehmen (nicht MwSt-Hinweis)
        raw = tag.get_text(separator="|", strip=True).split("|")[0]
        preis_aktuell = raw.replace("\xa0", " ").replace("*", "").strip()

    # ── Streichpreis ──────────────────────────────────────────
    # <span class="list-price-price">349,00 €</span>
    preis_alt = ""
    tag = soup.find("span", class_="list-price-price")
    if tag:
        preis_alt = tag.get_text(strip=True).replace("\xa0", " ").replace("*", "").strip()

    # ── Artikelnummer ─────────────────────────────────────────
    # <tr class="properties-row">
    #   <th class="properties-label">Artikel-Nr.:</th>
    #   <td class="properties-value"><span>7036645</span></td>
    # </tr>
    artikelnummer = ""
    for row in soup.find_all("tr", class_="properties-row"):
        th = row.find("th", class_="properties-label")
        if th and "Artikel-Nr" in th.get_text():
            td = row.find("td", class_="properties-value")
            if td:
                artikelnummer = td.get_text(strip=True)
                break

    # Fallback: freier Text-Scan
    if not artikelnummer:
        m = re.search(
            r"Artikel-?Nr\.?\s*[:\-]?\s*([A-Za-z0-9\-\.]+)",
            soup.get_text(), re.I
        )
        artikelnummer = m.group(1) if m else ""

    # ── Produktbild ───────────────────────────────────────────
    # Hauptbild sitzt meist in .product-detail-media oder .cms-image
    img_url = ""

    # 1) Klassen-Suche
    for container_cls in [
        "product-detail-media",
        "product-detail-images-container",
        "gallery-slider-thumbnails",
        "cms-block-image",
    ]:
        container = soup.find(class_=re.compile(container_cls, re.I))
        if container:
            img = container.find("img")
            if img:
                src = (img.get("src") or img.get("data-src")
                       or img.get("data-lazy-src") or "")
                if src and re.search(r"\.(jpg|jpeg|png|webp)", src, re.I):
                    img_url = src if src.startswith("http") else "https:" + src
                    break

    # 2) Fallback: größtes Bild der Seite (kein Logo/Icon)
    if not img_url:
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "")
            if (src
                    and re.search(r"\.(jpg|jpeg|png|webp)", src, re.I)
                    and "logo" not in src.lower()
                    and "icon" not in src.lower()
                    and "modul" not in src.lower()):          # Zubehör-Bilder überspringen
                img_url = src if src.startswith("http") else "https:" + src
                break

    return modell, artikelnummer, preis_aktuell, preis_alt, img_url


def _fetch_with_playwright(url: str):
    """Echter Browser – überwindet Cloudflare & Co."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="de-DE",
            ).new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2_000)   # JS-Rendering abwarten
            html = page.content()
            browser.close()
        return html
    except Exception as e:
        return None


def _fetch_with_requests(url: str):
    """Einfacher HTTP-Fallback."""
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "de-DE,de;q=0.9",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def scrape_product_info(url: str):
    html = _fetch_with_playwright(url) or _fetch_with_requests(url)
    if not html:
        return "", "", "", "", ""
    return _parse_html(html)


# ─────────────────────────────────────────────────────────────
# WORD-DATEI ERSTELLEN
# ─────────────────────────────────────────────────────────────

def create_word_file(modell, artikelnummer, preis_aktuell, preis_alt, img_url):
    doc = Document()
    section = doc.sections[0]
    section.page_width        = Mm(210)
    section.page_height       = Mm(297)
    section.orientation       = WD_ORIENT.PORTRAIT
    section.top_margin        = Mm(20)
    section.bottom_margin     = Mm(20)
    section.left_margin       = Mm(31)
    section.right_margin      = Mm(31)

    # Globale Schriftart
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")

    # ── A5-Rahmen-Tabelle ─────────────────────────────────────
    table = doc.add_table(rows=1, cols=1)
    table.autofit    = False
    table.alignment  = WD_TABLE_ALIGNMENT.CENTER

    # Innenabstände auf 0 setzen
    tbl_pr = table._tbl.tblPr
    tbl_cell_mar = OxmlElement("w:tblCellMar")
    for side in ["top", "left", "bottom", "right"]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), "0")
        el.set(qn("w:type"), "dxa")
        tbl_cell_mar.append(el)
    tbl_pr.append(tbl_cell_mar)

    cell = table.rows[0].cells[0]
    table.columns[0].width  = Mm(148)
    table.rows[0].height    = Mm(210)

    # Schneide-Rahmen (gepunktet, hellgrau)
    tcPr    = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ["top", "left", "bottom", "right"]:
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"),   "dotted")
        el.set(qn("w:sz"),    "5")
        el.set(qn("w:color"), "E0E0E0")
        borders.append(el)
    tcPr.append(borders)

    # ── Hintergrundgrafik ─────────────────────────────────────
    try:
        bg_url = "https://backend.ofen.de/media/image/63/2e/5c/Grafik-fuer-Preisschildchen-unten.png"
        bg_r   = requests.get(bg_url, timeout=10)
        bg_r.raise_for_status()
        p_bg = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()
        p_bg.clear()
        p_bg.add_run().add_picture(BytesIO(bg_r.content), width=Mm(148), height=Mm(210))
        p_bg.alignment = 1   # zentriert
    except Exception:
        pass

    # ── Produktbild ───────────────────────────────────────────
    if img_url:
        try:
            img_r = requests.get(img_url, timeout=10)
            img_r.raise_for_status()
            p_img = cell.add_paragraph()
            p_img.alignment = 1
            p_img.add_run().add_picture(BytesIO(img_r.content), width=Mm(80))
        except Exception:
            cell.add_paragraph("(Produktbild nicht ladbar)")
    else:
        cell.add_paragraph("(Kein Produktbild)")

    # ── Textblock ─────────────────────────────────────────────
    p = cell.add_paragraph()
    p.alignment = 1   # zentriert

    r1 = p.add_run(modell + "\n")
    r1.font.size = Pt(16)
    r1.font.bold = True

    if artikelnummer:
        r2 = p.add_run(f"Art.-Nr.: {artikelnummer}\n")
        r2.font.size = Pt(10)

    p.add_run("\n").font.size = Pt(4)   # kleiner Abstand

    # Aktueller Preis – groß, rot
    r3 = p.add_run(preis_aktuell + "\n")
    r3.font.size       = Pt(26)
    r3.font.bold       = True
    r3.font.color.rgb  = RGBColor(200, 0, 0)

    # Streichpreis – klein, grau, durchgestrichen
    if preis_alt:
        r4 = p.add_run(f"statt {preis_alt}")
        r4.font.size       = Pt(14)
        r4.font.strike     = True
        r4.font.color.rgb  = RGBColor(120, 120, 120)

    # Speichern
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out


# ─────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="Preisschild Generator – ofen.de", page_icon="🧾")
st.title("🧾 Preisschild Generator – ofen.de")

# Session State initialisieren
for key in ["modell", "artikelnummer", "preis_aktuell", "preis_alt", "img_url"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# ── Schritt 1: URL ────────────────────────────────────────────
st.markdown("### 🔗 Schritt 1: Produkt-URL eingeben")
url = st.text_input(
    "Produkt-URL von ofen.de",
    placeholder="https://www.ofen.de/...",
)

if url and st.button("🔍 Daten automatisch laden"):
    with st.spinner("Seite wird geladen …"):
        m, a, p, pa, i = scrape_product_info(url)
    st.session_state["modell"]        = m
    st.session_state["artikelnummer"] = a
    st.session_state["preis_aktuell"] = p
    st.session_state["preis_alt"]     = pa
    st.session_state["img_url"]       = i

    if p:
        st.success("✅ Produktdaten geladen!")
    else:
        st.warning(
            "⚠️ Preis nicht automatisch erkannt. "
            "Bitte unten manuell eintragen."
        )

# ── Schritt 2: Daten prüfen / ergänzen ───────────────────────
st.markdown("### ✏️ Schritt 2: Daten prüfen / ergänzen")

col1, col2 = st.columns(2)
with col1:
    modell = st.text_input(
        "Artikelbezeichnung *",
        value=st.session_state["modell"],
        placeholder="z. B. Kugelgrill Napoleon PRO22K-LEG-3",
    )
    artikelnummer = st.text_input(
        "Artikelnummer",
        value=st.session_state["artikelnummer"],
        placeholder="z. B. 7036645",
    )
    preis_aktuell = st.text_input(
        "Aktueller Preis *",
        value=st.session_state["preis_aktuell"],
        placeholder="z. B. 289,00 €",
    )
with col2:
    preis_alt = st.text_input(
        "Streichpreis (leer = kein Streichpreis)",
        value=st.session_state["preis_alt"],
        placeholder="z. B. 349,00 €",
    )
    img_url = st.text_input(
        "Bild-URL (optional)",
        value=st.session_state["img_url"],
        placeholder="https://www.ofen.de/media/...",
    )
    if img_url:
        st.image(img_url, width=200)

st.caption("_Felder mit * sind Pflichtfelder._")

# ── Schritt 3: Erstellen ──────────────────────────────────────
st.markdown("### 📄 Schritt 3: Preisschild erstellen")

if st.button("📄 Preisschild erstellen", type="primary"):
    if not modell:
        st.error("❌ Bitte Artikelbezeichnung eingeben.")
    elif not preis_aktuell:
        st.error("❌ Bitte aktuellen Preis eingeben.")
    else:
        with st.spinner("Word-Datei wird erstellt …"):
            file = create_word_file(
                modell, artikelnummer, preis_aktuell, preis_alt, img_url
            )
        st.download_button(
            label="⬇️ Preisschild herunterladen (.docx)",
            data=file,
            file_name="preisschild_A5.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
        )
        st.info(
            "**Hinweis in Word:**\n\n"
            "1. Rechtsklick auf das schwarze Banner (ofen.de-Logo)\n"
            "2. → **Textumbruch** → **Hinter den Text**\n"
            "3. Drucken – fertig ✅"
        )
