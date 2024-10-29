################################################
# Step1: import the necessary libraries
import streamlit as st # for user interactive analysis
import pandas as pd
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract # for Ocr
from io import BytesIO
import re  # regular expression
import time # to keep a track of processing time


#################################################
# Step 2: Helping Functions 

# Fextract_text_from_pdf : to extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_file):
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text, True, "Text extracted successfully."
    except Exception as e:
        return "", False, f"Error extracting text using PyMuPDF: {str(e)}"

# extract_text_from_image: to apply OCR using Tesseract for scanned PDFs
def extract_text_from_image(pdf_file):
    try:
        images = convert_from_path(pdf_file, dpi=300)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text, True, "OCR applied successfully."
    except Exception as e:
        return "", False, f"Error extracting text using OCR: {str(e)}"

# safe_float: to process extracted text into desired format removing  commas and rupees symbol
def safe_float(value):
    try:
        return float(value.replace(',', '').replace('₹', '').strip())
    except ValueError:
        return 0.0
    

def process_invoice_text(text):
    # Initialize variables and their confidence levels
    accuracy_scores = {}
    invoice_number, invoice_date, due_date = "", "", ""
    place_of_supply, place_of_origin = "", ""
    mobile, email, customer_details, gstin = "", "", "", ""
    taxable_value, sgst_amount, cgst_amount, igst_amount, final_amount = 0, 0, 0, 0, 0
    total_discount, tax_amount = 0, 0
    cgst_rates, sgst_rates, igst_rates = [], [], []

    # Extracting invoice number
    invoice_number_match = re.search(r"Invoice #:\s*([A-Za-z0-9\-]+)", text)
    if invoice_number_match:
        invoice_number = invoice_number_match.group(1).strip()
        accuracy_scores['invoice_number'] = 1
    else:
        accuracy_scores['invoice_number'] = 0.5

    # Extracting invoice date
    invoice_date_match = re.search(r"Invoice Date:\s*([0-9A-Za-z\s]+)\s*Due Date:", text)
    if invoice_date_match:
        invoice_date = invoice_date_match.group(1).strip()
        accuracy_scores['invoice_date'] = 1
    else:
        accuracy_scores['invoice_date'] = 0.6

    # Extracting due date
    due_date_match = re.search(r"Due Date:\s*([0-9A-Za-z\s]+)\s*Customer Details:", text)
    if due_date_match:
        due_date = due_date_match.group(1).strip()
        accuracy_scores['due_date'] = 1
    else:
        accuracy_scores['due_date'] = 0.6

    # Extracting place of supply
    place_of_supply_match = re.search(r"Place of Supply:\s*([0-9A-Za-z\s\-]+)", text)
    if place_of_supply_match:
        place_of_supply = place_of_supply_match.group(1).strip()
        accuracy_scores['place_of_supply'] = 1
    else:
        accuracy_scores['place_of_supply'] = 0.5

    # Extracting place of origin
    place_of_origin_match = re.search(r"(?:Shahdol,)\s*([A-Za-z\s]+),\s*[0-9]{6}", text, re.DOTALL)
    if place_of_origin_match:
        place_of_origin = place_of_origin_match.group(1).strip()

    # Extracting mobile number
    mobile_match = re.search(r"Mobile\s*\+?\d*\s*([0-9]+)", text)
    if mobile_match:
        mobile = mobile_match.group(1).strip()

    # Extracting email
    email_match = re.search(r"Email\s*([A-Za-z0-9@.\-_]+)", text)
    if email_match:
        email = email_match.group(1).strip()

    # Extracting customer details
    customer_details_match = re.search(r"Customer Details:\s*([A-Za-z\s]+)", text)
    if customer_details_match:
        customer_details = customer_details_match.group(1).strip()
    customer_details_clean = re.sub(r"\b(Place of Supply|Ph)\b.*", '', customer_details).strip()

    # Extracting GSTIN
    gstin_match = re.search(r"GSTIN\s*([A-Za-z0-9]+)", text)
    if gstin_match:
        gstin = gstin_match.group(1).strip()
        accuracy_scores['gstin'] = 1
    else:
        accuracy_scores['gstin'] = 1

    # Extracting taxable value
    taxable_value_match = re.search(r"Taxable Amount\s*₹([0-9,]+\.\d{2})", text)
    if taxable_value_match:
        taxable_value = safe_float(taxable_value_match.group(1))
        accuracy_scores['taxable_value'] = 1
    else:
        accuracy_scores['taxable_value'] = 0.6

    # Extracting CGST amounts and rates
    cgst_matches = re.findall(r"CGST\s*(\d+\.?\d*)%?\s*₹([0-9,]+\.\d{2})", text)
    for match in cgst_matches:
        cgst_rates.append(float(match[0]))
        cgst_amount += safe_float(match[1])
    accuracy_scores['cgst_amount'] = 1 if cgst_matches else 0.9

    # Extracting SGST amounts and rates
    sgst_matches = re.findall(r"SGST\s*(\d+\.?\d*)%?\s*₹([0-9,]+\.\d{2})", text)
    for match in sgst_matches:
        sgst_rates.append(float(match[0]))
        sgst_amount += safe_float(match[1])
    accuracy_scores['sgst_amount'] = 1 if sgst_matches else 0.9

    # Extracting IGST amounts and rates
    igst_matches = re.findall(r"IGST\s*(\d+\.?\d*)%?\s*₹([0-9,]+\.\d{2})", text)
    for match in igst_matches:
        igst_rates.append(float(match[0]))
        igst_amount += safe_float(match[1])
    accuracy_scores['igst_amount'] = 1 if igst_matches else 0.9

    # Extracting final amount
    final_amount_match = re.search(r"Total\s*₹([0-9,]+\.\d{2})", text)
    if final_amount_match:
        final_amount = safe_float(final_amount_match.group(1))
        accuracy_scores['final_amount'] = 1
    else:
        accuracy_scores['final_amount'] = 0.5

    # Extracting total discount
    discount_match = re.search(r"Total Discount\s*-?\s*₹([0-9,]+\.\d{2})", text)
    if discount_match:
        total_discount = safe_float(discount_match.group(1))

    # Calculating total tax amount
    tax_amount = sgst_amount + cgst_amount + igst_amount
    accuracy_scores['tax_amount'] = 1

    # Calculate overall trust score (average of individual scores)
    overall_trust_score = sum(accuracy_scores.values()) / len(accuracy_scores)
    accuracy_scores['overall_trust_score'] = overall_trust_score

    # Return parsed data and accuracy scores
    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "mobile": mobile,
        "email": email,
        "customer_details": customer_details_clean,
        "place_of_origin": place_of_origin,
        "place_of_supply": place_of_supply,
        "gstin": gstin,
        "taxable_value": taxable_value,
        "cgst_rates": cgst_rates if cgst_rates else [0],
        "sgst_rates": sgst_rates if sgst_rates else [0],
        "igst_rates": igst_rates if igst_rates else [0],
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "tax_amount": tax_amount,
        "total_discount": total_discount,
        "final_amount": final_amount,
        "overall_trust_score": overall_trust_score
    }, accuracy_scores

