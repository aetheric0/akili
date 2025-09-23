#!/usr/bin/env python3
'''PDF and WORD parser functions to extract text from bytes in PDF
and Word documents. This module uses pdfminer for PDFs and Apache
Tika for Word documents (DOC, DOCX, ODT, RTF, etc.).

Security Note:
    -   Ensure that inputs (especially user-uploaded files) are
        validated for acceptable size and type at your API level
        to mitigate potential resource exhaustion or DOS attacks.
    -   This module handles files in memory safely, but overall
        security also depends on upstream checks.
'''

import io
import logging
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdfminer.pdfparser import PDFSyntaxError
from tika import parser as tika_parser
import unicodedata

# Configure basic logging for the module.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def parse_pdf(file_bytes: bytes) -> str:
    ''' Extracts text from a PDF file using pdfminer.

    Validations:
        - Raises ValueError if the file is empty.
        - Checks for a valid PDF header (must start with '%PDF-')
        - Catches PDFSyntaxError or other unexpected errors.
        - Ensures that extracted text is not empty.

    :param file_bytes: The content of the PDF file as bytes.
    :return: The extracted text from the PDF.
    '''
    # First check for empty file
    if not file_bytes:
        raise ValueError('Empty PDF file: no text extracted.')
    # Check the file header to see if it starts with the PDF signature
    if not file_bytes.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF file: Missing PDF header.')
    output_string = io.StringIO()

    # Use BytesIO to wrap the byte stream for pdfminer
    try:
        with io.BytesIO(file_bytes) as file_stream:
            # Adjust LAParams if needed to tune layout analysis
            laparams = LAParams()
            extract_text_to_fp(file_stream, output_string, laparams=laparams)
    except PDFSyntaxError as e:
        # This exception indicates a parsing error,
        # so the PDF is likely corrupt
        logger.exception('PDF syntax error encountered')
        raise ValueError('Corrupt PDF file: cannot extract text') from e
    except Exception as e:
        logger.exception('Unexpected error during PDF extraction.')
        raise ValueError('An error occured while processing the PDF file.')

    text = output_string.getvalue().strip()
    if not text:
        raise ValueError('Empty PDF file: no text extracted')
    # Normalize to NFC so that accents are properly composed
    text = unicodedata.normalize('NFC', text)
    return text


def parse_word(file_bytes: bytes, file_name: str) -> str:
    '''Extracts text from Word documents (DOC, DOCX, ODT, RTF, etc.) using
    Apache Tika.

    Validations:
        - Raises ValueError if the file is empty.
        - Catches exceptions from Tika and logs the filename for context.
        - Ensures that extracted text is not empty

    :param file_bytes: The content of the Word document as bytes.
    :param file_name: The name of the file (used for logging and context).
    :return: The extracted text from the document.
    '''
    if not file_bytes:
        raise ValueError('Empty Word document: no content provided.')
    try:
        #Extracts text using Apache Tika
        result = tika_parser.from_buffer(file_bytes)
    except Exception as e:
        logger.exception(
            'Error processing the Word document through Tika for file: %s',
            file_name
        )
        raise ValueError('Error processing the document through Tika.') from e

    content = result.get('content', '').strip()
    if not content:
        raise ValueError('Empty Word document: no text extracted.')
    # Normalize to NFC so that accents are properly composed
    content = unicodedata.normalize('NFC', content)
    return content

def parse_document(file_bytes: bytes, file_name: str) -> str:
    ''' Unified parser that routes to the appropriate extractor based on the
    file extension. Supports PDF files through pdfminer and various Word
    document formats through Tika.
    '''
    file_name_lower = file_name.lower()
    if file_name_lower.endswith('.pdf'):
        return parse_pdf(file_bytes)
    elif file_name_lower.endswith(('.doc', '.docx', '.odt', '.rtf')):
        return parse_word(file_bytes, file_name)
    else:
        raise ValueError('Unsupported file type.')
