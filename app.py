import streamlit as st
import pandas as pd
import re
from pdfminer.high_level import extract_text
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging
from decimal import Decimal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class InvoiceData:
    page_number: int
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    departure_point: Optional[str]
    destination: Optional[str]
    total_price: Optional[str]

class InvoiceProcessor:
    def __init__(self):
        self.price_pattern = r"Solde restant à payer\s*([\d,.]+)\s*€"
        self.invoice_number_pattern = r"FACTURE N°\s*(\S+)"
        self.date_pattern = r"Clichy, le (\d{2}/\d{2}/\d{4})"
        self.departure_pattern = r"Départ :\s*(.+)"
        self.destination_pattern = r"Arrivée :\s*(.+)"

    def extract_field(self, pattern: str, text: str) -> List[str]:
        return re.findall(pattern, text)

    def parse_price(self, price_str: str) -> Optional[Decimal]:
        try:
            if price_str:
                # Remove currency symbol and spaces, replace comma with dot
                cleaned_price = price_str.replace('€', '').replace(' ', '').replace(',', '.')
                return Decimal(cleaned_price)
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing price {price_str}: {e}")
            return None

    def process_page(self, page_text: str, page_number: int) -> List[InvoiceData]:
        try:
            invoice_numbers = self.extract_field(self.invoice_number_pattern, page_text)
            invoice_dates = self.extract_field(self.date_pattern, page_text)
            departure_points = self.extract_field(self.departure_pattern, page_text)
            destinations = self.extract_field(self.destination_pattern, page_text)
            total_prices = self.extract_field(self.price_pattern, page_text)

            results = []
            for i in range(len(invoice_numbers)):
                invoice_data = InvoiceData(
                    page_number=page_number,
                    invoice_number=invoice_numbers[i] if i < len(invoice_numbers) else None,
                    invoice_date=invoice_dates[0] if invoice_dates else None,
                    departure_point=departure_points[i] if i < len(departure_points) else None,
                    destination=destinations[i] if i < len(destinations) else None,
                    total_price=f"{total_prices[0].replace('.', ',')} €" if total_prices else None
                )
                results.append(invoice_data)
            return results
        except Exception as e:
            logger.error(f"Error processing page {page_number}: {e}")
            return []

class StreamlitApp:
    def __init__(self):
        self.processor = InvoiceProcessor()
        self.initialize_session_state()
        self.setup_page_config()

    def initialize_session_state(self):
        if "uploaded_files" not in st.session_state:
            st.session_state.uploaded_files = {}
        if "extracted_data" not in st.session_state:
            st.session_state.extracted_data = pd.DataFrame()
        if "should_rerun" not in st.session_state:
            st.session_state.should_rerun = False

    def setup_page_config(self):
        st.set_page_config(
            page_title="Analyseur de PDF Askifea",
            page_icon="📄",
            layout="wide"
        )
        st.title("Analyseur de PDF Askifea")
        st.markdown("### Téléchargez plusieurs fichiers PDF pour les analyser")

    def process_uploaded_file(self, uploaded_file) -> pd.DataFrame:
        try:
            pdf_text = extract_text(uploaded_file)
            pages = pdf_text.split('\x0c')
            all_invoice_data = []
            
            for page_num, page_text in enumerate(pages, start=1):
                page_data = self.processor.process_page(page_text, page_num)
                all_invoice_data.extend(page_data)

            return pd.DataFrame([vars(invoice) for invoice in all_invoice_data])
        except Exception as e:
            logger.error(f"Error processing file {uploaded_file.name}: {e}")
            st.error(f"Erreur lors du traitement du fichier {uploaded_file.name}")
            return pd.DataFrame()

    def create_invoice_table(self, df: pd.DataFrame):
        if df.empty:
            return

        st.markdown("#### Liste des factures analysées")
        
        for index, row in df.iterrows():
            cols = st.columns([1, 2, 2, 2, 2, 2, 1])
            cols[0].write(row["page_number"])
            cols[1].write(row["invoice_number"])
            cols[2].write(row["invoice_date"])
            cols[3].write(row["departure_point"])
            cols[4].write(row["destination"])
            cols[5].write(row["total_price"])
            
            if cols[6].button("🗑️", key=f"delete_{index}"):
                self.delete_invoice(row["invoice_number"])
                st.session_state.should_rerun = True
                st.rerun()

    def calculate_summary(self, df: pd.DataFrame):
        if df.empty:
            return

        total_invoices = len(df["invoice_number"].dropna())
        total_cost = sum(
            self.processor.parse_price(price) or Decimal('0')
            for price in df["total_price"].dropna()
        )

        st.markdown("### Résumé")
        summary_data = pd.DataFrame({
            "Statistiques": [
                f"Nombre total de factures: {total_invoices}",
                f"Montant total: {total_cost:.2f} €",
            ]
        })
        st.table(summary_data)

    def delete_invoice(self, invoice_number: str):
        st.session_state.extracted_data = st.session_state.extracted_data[
            st.session_state.extracted_data["invoice_number"] != invoice_number
        ]
        # Remove from uploaded_files if present
        for file_name, data in list(st.session_state.uploaded_files.items()):
            if invoice_number in data["invoice_number"].values:
                del st.session_state.uploaded_files[file_name]

    def run(self):
        uploaded_files = st.file_uploader(
            "Téléchargez des fichiers PDF",
            type="pdf",
            accept_multiple_files=True
        )

        if uploaded_files:
            self.handle_uploaded_files(uploaded_files)
            
        if not st.session_state.extracted_data.empty:
            self.create_invoice_table(st.session_state.extracted_data)
            self.calculate_summary(st.session_state.extracted_data)

    def handle_uploaded_files(self, uploaded_files):
        current_files = {file.name for file in uploaded_files}
        
        # Remove files that are no longer present
        files_to_remove = set(st.session_state.uploaded_files.keys()) - current_files
        for file_name in files_to_remove:
            del st.session_state.uploaded_files[file_name]
        
        # Process new files
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.uploaded_files:
                new_data = self.process_uploaded_file(uploaded_file)
                if not new_data.empty:
                    st.session_state.uploaded_files[uploaded_file.name] = new_data
                    st.session_state.extracted_data = pd.concat(
                        [st.session_state.extracted_data, new_data],
                        ignore_index=True
                    )

if __name__ == "__main__":
    app = StreamlitApp()
    app.run()
