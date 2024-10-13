# importing the necessary libraries needed 
import os
import requests
import json
import pandas as pd
import re
import logging
import time
from pypdf import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

###########################################################################
# 1. Configuration and Setup


# Configure logging
logging.basicConfig(
    filename='invoice_extraction.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Loaded environment variables from .env
load_dotenv()


GPT4V_KEY = os.getenv("GPT4V_KEY")
GPT4V_ENDPOINT = os.getenv("GPT4V_ENDPOINT")

if not GPT4V_KEY or not GPT4V_ENDPOINT:
    st.error("API key or endpoint not found in the environment variables.")
    st.stop()

# Headers for the API call
headers = {
    "Content-Type": "application/json",
    "api-key": GPT4V_KEY,
}



###################################################################
# 2.  Functions

# extracting text from pdf files handling regular and scanned PDFs.
def get_pdf_text(pdf_doc):  # pdf_doc (UploadedFile): The uploaded PDF file.
    
    text = ""
    try:
        pdf_reader = PdfReader(pdf_doc)
        num_pages = len(pdf_reader.pages)
        for page_number, page in enumerate(pdf_reader.pages, start=1):
            extracted_text = page.extract_text()
            
            if extracted_text and len(extracted_text.strip()) > 50:  # Threshold for text extraction
                text += extracted_text + "\n"
                logging.info(f"Text extracted from page {page_number} using PdfReader.")
            else:
                # If text extraction is insufficient, use OCR
                logging.info(f"Insufficient text on page {page_number}. Applying OCR.")
                pdf_doc.seek(0)  # Reset file pointer to read bytes
                pdf_bytes = pdf_doc.read()
                images = convert_from_bytes(pdf_bytes, first_page=page_number, last_page=page_number)
                
                for image in images:
                    ocr_text = pytesseract.image_to_string(image, config='--psm 6')  # Assume a single uniform block of text
                    
                    if ocr_text and len(ocr_text.strip()) > 10:  # Threshold for OCR text
                        text += ocr_text + "\n"
                        logging.info(f"OCR text extracted from page {page_number}.")
    
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        st.error(f"Error extracting text from PDF: {e}")

    return text  # str: The extracted text from the PDF.





# Calls the OpenAI GPT-4 API to extract invoice data in JSON format.
def call_openai_api(pages_data):  #pages_data (str): The extracted text from the PDF.
               
            # designing a prompt using personification
    prompt_template = '''You are an expert and have best knowledge of invoices .Extract the following fields from the invoice data: 
- Invoice No.
- Quantity
- Date
- Amount
- Total
- Email
- Address
- Taxable Value
- SGST Amount
- CGST Amount
- IGST Amount
- SGST Rate
- CGST Rate
- IGST Rate
- Tax Amount
- Tax Rate
- Final Amount
- Invoice Date
- Place of Supply
- Place of Origin
- GSTIN Supplier
- GSTIN Recipient

**Provide the output strictly in valid JSON format with no additional text, explanations, or comments. Ensure all keys are correctly spelled and correspond to the field names above. Do not include any trailing commas or syntax errors.**

Here is the invoice data:
{pages}
'''
    prompt = prompt_template.format(pages=pages_data)

    data = {
        "messages": [
            {"role": "system", "content": "You are a helpful and accurate assistant."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,  # Increased tokens for detailed extraction
        "temperature": 0.3    # Lower temperature for more deterministic output
    }

    try:
        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=data)
        if response.status_code == 200:
            response_json = response.json()
            llm_extracted_data = response_json.get("choices", [])[0].get("message", {}).get("content", "")
            logging.info(f"Raw API response for data extraction: {llm_extracted_data}")
            return llm_extracted_data
        elif response.status_code == 429:
            # Rate limit exceeded
            logging.warning("Rate limit exceeded!!!!!. Retrying after 10 seconds...")
            st.warning("Rate limit exceeded !!!!!. Retrying after 10 seconds...")
            time.sleep(10)  # Wait for 10 seconds before retrying
            return call_openai_api(pages_data)
        else:
            logging.error(f"API call failed: {response.status_code} - {response.text}")
            st.error(f"Error during API call: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Exception during API call: {e}")
        st.error(f"An error occurred during API call: {e}")
        return None     #str or None: The raw extracted data from the API if successful; otherwise, None.




# Validates the extracted data fields using regex patterns and assigns confidence levels.
def validate_data(field, value): # field (str): The name of the field.  value (str): The extracted value of the field.
    
    patterns = {
        'Invoice No.': r'^[A-Za-z0-9\-]+$',
        'Quantity': r'^\d+(\.\d+)?$',
        'Date': r'^\d{2}/\d{2}/\d{4}$',
        'Amount': r'^\d+(\.\d+)?$',
        'Total': r'^\d+(\.\d+)?$',
        'Email': r'^[\w\.-]+@[\w\.-]+\.\w+$',
        'GSTIN Supplier': r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$',
        'GSTIN Recipient': r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$',
        # Add more patterns as needed
    }

    if field in patterns:
        if re.match(patterns[field], str(value).strip()):
            return True, "High Confidence"
        else:
            return False, "Low Confidence"
    else:
        # For fields without specific patterns, basic non-empty check
        if str(value).strip():
            return True, "Medium Confidence"
        else:
            return False, "Low Confidence"    
  

# Extracts the first JSON object found in the raw text.  
def extract_json(raw_text):  # raw_text (str): The raw text containing JSON.    
                
    pattern = r'\{.*\}'  # Matches the first occurrence of {...}
    match = re.search(pattern, raw_text, re.DOTALL)
    if match:
        return match.group(0)
    else:
        return None
    # str or None: The extracted JSON string if found; otherwise, None.




############################################################
# 3. Main Function to Process PDF Files

# Processes multiple PDF files to extract invoice data and compile it into a DataFrame.
def create_docs(user_pdf_list):  # user_pdf_list (list): List of uploaded PDF files.

    # Initialize DataFrame with additional columns for confidence and trust
    df = pd.DataFrame(columns=[
        'Invoice No.', 'Quantity', 'Date', 'Amount', 'Total',
        'Email', 'Address', 'Taxable Value', 'SGST Amount',
        'CGST Amount', 'IGST Amount', 'SGST Rate', 'CGST Rate',
        'IGST Rate', 'Tax Amount', 'Tax Rate', 'Final Amount',
        'Invoice Date', 'Place of Supply', 'Place of Origin',
        'GSTIN Supplier', 'GSTIN Recipient',
        'Confidence', 'Trust'
    ])
    
    # Metrics 
    metrics = {
        'total_files': 0,
        'successful_extractions': 0,
        'field_accuracy': {field: {'correct': 0, 'total': 0} for field in df.columns if field not in ['Confidence', 'Trust']}
    }
    
    for file in user_pdf_list:
        metrics['total_files'] += 1
        st.write(f"### Processing `{file.name}`...")
        try:
            raw_data = get_pdf_text(file)
            if not raw_data.strip():
                st.warning(f"No text extracted from `{file.name}`. Skipping.")
                logging.warning(f"No text extracted from {file.name}.")
                continue
            
            # Display extracted text for debugging
            with st.expander(f"🔍 Extracted Text from `{file.name}`", expanded=False):
                st.text_area("Extracted Text:", raw_data, height=300)
            
            llm_extracted_data = call_openai_api(raw_data)
            if not llm_extracted_data:
                st.error(f"Failed to extract data from `{file.name}`.")
                logging.error(f"API response failed for {file.name}.")
                continue

            # Log the raw extracted data
            logging.info(f"Raw extracted data for {file.name}: {llm_extracted_data}")
            
            # Display raw extracted data for debugging
            with st.expander(f" Raw Extracted Data from `{file.name}`", expanded=False):
                st.code(llm_extracted_data, language='json')

            # Extract JSON from the raw response
            json_text = extract_json(llm_extracted_data)
            if not json_text:
                logging.error(f"No JSON found in the API response for {file.name}.")
                st.error(f"Error parsing extracted data from `{file.name}`: Invalid JSON.")
                st.write("**Please ensure that the GPT-4 API returns valid JSON.**")
                continue

            # Parse the JSON text
            try:
                data_dict = json.loads(json_text)
                logging.info(f"Extracted data from {file.name}: {data_dict}")
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding failed for {file.name}: {e}")
                st.error(f"Error parsing extracted data from `{file.name}`: Invalid JSON.")
                st.write("**Please ensure that the GPT-4 API returns valid JSON.**")
                continue

            # Validate each field and assess confidence
            confidence_list = []
            trust_list = []
            for field in df.columns:
                if field in ['Confidence', 'Trust']:
                    continue
                value = data_dict.get(field, "")
                is_valid, confidence = validate_data(field, value)
                confidence_list.append(confidence)
                trust = "Trusted" if confidence in ["High Confidence", "Medium Confidence"] else "Untrusted"
                trust_list.append(trust)
                
                # Update metrics
                metrics['field_accuracy'][field]['total'] += 1
                if is_valid:
                    metrics['field_accuracy'][field]['correct'] += 1

            # Add confidence and trust assessment
            data_dict['Confidence'] = "; ".join(confidence_list)
            data_dict['Trust'] = "Trusted" if "Low Confidence" not in confidence_list else "Untrusted"

            # Append the extracted data to the DataFrame
            df = pd.concat([df, pd.DataFrame([data_dict])], ignore_index=True)
            metrics['successful_extractions'] += 1
            st.success(f"**Extraction successful for `{file.name}`.** ")
            logging.info(f"Extraction successful for {file.name}.")

        except Exception as e:
            logging.error(f"An error occurred while processing {file.name}: {e}")
            st.error(f"An error occurred while processing `{file.name}`: {e}")

    # Calculate accuracy rates
    accuracy_rates = {}
    for field, counts in metrics['field_accuracy'].items():
        if counts['total'] > 0:
            accuracy = (counts['correct'] / counts['total']) * 100
            accuracy_rates[field] = f"{accuracy:.2f}%"
        else:
            accuracy_rates[field] = "N/A"

    # Save the DataFrame to an Excel file
    output_excel_file = "extracted_invoice_data.xlsx"
    try:
        df.to_excel(output_excel_file, index=False)
        logging.info("DataFrame successfully saved to Excel.")
    except Exception as e:
        logging.error(f"Failed to save DataFrame to Excel: {e}")
        st.error(f"Failed to save extracted data to Excel: {e}")

    # Display metrics
    st.write("###  Extraction Performance Metrics")
    st.write(f"**Total Files Processed:** {metrics['total_files']}")
    st.write(f"**Successful Extractions:** {metrics['successful_extractions']}")
    
    metrics_df = pd.DataFrame.from_dict(accuracy_rates, orient='index', columns=['Accuracy Rate'])
    metrics_df.index.name = 'Field'
    st.write("**Per-Field Accuracy Rates:**")
    st.dataframe(metrics_df.style.highlight_max(color='lightgreen'))

    # Provide download options
    with open(output_excel_file, "rb") as f:
        excel_data = f.read()
    st.download_button(
        "Download Extracted Data as Excel",
        data=excel_data,
        file_name=output_excel_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Additionally, allow downloading as CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Extracted Data as CSV",
        data=csv,
        file_name="extracted_invoice_data.csv",
        mime="text/csv"
    )

    # Display trust assessment summary
    trusted = df['Trust'].value_counts().get('Trusted', 0)
    untrusted = df['Trust'].value_counts().get('Untrusted', 0)
    st.write(f"**Trusted Data Points:** {trusted}")
    st.write(f"**Untrusted Data Points:** {untrusted}")

    return df     # pd.DataFrame: DataFrame containing all extracted invoice data.






#############################################################
# 4. Streamlit Application


def main():
    """
    The main function that runs the Streamlit application.
    """
    st.set_page_config(page_title=" Invoice Extraction Bot", layout="wide")
    st.title(" Invoice Extraction Bot")
    st.subheader("Extract and Validate Invoice Data with High Accuracy")

    # Upload the invoices (PDF files)
    pdf_files = st.file_uploader(
        "Upload invoice PDFs here (supports regular, scanned, and mixed PDFs)",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("Extract Data"):
        if pdf_files:
            with st.spinner('Processing your invoices...'):
                df = create_docs(pdf_files)
                
                if not df.empty:
                    st.write("### Extracted Data:")
                    st.dataframe(df)
    
                    # Provide a summary of trust assessments
                    trusted = df['Trust'].value_counts().get('Trusted', 0)
                    untrusted = df['Trust'].value_counts().get('Untrusted', 0)
                    st.write(f"**Trusted Data Points:** {trusted}")
                    st.write(f"**Untrusted Data Points:** {untrusted}")
                    
                    st.success("Extraction complete!")
                else:
                    st.warning("⚠️ No data extracted from the uploaded PDFs.")
        else:
            st.error("Please upload at least one PDF file.")







##################################################################################
# Finally Run the Application


if __name__ == "__main__":
    main()

