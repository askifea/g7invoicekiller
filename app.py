import streamlit as st
import pandas as pd
import re
from pdfminer.high_level import extract_text

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
            # Take the first match, replace dots with commas
            total_price = total_price_matches[0].replace('.', ',')

        for i in range(len(invoice_numbers)):
            data.append({
                "Numéro de page": page_number,
                "Numéro de facture": invoice_numbers[i] if i < len(invoice_numbers) else None,
                "Date de la facture": invoice_dates[0] if invoice_dates else None,
                "Point de départ": starting_points[i] if i < len(starting_points) else None,
                "Destination": destinations[i] if i < len(destinations) else None,
                "Prix total": total_price
            })
    return pd.DataFrame(data)

# Set up the app title and description (in French)
st.set_page_config(
    page_title="Analyseur de PDF Askifea",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Analyseur de PDF Askifea")
st.write("### Analysez les factures PDF (taxi, G7, ...).")

# File uploader (in French)
uploaded_file = st.file_uploader("Téléchargez un fichier PDF", type="pdf")

if uploaded_file:
    st.write("Traitement de votre fichier...")
    # Extract text from PDF
    pdf_text = extract_text(uploaded_file)
    
    # Process the text to extract invoice data
    invoice_data = extract_invoice_data(pdf_text)

    # Display results (in French)
    st.write("### Données des factures extraites")
    st.dataframe(invoice_data)

    # Download the Excel file (in French)
    output_path = "Factures_Extraites.xlsx"
    invoice_data.to_excel(output_path, index=False)

    with open(output_path, "rb") as file:
        st.download_button(
            label="Télécharger le fichier Excel",
            data=file,
            file_name="Factures_Extraites.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
