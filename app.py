import streamlit as st
import pandas as pd
import re
from pdfminer.high_level import extract_text

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
                "Prix total": total_price
            })
    return pd.DataFrame(data)

# Streamlit app
st.set_page_config(page_title="Analyseur de PDF Askifea", page_icon="📄", layout="wide")
st.title("Analyseur de PDF Askifea")
st.write("### Téléchargez plusieurs fichiers PDF pour les analyser")

# File uploader for multiple files
uploaded_files = st.file_uploader("Téléchargez des fichiers PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    st.write("Traitement de vos fichiers...")
    combined_data = pd.DataFrame()  # Initialize an empty DataFrame

    # Process each file
    for uploaded_file in uploaded_files:
        # Extract text from the PDF
        pdf_text = extract_text(uploaded_file)
        # Process the PDF and extract data
        invoice_data = extract_invoice_data(pdf_text)
        # Append the data to the combined DataFrame
        combined_data = pd.concat([combined_data, invoice_data], ignore_index=True)

    # Display combined data
    st.write("### Données extraites")
    st.dataframe(combined_data)

    # Save the combined data to Excel
    output_file = "Factures_Extraites_Multifichiers.xlsx"
    combined_data.to_excel(output_file, index=False)

    # Provide a download link for the Excel file
    with open(output_file, "rb") as file:
        st.download_button(
            label="Télécharger le fichier Excel combiné",
            data=file,
            file_name="Factures_Extraites_Multifichiers.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
