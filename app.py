import streamlit as st
import pandas as pd
import re
from pdfminer.high_level import extract_text
from st_aggrid import AgGrid, GridOptionsBuilder

# Function to extract invoice data
def extract_invoice_data(pdf_text):
    pages = pdf_text.split('\x0c')  # Split text by pages
    data = []

    for page_number, page_text in enumerate(pages, start=1):
        # Extract fields using regex
        invoice_numbers = re.findall(r"FACTURE N°\s*(\S+)", page_text)
        invoice_dates = re.findall(r"Clichy, le (\d{2}/\d{2}/\d{4})", page_text)
        starting_points = re.findall(r"Départ :\s*(.+)", page_text)
        destinations = re.findall(r"Arrivée :\s*(.+)", page_text)

        # Extract the total price after "Solde restant à payer" and before the next "€"
        total_price_matches = re.findall(r"Solde restant à payer\s*([\d,.]+)\s*€", page_text)
        total_price = None
        if total_price_matches:
            total_price = total_price_matches[0].replace('.', ',')

        for i in range(len(invoice_numbers)):
            data.append({
                "Numéro de page": page_number,
                "Numéro de facture": invoice_numbers[i] if i < len(invoice_numbers) else None,
                "Date de la facture": invoice_dates[0] if invoice_dates else None,
                "Point de départ": starting_points[i] if i < len(starting_points) else None,
                "Destination": destinations[i] if i < len(destinations) else None,
                "Prix total": f"{total_price} €" if total_price else None
            })
    return pd.DataFrame(data)

# Streamlit app
st.set_page_config(page_title="Analyseur de PDF Askifea", page_icon="📄", layout="wide")
st.title("Analyseur de PDF Askifea")

st.markdown("### Téléchargez plusieurs fichiers PDF pour les analyser")

# Initialize session state to store uploaded files and their data
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "combined_data" not in st.session_state:
    st.session_state.combined_data = pd.DataFrame()

# File uploader for multiple files
uploaded_files = st.file_uploader("Téléchargez des fichiers PDF", type="pdf", accept_multiple_files=True)

# Process newly uploaded files
if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.uploaded_files:
            pdf_text = extract_text(uploaded_file)
            invoice_data = extract_invoice_data(pdf_text)
            st.session_state.uploaded_files[uploaded_file.name] = invoice_data
            st.session_state.combined_data = pd.concat(
                [st.session_state.combined_data, invoice_data], ignore_index=True
            )

# Display Résumé section
if not st.session_state.combined_data.empty:
    # Compute totals for "Résumé"
    total_invoices = len(st.session_state.combined_data["Numéro de facture"].dropna())
    total_cost = st.session_state.combined_data["Prix total"].str.replace(" €", "").str.replace(",", ".").astype(float).sum()

    st.markdown("### Résumé")
    total_data = pd.DataFrame(
        {
            "": [
                f"Total factures: {total_invoices}",
                f"Total coût: {total_cost:.2f} €",
            ]
        }
    )
    st.table(total_data)

# Display combined data as a filterable table
st.markdown("#### Liste des factures analysées")
if not st.session_state.combined_data.empty:
    # Build filterable AgGrid table
    gb = GridOptionsBuilder.from_dataframe(st.session_state.combined_data)
    gb.configure_pagination(paginationAutoPageSize=True)  # Enable pagination
    gb.configure_default_column(editable=False, filter=True)  # Enable filtering
    grid_options = gb.build()

    # Display the table
    AgGrid(
        st.session_state.combined_data,
        gridOptions=grid_options,
        height=800,
        theme="streamlit",
    )

# Save the combined data to Excel
if not st.session_state.combined_data.empty:
    output_file = "Factures_Extraites_Multifichiers.xlsx"
    st.session_state.combined_data.to_excel(output_file, index=False)

    # Provide a download link for the Excel file
    with open(output_file, "rb") as file:
        st.download_button(
            label="Télécharger le fichier Excel combiné",
            data=file,
            file_name="Factures_Extraites_Multifichiers.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
