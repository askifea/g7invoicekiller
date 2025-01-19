import solara
import pandas as pd
import re
from pdfminer.high_level import extract_text
from PyPDF2 import PdfMerger
import io


@solara.component
def InvoiceProcessor():
    files, set_files = solara.use_state({})
    extracted_data, set_extracted_data = solara.use_state(pd.DataFrame())
    alerts, set_alerts = solara.use_state([])
    filters, set_filters = solara.use_state({})
    sort_column, set_sort_column = solara.use_state(None)
    sort_ascending, set_sort_ascending = solara.use_state(True)
    merged_pdf_data, set_merged_pdf_data = solara.use_state(None)

    def extract_invoice_data(pdf_text):
        """Extract structured invoice data from PDF text."""
        pages = pdf_text.split('\x0c')
        data = []

        for page_number, page_text in enumerate(pages, start=1):
            invoice_numbers = re.findall(r"FACTURE N°\s*(\S+)", page_text)
            invoice_dates = re.findall(r"Clichy, le (\d{2}/\d{2}/\d{4})", page_text)
            starting_points = re.findall(r"Départ :\s*(.+)", page_text)
            destinations = re.findall(r"Arrivée :\s*(.+)", page_text)
            total_price_matches = re.findall(r"Solde restant à payer\s*([\d,.]+)\s*€", page_text)

            total_price = None
            if total_price_matches:
                total_price = total_price_matches[0].replace('.', ',')

            for i in range(len(invoice_numbers)):
                data.append({
                    "Page #": page_number,
                    "Numéro de facture": invoice_numbers[i] if i < len(invoice_numbers) else None,
                    "Date de la facture": invoice_dates[0] if invoice_dates else None,
                    "Point de départ": starting_points[i] if i < len(starting_points) else None,
                    "Destination": destinations[i] if i < len(destinations) else None,
                    "Prix total": f"{total_price} €" if total_price else None,
                })
        return pd.DataFrame(data)

    def handle_files(uploaded_files):
        """Process uploaded files and extract invoice data."""
        if not uploaded_files:
            return

        new_files = files.copy()
        new_data = extracted_data.copy() if not extracted_data.empty else pd.DataFrame()
        new_alerts = alerts.copy()

        for file_data in uploaded_files:
            filename = None
            try:
                filename = file_data["name"]
                file_obj = file_data["file_obj"]
                content = file_obj.read()

                if not filename.lower().endswith('.pdf'):
                    new_alerts.append(f"⚠️ {filename} is not a valid PDF. Skipping...")
                    continue

                new_files[filename] = content
                pdf_text = extract_text(io.BytesIO(content))

                if not pdf_text.strip():
                    new_alerts.append(f"⚠️ {filename} is empty or unreadable. Skipping...")
                    continue

                invoice_data = extract_invoice_data(pdf_text)
                new_data = pd.concat([new_data, invoice_data], ignore_index=True)

            except Exception as e:
                new_alerts.append(f"❌ Error processing {filename}: {e}" if filename else "❌ Error processing a file.")

        set_files(new_files)
        set_extracted_data(new_data)
        set_alerts(new_alerts)

    def delete_file_and_row(invoice_number):
        """Delete a file and the corresponding row from the table."""
        filename_to_delete = None
        for filename, content in files.items():
            pdf_text = extract_text(io.BytesIO(content))
            if invoice_number in pdf_text:
                filename_to_delete = filename
                break

        if filename_to_delete:
            new_files = {name: content for name, content in files.items() if name != filename_to_delete}
            set_files(new_files)

            if "Numéro de facture" in extracted_data.columns:
                new_data = extracted_data[extracted_data["Numéro de facture"] != invoice_number]
                set_extracted_data(new_data)

    def generate_merged_pdf():
        """Merge all remaining files into a single PDF."""
        if not files:
            set_alerts(["⚠️ No files to merge."])
            return

        merger = PdfMerger()
        for content in files.values():
            merger.append(io.BytesIO(content))

        # Generate merged PDF in memory
        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()
        output_buffer.seek(0)
        set_merged_pdf_data(output_buffer.getvalue())

    def apply_filters(data):
        """Apply filters to the DataFrame."""
        filtered_data = data
        for column, value in filters.items():
            if value:
                filtered_data = filtered_data[filtered_data[column].astype(str).str.contains(value, case=False, na=False)]
        return filtered_data

    def apply_sort(data):
        """Apply sorting to the DataFrame."""
        if sort_column:
            data = data.sort_values(by=sort_column, ascending=sort_ascending)
        return data

    # UI Layout
    with solara.Column(align="center", style={"gap": "1rem"}):
        # Title
        solara.Markdown(
            "**G7 INVOICE KILLER**",
            style={"font-family": "Oswald, sans-serif", "font-weight": "bold", "font-size": "2rem", "text-align": "center"}
        )
        solara.Markdown(
            "_v.01-2025_",
            style={"font-family": "Oswald, sans-serif", "font-size": "1rem", "font-style": "italic", "text-align": "center"}
        )

        solara.Markdown("### Téléchargez vos fichiers PDF")
        
        solara.FileDropMultiple(
            on_file=handle_files,
            label="Glissez-déposez vos fichiers PDF ici"
        )

        if alerts:
            for alert in alerts:
                solara.Text(alert, style={"color": "red"})

        # Summary Section (without "Résumé" title)
        if not extracted_data.empty:
            filtered_data = apply_filters(extracted_data)
            sorted_data = apply_sort(filtered_data)

            # Calculate summary
            total_invoices = len(filtered_data)
            total_cost = (
                filtered_data["Prix total"]
                .str.replace(" €", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
                .sum()
            )
            solara.Text(
                f"{total_invoices} factures listées, coût total: {total_cost:.2f} €",
                style={
                    "font-weight": "bold",
                    "font-size": "1.5rem",
                    "background-color": "#f0f0f0",
                    "padding": "10px",
                    "border-radius": "5px",
                },
            )

            # Render Table Header
            solara.Markdown("### Tableau avec Filtres et Tri")
            with solara.Row(style={"font-weight": "bold", "border-bottom": "2px solid #ccc", "position": "sticky", "top": "0", "background-color": "white"}):  # Sticky headers
                column_styles = {
                    "Page #": {"min-width": "80px", "text-align": "left"},
                    "Numéro de facture": {"min-width": "200px", "text-align": "left"},
                    "Date de la facture": {"min-width": "120px", "text-align": "left"},
                    "Point de départ": {"min-width": "250px", "text-align": "left"},
                    "Destination": {"min-width": "250px", "text-align": "left"},
                    "Prix total": {"min-width": "100px", "text-align": "left"},
                }
                for column in extracted_data.columns:
                    col_style = column_styles.get(column, {"flex": "1", "text-align": "left", "min-width": "150px"})
                    with solara.Column(style=col_style):
                        solara.Button(
                            f"{column} {'↓' if sort_column == column and sort_ascending else '↑'}",
                            on_click=lambda c=column: [
                                set_sort_column(c),
                                set_sort_ascending(not sort_ascending) if sort_column == c else set_sort_ascending(True)
                            ]
                        )
                        solara.InputText(
                            value=filters.get(column, ""),
                            on_value=lambda v, c=column: set_filters({**filters, c: v}),
                            label=None  # Removed filter labels
                        )

                # Add "Actions" column for the Supprimer button
                with solara.Column(style={"flex": "1", "text-align": "center", "min-width": "120px"}):
                    solara.Text("Actions")

            # Render Rows
            for _, row in sorted_data.iterrows():
                with solara.Row(style={"border-bottom": "1px solid #ddd", "padding": "0.5rem"}):
                    for col_value, column in zip(row, sorted_data.columns):
                        col_style = column_styles.get(column, {"flex": "1", "text-align": "left", "min-width": "150px"})
                        solara.Text(str(col_value), style=col_style)

                    # Render "Supprimer" button in the last column
                    with solara.Column(style={"flex": "1", "text-align": "center", "min-width": "120px"}):
                        solara.Button(
                            "Supprimer",
                            on_click=lambda invoice=row["Numéro de facture"]: delete_file_and_row(invoice),
                            style={"background-color": "#ff4d4f", "color": "white"}
                        )

        # Add Export Button (sticky at the bottom)
        with solara.Row(style={"position": "sticky", "bottom": "0", "background-color": "white", "padding": "10px", "z-index": "10"}):
            if files:
                solara.Button(
                    "Générer un PDF fusionné",
                    on_click=generate_merged_pdf,
                    style={"background-color": "#007bff", "color": "white", "margin": "10px"}
                )
                if merged_pdf_data:
                    solara.FileDownload(
                        filename="Fichiers_Fusionnes.pdf",
                        data=merged_pdf_data,
                        label="Télécharger le PDF fusionné"
                    )


@solara.component
def Page():
    return InvoiceProcessor()
