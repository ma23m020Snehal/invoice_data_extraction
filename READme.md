 Invoice Extraction Bot

## Description

The *Invoice Extraction Bot* is a Streamlit application designed to extract and validate invoice data from PDF files. It utilizes OpenAI's GPT-4 model to intelligently parse and organize critical information from invoices, such as invoice numbers, dates, amounts, and various tax-related fields.

## Features

- Upload invoice PDFs (supports regular, scanned, and mixed PDFs).
- Automatically extracts data fields including:
  - Invoice No.
  - Quantity
  - Date
  - Amount
  - Total
  - Email
  - GSTINs (Supplier and Recipient)
  - Tax rates
  - Tax Amount
- Validation of extracted data with confidence levels.
- Provides detailed metrics on extraction performance.
- Download extracted data in Excel and CSV formats.

## Prerequisites

Before running the application, ensure you have the following installed:

- Python 3.9 or later (if running locally)
- An OpenAI GPT-4 API key (very important)

## Installation and Setup

1. *Clone the Repository:*

   bash
   git clone <repository-url>
   cd <repository-directory>


2. **Create a .env File:**
Create a .env file in the root directory and add your OpenAI API key and endpoint:

GPT4V_KEY=your_openai_api_key
GPT4V_ENDPOINT=your_openai_api_endpoint


3. *Access the Application:*

Open your web browser and navigate to http://localhost:8501 to access the Invoice Extraction Bot.


## screenshots




For a visual demonstration of the application, watch this video: Invoice Extraction Bot Demo

## Contributing
Contributions are welcome! Please create an issue or submit a pull request if you have suggestions or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.



### Notes

- *Repository URL*: Replace <repository-url> in the clone command with the actual URL of your GitHub repository.
- *Screenshots*: Make sure to place your screenshot in a screenshots directory within your project, and update the filename in the README if needed.
- *Video Link*: Replace https://www.example.com/demo-video with the actual link to your video demonstration. You can upload the video to platforms like YouTube or Vimeo.