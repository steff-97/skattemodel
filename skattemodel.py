import streamlit as st
import pandas as pd
import numpy as np

# Kommuneskat og institutionsbetaling (forkortet eksempel)
kommuneskat_liste = {
    "København": 23.50, "Frederiksberg": 24.57, "Aarhus": 24.52
}

institutionsbetaling = {
    "København": {"0-2": 47952, "3-5": 27804},
    "Frederiksberg": {"0-2": 44940, "3-5": 24408},
    "Aarhus": {"0-2": 46189, "3-5": 25399}
}

# Skatteparametre
personfradrag = 48000
am_bidrag_pct = 0.08
bundskat_pct = 0.1215
topskat_pct = 0.15
topskat_grænse = 568900
beskæftigelsesfradrag_pct = 0.123
beskæftigelsesfradrag_maks = 55600
jobfradrag_pct = 0.045
jobfradrag_bundgrænse = 224500
jobfradrag_maks = 2900
enlig_forsorger_fradrag_pct = 0.115
enlig_forsorger_fradrag_maks = 48300

# Kørselsfradrag

def beregn_kørselsfradrag(afstand_km, antal_dage, yderkommune=False, bro_ture=None):
    fradrag = 0
    daglig_returtur = afstand_km * 2
    for km in range(25, min(121, int(daglig_returtur)) + 1):
        fradrag += (2.47 if yderkommune else 2.23) * antal_dage
    for km in range(121, int(daglig_returtur) + 1):
        fradrag += (2.47 if yderkommune else 1.12) * antal_dage

    bro_fradrag = {
        'storebælt_bil': 110,
        'storebælt_tog': 15,
        'øresund_bil': 50,
        'øresund_tog': 8,
    }
    if bro_ture:
        for bro, antal in bro_ture.items():
            fradrag += bro_fradrag.get(bro, 0) * antal

    return fradrag

# Beregn ydelser og tilskud

def su(indkomst, modtager_su):
    return 80000 if modtager_su and indkomst < 350000 else 60000 if modtager_su else 0

def boligstøtte(indkomst, modtager_boligstøtte):
    if not modtager_boligstøtte:
        return 0
    return 12000 if indkomst < 300000 else 6000 if indkomst < 400000 else 0

def børne_unge_tilskud(indkomst, børn):
    ydelse_pr_barn = {(0, 2): 5292 * 4, (3, 6): 4191 * 4, (7, 14): 3297 * 4, (15, 17): 1099 * 12}
    samlet = sum(
        ydelse for barn in børn
        for (start, slut), ydelse in ydelse_pr_barn.items()
        if start <= barn['alder'] <= slut
    )
    aftrap = max(0, indkomst - 917000) * 0.02
    return max(0, samlet - aftrap)

def friplads_tilskud(indkomst, børn, kommune, er_enlig):
    grundgrænse = 208101
    ekstra_barn_tillæg = 7000
    enlig_tillæg = 72822 if er_enlig else 0
    direkte_tilskud_aar = 0
    for i, barn in enumerate(børn):
        alder = barn['alder']
        gruppe = "0-2" if alder <= 2 else "3-5" if alder <= 5 else None
        if gruppe is None: continue
        betaling_aar = institutionsbetaling.get(kommune, {}).get(gruppe, 0)
        barn_grænse = grundgrænse + enlig_tillæg + i * ekstra_barn_tillæg
        forskel = max(0, indkomst - barn_grænse)
        trin = forskel // 4614
        egenbetaling_pct = min(0.05 + trin * 0.01, 1.0)
        tilskud = betaling_aar * (1 - egenbetaling_pct)
        direkte_tilskud_aar += tilskud
    return direkte_tilskud_aar

def boligsikring(indkomst, boligudgift, antal_børn, har_børn_under_18=True):
    grænse = 167900 + max(0, antal_børn - 1) * 44200
    fradrag = max(0, indkomst - grænse) * 0.18
    tilskud = 0.6 * boligudgift - fradrag
    maks = 49716
    if not har_børn_under_18:
        maks = min(maks, boligudgift * 0.15)
    tilskud = min(tilskud, maks)
    if tilskud / 12 < 304 or boligudgift - tilskud < 28300:
        return 0
    return round(tilskud / 12) * 12

# Streamlit app