# Streamlit app with scalability and performance improvements
st.title("Scalable Invoice Data Extraction")
st.write("Upload invoices (PDFs) and receive detailed extraction with accuracy scores and performance metrics.")

uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

if uploaded_files:
    extracted_data = []
    start_time = time.time()

    for pdf_file in uploaded_files:
        extraction_status = {}
        try:
            extracted_text, success, message = extract_text_from_pdf(pdf_file)
            extraction_status['method'] = 'PyMuPDF'
            extraction_status['success'] = success
            extraction_status['message'] = message

            if not success:
                extracted_text, success, message = extract_text_from_image(pdf_file)
                extraction_status['method'] = 'OCR'
                extraction_status['success'] = success
                extraction_status['message'] = message

            if success:
                invoice_data, accuracy_scores = process_invoice_text(extracted_text)
                invoice_data['extraction_status'] = extraction_status
                invoice_data['accuracy_scores'] = accuracy_scores
                extracted_data.append(invoice_data)
            else:
                st.error(f"Failed to extract text for {pdf_file.name}: {message}")
        except Exception as e:
            st.error(f"Error processing file {pdf_file.name}: {str(e)}")
            extraction_status['success'] = False
            extraction_status['message'] = str(e)

    # Calculate total processing time
    processing_time = time.time() - start_time
    st.write(f"Processed {len(uploaded_files)} files in {processing_time:.2f} seconds.")

    # Display extracted data and accuracy scores
    if extracted_data:
        df = pd.DataFrame(extracted_data)
        st.write("Extracted Data with Accuracy Scores:")
        st.dataframe(df)

        # Export to Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            label="Download Excel file",
            data=output.getvalue(),
            file_name="extracted_invoices_with_accuracy.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )