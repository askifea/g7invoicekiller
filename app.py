import streamlit as st
import re
from PyPDF2 import PdfReader, PdfWriter
from pdfminer.high_level import extract_text
import io
import pandas as pd

st.set_page_config(page_title="Renommer & Fusionner les Factures G7", page_icon="📄", layout="wide")
st.title("📑 Séparer, Renommer et Fusionner les Factures G7")

# ---------- Extraction Function ----------
def extract_invoice_data(text, filename):
    pages = text.split('\x0c')
    results = []

    for idx, page in enumerate(pages):
        date_match = re.search(r"Clichy,\s*le\s*(\d{2}/\d{2}/\d{4})", page)
        depart_match = re.search(r"Départ\s*:\s*(.*)", page)
        arrivee_match = re.search(r"Arrivée\s*:\s*(.*)", page)

        # Extraction fiable du prix
        prix = "-"
        for line in page.splitlines():
            if "Montant" in line and "€" in line:
                match = re.findall(r"([\d\s,.]+)\s*€", line)
                if match:
                    raw = match[-1].strip().replace(" ", "").replace(",", ".")
                    prix = f"{raw} €"
                    break

        if date_match or depart_match or arrivee_match:
            if date_match:
                raw_date = date_match.group(1)
                date_display = raw_date
                date_filename = raw_date.replace("/", "_")
            else:
                date_display = "-"
                date_filename = "date"

            depart_raw = depart_match.group(1).strip() if depart_match else "depart"
            arrivee_raw = arrivee_match.group(1).strip() if arrivee_match else "arrivee"
            depart = re.sub(r"[^\w]", "_", depart_raw)
            arrivee = re.sub(r"[^\w]", "_", arrivee_raw)

            filename_clean = f"{date_filename}_{depart}_{arrivee}.pdf"

            results.append({
                "page": idx,
                "Date de la facture": date_display,
                "Point de départ": depart_raw,
                "Destination": arrivee_raw,
                "Prix total": prix,
                "Nom du fichier": filename_clean
            })

    return results

# ---------- Upload ----------
uploaded_files = st.file_uploader("📎 Uploadez un ou plusieurs fichiers PDF", type="pdf", accept_multiple_files=True)

renamed_files = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.read()
        file_io = io.BytesIO(file_bytes)

        text = extract_text(io.BytesIO(file_bytes))
        metadata = extract_invoice_data(text, uploaded_file.name)

        reader = PdfReader(file_io)
        if not metadata:
            st.warning(f"❗️Aucune facture détectée dans {uploaded_file.name}")
        else:
            for meta in metadata:
                writer = PdfWriter()
                writer.add_page(reader.pages[meta["page"]])

                output = io.BytesIO()
                writer.write(output)
                output.seek(0)

                renamed_files.append((meta, output))

# ---------- Selection Area + Output ----------
if renamed_files:
    st.markdown("### ✅ Sélectionnez les factures à fusionner")
    selected_items = []

    # 🔽 Tri et filtre
    col1, col2 = st.columns([1, 3])
    with col1:
        sort_by_destination = st.checkbox("Trier par destination")
    with col2:
        destination_filter = st.text_input("🔎 Filtrer par destination", "")

    # Appliquer filtre et tri
    filtered_files = [
        (meta, buffer) for meta, buffer in renamed_files
        if destination_filter.lower() in meta["Destination"].lower()
    ]
    sorted_files = sorted(filtered_files, key=lambda x: x[0]["Destination"]) if sort_by_destination else filtered_files

    for idx, (meta, buffer) in enumerate(sorted_files):
        label = (
            f"**{meta['Date de la facture']}** | "
            f"{meta['Point de départ']} → {meta['Destination']} | "
            f"{meta['Prix total']}"
        )
        if st.checkbox(label, key=f"select_{idx}"):
            selected_items.append((meta, buffer))

    # ---------- Table of Selected Invoices ----------
    if selected_items:
        st.markdown("### 📊 Aperçu des factures sélectionnées")

        selected_meta = [meta for meta, _ in selected_items]
        df_selected = pd.DataFrame(selected_meta).drop(columns=["Nom du fichier"])

        st.dataframe(df_selected, use_container_width=True)

        # ---------- Show Total Price ----------
        try:
            total = df_selected["Prix total"].str.replace(" €", "").str.replace(",", ".").astype(float).sum()
            st.success(f"💰 Total sélectionné : {total:.2f} €")
        except Exception:
            st.warning("❗️ Impossible de calculer le total.")

        # ---------- Excel Export ----------
        excel_output = io.BytesIO()
        df_selected.to_excel(excel_output, index=False)
        excel_output.seek(0)

        st.download_button(
            label="📊 Télécharger tableau Excel",
            data=excel_output,
            file_name="Factures_Selectionnees.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ---------- Merge PDF & Download ----------
        merger = PdfWriter()
        for _, buf in selected_items:
            buf.seek(0)
            merger.append(buf)

        merged_output = io.BytesIO()
        merger.write(merged_output)
        merger.close()
        merged_output.seek(0)

        st.markdown("### 📥 Télécharger la sélection fusionnée")
        st.download_button(
            label="📎 Télécharger PDF fusionné",
            data=merged_output,
            file_name="Factures_Renommees_Merge.pdf",
            mime="application/pdf"
        )
    else:
        st.info("🔘 Cochez les factures à fusionner.")
