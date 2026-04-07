from src.receipt_parser.config.settings import client
from src.receipt_parser.models.receipt import ReceiptData

RECEIPT_PARSER_PROMPT = """
Extract receipt data with these rules:

Store Name: Use the parent company name. Drop leading articles only if they are separate words (e.g., "The Home Depot" → "Home Depot"). Do NOT drop the leading letter if it is part of a name or acronym (e.g., "Amazon" stays "Amazon", "A&W" stays "A&W", "A1" stays "A1"). If the name is "The [Store Type] Company", keep "Company" to maintain brand identity.

Items: Extract all line items exactly as printed on the receipt. Do NOT merge duplicate items — if the same product appears on two separate lines, keep them as two separate items. Exclude service fees (Delivery Fee, Service Fee, etc.). number_of_items = count of distinct line items (rows), NOT the sum of quantities.

Pricing: Ensure unit_price × quantity = total_price. Handle $, £, €.

Dates: Use Invoice/Transaction Date (not Order Date for Amazon). Format: YYYY-MM-DD.

Default missing numeric fields to 0.
"""

current_model = "gemini-3-flash-preview"


def parse_result(receipt_text, model=current_model):
    """Parse OCR text into structured receipt data using Gemini."""
    try:
        response = client.models.generate_content(
            model=model,
            contents=receipt_text,
            config={
                "system_instruction": RECEIPT_PARSER_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": ReceiptData.model_json_schema(),
                "thinking_config": {
                    "thinking_budget": 0  # no thinking
                },
            },
        )
        return ReceiptData.model_validate_json(response.text)
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Full error: {repr(e)}")
        raise