st.set_page_config(page_title="Dansk Skattemodel 2025", layout="wide")
st.title("🇩🇰 Dansk Skattemodel 2025")

kommune = st.selectbox("Vælg din kommune", sorted(kommuneskat_liste.keys()))
kommuneskat_pct = kommuneskat_liste[kommune] / 100
løn = st.number_input("Indtast din årlige løn", value=450000)
su_check = st.checkbox("Modtager du SU?")
lejebolig = st.checkbox("Bor du i lejebolig?")
boligudgift = st.number_input("Din årlige boligudgift", value=60000) if lejebolig else 0
antal_børn = st.number_input("Antal børn", min_value=0, step=1)
børn_aldre = [st.slider(f"Alder på barn {i+1}", 0, 17, 4) for i in range(antal_børn)]
er_enlig = st.checkbox("Er du enlig forsørger?")

# Transport
st.write("### Transport og kørselsfradrag")
afstand_km = st.number_input("Hvor mange km er der til arbejde (én vej)?", value=0)
antal_dage = st.number_input("Hvor mange dage om året kører du til arbejde?", value=216)
yderkommune = st.checkbox("Bor du i en yderkommune eller på en småø?")
brovalg = {
    'storebælt_bil': st.number_input("Antal årlige ture over Storebælt (bil)", value=0),
    'storebælt_tog': st.number_input("Antal årlige ture over Storebælt (tog)", value=0),
    'øresund_bil': st.number_input("Antal årlige ture over Øresund (bil)", value=0),
    'øresund_tog': st.number_input("Antal årlige ture over Øresund (tog)", value=0)
}

if st.button("Beregn skat og tilskud"):
    børn = [{'alder': a} for a in børn_aldre]
    su_beløb = su(løn, su_check)
    børneydelse = børne_unge_tilskud(løn, børn)
    boligstøtte_beløb = boligstøtte(løn, True)
    friplads = friplads_tilskud(løn, børn, kommune, er_enlig)
    boligsikring_beløb = boligsikring(løn, boligudgift, antal_børn, any(b['alder'] < 18 for b in børn)) if lejebolig else 0
    kørselsfradrag = beregn_kørselsfradrag(afstand_km, antal_dage, yderkommune, brovalg)

    # Skat
    am_bidrag = løn * am_bidrag_pct
    besk_fradrag = min(beskæftigelsesfradrag_pct * løn, beskæftigelsesfradrag_maks)
    jobfradrag = min(jobfradrag_pct * max(0, løn - jobfradrag_bundgrænse), jobfradrag_maks)
    enlig_fradrag = min(løn * enlig_forsorger_fradrag_pct, enlig_forsorger_fradrag_maks) if er_enlig else 0
    ligning_fradrag = besk_fradrag + jobfradrag + enlig_fradrag + kørselsfradrag
    skattepligtig = max(0, løn - am_bidrag - personfradrag)
    bundskat = skattepligtig * bundskat_pct
    topskat = max(0, (skattepligtig - (topskat_grænse - personfradrag)) * topskat_pct)
    kommuneskat = max(0, (skattepligtig - ligning_fradrag) * kommuneskat_pct)
    total_skat = am_bidrag + bundskat + topskat + kommuneskat

    brutto = løn + su_beløb + børneydelse + boligstøtte_beløb + friplads + boligsikring_beløb
    netto = brutto - total_skat
    effektiv_skat = total_skat / brutto * 100

    # Output
    st.subheader("Resultater")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Bruttoindkomst", f"{brutto:,.0f} kr")
        st.metric("Nettoindkomst", f"{netto:,.0f} kr")
        st.metric("Effektiv skat", f"{effektiv_skat:.2f}%")
    with col2:
        st.write("### Tilskud og fradrag")
        st.write(f"Børneydelse: {børneydelse:,.0f} kr")
        st.write(f"Friplads: {friplads:,.0f} kr")
        st.write(f"SU: {su_beløb:,.0f} kr")
        st.write(f"Boligsikring: {boligsikring_beløb:,.0f} kr")
        st.write(f"Kørselsfradrag: {kørselsfradrag:,.0f} kr")
        st.write(f"Besparelse i skat pga. kørselsfradrag: {kørselsfradrag * kommuneskat_pct:,.0f} kr")
