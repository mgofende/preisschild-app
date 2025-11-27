import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# -----------------------------
# Funktion: ofen.de Daten auslesen
# -----------------------------
def scrape_ofen(url, artikelnummer=None, ean=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    modell_tag = soup.find('h1', class_='product--title') or soup.find('h1', class_='product-header-title')
    modell = modell_tag.text.strip() if modell_tag else None
    
    if not artikelnummer:
        all_text = soup.get_text()
        match = re.search(r'Artikel-?Nr\.?:\s*(\d+)', all_text)
        artikelnummer = match.group(1) if match else None
    
    preis_tag = soup.find('span', class_='price--content') or soup.find('div', class_='price--current')
    preis = preis_tag.text.strip() if preis_tag else None
    
    uvp_tag = soup.find('span', class_='price--line-through') or soup.find('span', class_='price-old')
    uvp = uvp_tag.text.strip() if uvp_tag else None
    
    liefer_tag = soup.find(text=re.compile(r"Lieferzeit"))
    lieferzeit = liefer_tag.strip() if liefer_tag else None
    
    if not ean:
        all_text = soup.get_text()
        ean_match = re.search(r'\b(\d{13})\b', all_text)
        ean = ean_match.group(1) if ean_match else None
    
    return {
        "Modell": modell,
        "Artikelnummer": artikelnummer,
        "EAN": ean,
        "Preis_Ofen": preis,
        "UVP_Ofen": uvp,
        "Lieferzeit_Ofen": lieferzeit
    }

# -----------------------------
# Shop Scraper Funktionen (Beispiele)
# -----------------------------
def scrape_feuerdepot():
    url = "https://www.feuerdepot.de/pelletofen/pelletofen-la-nordica-extraflame-klaudia-plus-5-0-8-kw/?number=1286850"
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    
    name_tag = soup.find('h1', class_='product--title') or soup.find('h1')
    name = name_tag.text.strip() if name_tag else None
    
    uvp_tag = soup.find('span', class_='price--line-through')
    uvp = uvp_tag.text.strip() if uvp_tag else None
    
    preis_tag = soup.find('span', class_='price--content')
    preis = preis_tag.text.strip() if preis_tag else None
    
    liefer_tag = soup.find(text=re.compile(r'Lieferzeit'))
    lieferzeit = liefer_tag.strip() if liefer_tag else None
    
    artnr_tag = soup.find(text=re.compile(r'Artikel-Nr'))
    artnr_match = re.search(r'(\d+)', artnr_tag) if artnr_tag else None
    artnr = artnr_match.group(1) if artnr_match else None
    
    return {
        "Shop": "Feuerdepot",
        "URL": url,
        "Name": name,
        "UVP": uvp,
        "Preis": preis,
        "Lieferzeit": lieferzeit,
        "Artikelnummer": artnr,
        "EAN": None
    }

def scrape_kamdi():
    url = "https://www.kamdi24.de/extraflame-klaudia-plus-50-pelletofen-bordeaux"
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    
    name_tag = soup.find('h1', class_='product--title') or soup.find('h1')
    name = name_tag.text.strip() if name_tag else None
    
    preis_tag = soup.find('span', class_='price')
    preis = preis_tag.text.strip() if preis_tag else None
    
    uvp_tag = soup.find('span', class_='old-price')
    uvp = uvp_tag.text.strip() if uvp_tag else None
    
    liefer_tag = soup.find(text=re.compile(r'Lieferzeit'))
    lieferzeit = liefer_tag.strip() if liefer_tag else None
    
    artnr_tag = soup.find(text=re.compile(r'Art.-Nr.'))
    artnr_match = re.search(r'(\d+)', artnr_tag) if artnr_tag else None
    artnr = artnr_match.group(1) if artnr_match else None
    
    return {
        "Shop": "Kamdi24",
        "URL": url,
        "Name": name,
        "UVP": uvp,
        "Preis": preis,
        "Lieferzeit": lieferzeit,
        "Artikelnummer": artnr,
        "EAN": None
    }

def scrape_feuerfuchs():
    url = "https://www.feuer-fuchs.de/suche/?search=Pelletofen+Extraflame+Klaudia+5.0"
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    
    name_tag = soup.find('h1')
    name = name_tag.text.strip() if name_tag else None
    
    uvp_tag = soup.find('span', class_='price--line-through')
    uvp = uvp_tag.text.strip() if uvp_tag else None
    
    preis_tag = soup.find('span', class_='price--content')
    preis = preis_tag.text.strip() if preis_tag else None
    
    liefer_tag = soup.find(text=re.compile(r'Lieferzeit'))
    lieferzeit = liefer_tag.strip() if liefer_tag else None
    
    return {
        "Shop": "Feuer-Fuchs",
        "URL": url,
        "Name": name,
        "UVP": uvp,
        "Preis": preis,
        "Lieferzeit": lieferzeit,
        "Artikelnummer": None,
        "EAN": None
    }

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Preisvergleich Pelletofen", page_icon="🔥")
st.title("🔥 Preisvergleich Pelletofen Extraflame Klaudia 5.0 Evo")

st.markdown("**Gib die ofen.de URL ein und optional Artikelnummer / EAN:**")

ofen_url = st.text_input("ofen.de URL")
artikelnummer = st.text_input("Hersteller Artikelnummer (optional)")
ean = st.text_input("EAN (optional, 13-stellig)")

if st.button("Preissuche starten"):
    with st.spinner("Daten werden geladen..."):
        try:
            product = scrape_ofen(ofen_url, artikelnummer=artikelnummer if artikelnummer else None, ean=ean if ean else None)
            st.subheader("Daten von ofen.de")
            st.write(product)
            
            # Shops durchsuchen
            results = []
            results.append(scrape_feuerdepot())
            results.append(scrape_kamdi())
            results.append(scrape_feuerfuchs())
            
            df = pd.DataFrame(results)
            st.subheader("Preisvergleich Ergebnisse")
            st.dataframe(df)
            
            # CSV Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Ergebnisse als CSV herunterladen",
                data=csv,
                file_name='preisvergleich.csv',
                mime='text/csv'
            )
            
        except Exception as e:
            st.error(f"Fehler: {e}")
