import os
import time
from datetime import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import List, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

# Load environment variables
load_dotenv()

app = FastAPI(title="Purchase Request Site")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Set up templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request, success: str = None):
    success_message = None
    if success:
        success_message = "All your purchase requests have been submitted successfully! We'll be in touch soon."
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "heading": "Enter your purchase request information",
            "success_message": success_message,
            "google_api_key": os.getenv("GOOGLE_PLACES_API_KEY"),
        },
    )

@app.post("/submit-request")
async def submit_request(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    e_transfer_email: str = Form(...),
    address: str = Form(...),
    team: str = Form(...),
    signature: UploadFile = File(...),
):
    # Save signature file
    signature_extension = signature.filename.split('.')[-1] if '.' in signature.filename else 'png'
    safe_signature_filename = f"signature_{name.replace(' ', '_').lower()}_{int(time.time())}.{signature_extension}"
    signature_location = f"uploads/{safe_signature_filename}"
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save the signature file
    with open(signature_location, "wb") as file_object:
        content = await signature.read()
        file_object.write(content)
    
    # Redirect to dashboard with user information including signature
    return RedirectResponse(
        url=f"/dashboard?name={name}&email={email}&e_transfer_email={e_transfer_email}&address={address}&team={team}&signature={safe_signature_filename}",
        status_code=303
    )

@app.get("/dashboard")
async def dashboard(
    request: Request,
    name: str,
    email: str,
    e_transfer_email: str,
    address: str,
    team: str,
    signature: str,
):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "name": name,
            "email": email,
            "e_transfer_email": e_transfer_email,
            "address": address,
            "team": team,
            "signature": signature,
        },
    )

def create_excel_export(user_info, submitted_forms):
    """Create an Excel file with all submitted form data"""
    
    # Create a new workbook and select the active worksheet
    wb = Workbook()
    
    # Create Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    
    # Header style
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # User Information Section
    ws_summary['A1'] = "PURCHASE REQUEST SUBMISSION SUMMARY"
    ws_summary['A1'].font = Font(bold=True, size=16)
    ws_summary.merge_cells('A1:G1')
    
    ws_summary['A3'] = "Submission Date:"
    ws_summary['B3'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ws_summary['A4'] = "Submitter Name:"
    ws_summary['B4'] = user_info['name']
    
    ws_summary['A5'] = "McMaster Email:"
    ws_summary['B5'] = user_info['email']
    
    ws_summary['A6'] = "E-Transfer Email:"
    ws_summary['B6'] = user_info['e_transfer_email']
    
    ws_summary['A7'] = "Address:"
    ws_summary['B7'] = user_info['address']
    
    ws_summary['A8'] = "Team/Department:"
    ws_summary['B8'] = user_info['team']
    
    ws_summary['A9'] = "Digital Signature:"
    ws_summary['B9'] = user_info['signature']
    
    # Forms Summary Section
    ws_summary['A11'] = "FORMS SUBMITTED"
    ws_summary['A11'].font = Font(bold=True, size=14)
    
    # Summary headers
    summary_headers = ["Form #", "Vendor", "Total Amount (CAD)", "# of Items", "Invoice File"]
    for col, header in enumerate(summary_headers, 1):
        cell = ws_summary.cell(row=13, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Summary data
    total_overall = 0
    for i, form in enumerate(submitted_forms, 14):
        ws_summary.cell(row=i, column=1, value=form['form_number'])
        ws_summary.cell(row=i, column=2, value=form['vendor_name'])
        ws_summary.cell(row=i, column=3, value=f"${form['total_amount']:.2f}")
        ws_summary.cell(row=i, column=4, value=len(form['items']))
        ws_summary.cell(row=i, column=5, value=form['invoice_filename'])
        total_overall += form['total_amount']
    
    # Total row
    total_row = 14 + len(submitted_forms)
    ws_summary.cell(row=total_row, column=2, value="TOTAL:").font = Font(bold=True)
    ws_summary.cell(row=total_row, column=3, value=f"${total_overall:.2f}").font = Font(bold=True)
    
    # Create detailed sheet for each form
    for form in submitted_forms:
        ws_detail = wb.create_sheet(title=f"Form {form['form_number']}")
        
        # Form header
        ws_detail['A1'] = f"PURCHASE REQUEST #{form['form_number']}"
        ws_detail['A1'].font = Font(bold=True, size=16)
        ws_detail.merge_cells('A1:F1')
        
        # Vendor information
        ws_detail['A3'] = "Vendor/Store:"
        ws_detail['B3'] = form['vendor_name']
        
        ws_detail['A4'] = "Invoice File:"
        ws_detail['B4'] = form['invoice_filename']
        
        # Financial breakdown
        ws_detail['A6'] = "FINANCIAL BREAKDOWN"
        ws_detail['A6'].font = Font(bold=True, size=14)
        
        ws_detail['A7'] = "Subtotal:"
        ws_detail['B7'] = f"${form['subtotal_amount']:.2f}"
        
        ws_detail['A8'] = "Discount:"
        ws_detail['B8'] = f"-${form['discount_amount']:.2f}"
        
        ws_detail['A9'] = "HST/GST:"
        ws_detail['B9'] = f"${form['hst_gst_amount']:.2f}"
        
        ws_detail['A10'] = "Shipping:"
        ws_detail['B10'] = f"${form['shipping_amount']:.2f}"
        
        ws_detail['A11'] = "TOTAL:"
        ws_detail['A11'].font = Font(bold=True)
        ws_detail['B11'] = f"${form['total_amount']:.2f}"
        ws_detail['B11'].font = Font(bold=True)
        
        # Items section
        ws_detail['A13'] = "ITEMS PURCHASED"
        ws_detail['A13'].font = Font(bold=True, size=14)
        
        # Item headers
        item_headers = ["Item #", "Item Name", "Usage/Purpose", "Quantity", "Unit Price (CAD)", "Total (CAD)"]
        for col, header in enumerate(item_headers, 1):
            cell = ws_detail.cell(row=15, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Item data
        for i, item in enumerate(form['items'], 16):
            ws_detail.cell(row=i, column=1, value=i-15)
            ws_detail.cell(row=i, column=2, value=item['name'])
            ws_detail.cell(row=i, column=3, value=item['usage'])
            ws_detail.cell(row=i, column=4, value=item['quantity'])
            ws_detail.cell(row=i, column=5, value=f"${item['unit_price']:.2f}")
            ws_detail.cell(row=i, column=6, value=f"${item['total']:.2f}")
        
        # Auto-adjust column widths
        for col in range(1, 7):
            column_letter = get_column_letter(col)
            ws_detail.column_dimensions[column_letter].width = 20
    
    # Auto-adjust column widths for summary
    for col in range(1, 6):
        column_letter = get_column_letter(col)
        ws_summary.column_dimensions[column_letter].width = 20
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = user_info['name'].replace(' ', '_').lower()
    filename = f"purchase_requests_{safe_name}_{timestamp}.xlsx"
    filepath = f"exports/{filename}"
    
    # Create exports directory if it doesn't exist
    os.makedirs("exports", exist_ok=True)
    
    # Save the workbook
    wb.save(filepath)
    
    return filename, filepath

@app.post("/submit-all-requests")
async def submit_all_requests(request: Request):
    # Get form data
    form_data = await request.form()
    
    # Extract user information
    name = form_data.get("name")
    email = form_data.get("email")
    e_transfer_email = form_data.get("e_transfer_email")
    address = form_data.get("address")
    team = form_data.get("team")
    signature_filename = form_data.get("signature")
    
    submitted_forms = []
    
    # Process each of the 10 possible forms
    for form_num in range(1, 11):
        vendor_name = form_data.get(f"vendor_name_{form_num}")
        invoice_file = form_data.get(f"invoice_file_{form_num}")
        
        # Skip empty forms (no vendor name or invoice)
        if not vendor_name or not invoice_file or not hasattr(invoice_file, 'filename'):
            continue
            
        # Extract financial data
        subtotal_amount = float(form_data.get(f"subtotal_amount_{form_num}") or 0)
        discount_amount = float(form_data.get(f"discount_amount_{form_num}") or 0)
        hst_gst_amount = float(form_data.get(f"hst_gst_amount_{form_num}") or 0)
        shipping_amount = float(form_data.get(f"shipping_amount_{form_num}") or 0)
        total_amount = float(form_data.get(f"total_amount_{form_num}") or 0)
        
        # Extract items for this form
        items = []
        item_num = 1
        while True:
            item_name = form_data.get(f"item_name_{form_num}_{item_num}")
            if not item_name:
                break
                
            item_usage = form_data.get(f"item_usage_{form_num}_{item_num}")
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")
            
            if item_name and item_usage and item_quantity and item_price:
                items.append({
                    "name": item_name,
                    "usage": item_usage,
                    "quantity": int(item_quantity),
                    "unit_price": float(item_price),
                    "total": float(item_total) if item_total else 0
                })
            
            item_num += 1
        
        # Skip forms with no items
        if not items:
            continue
            
        # Save uploaded file with form number in filename
        safe_filename = f"form_{form_num}_{invoice_file.filename.replace(' ', '_')}"
        file_location = f"uploads/{safe_filename}"
        
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Save the file
        with open(file_location, "wb") as file_object:
            content = await invoice_file.read()
            file_object.write(content)
        
        # Store form data
        form_submission = {
            "form_number": form_num,
            "vendor_name": vendor_name,
            "invoice_filename": safe_filename,
            "file_location": file_location,
            "subtotal_amount": subtotal_amount,
            "discount_amount": discount_amount,
            "hst_gst_amount": hst_gst_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "items": items
        }
        
        submitted_forms.append(form_submission)
    
    # Print all submitted forms
    if submitted_forms:
        # Create Excel export
        user_info = {
            'name': name,
            'email': email,
            'e_transfer_email': e_transfer_email,
            'address': address,
            'team': team,
            'signature': signature_filename
        }
        
        excel_filename, excel_filepath = create_excel_export(user_info, submitted_forms)
        
        print(f"Bulk submission received from:")
        print(f"Name: {name}")
        print(f"McMaster Email: {email}")
        print(f"E-Transfer Email: {e_transfer_email}")
        print(f"Address: {address}")
        print(f"Team: {team}")
        print(f"Digital Signature: {signature_filename} (saved to uploads/{signature_filename})")
        print(f"Excel Export: {excel_filename} (saved to {excel_filepath})")
        print(f"")
        print(f"Number of forms submitted: {len(submitted_forms)}")
        print("=" * 60)
        
        for form in submitted_forms:
            print(f"Purchase Request #{form['form_number']}:")
            print(f"  Vendor: {form['vendor_name']}")
            print(f"  Invoice File: {form['invoice_filename']} (saved to {form['file_location']})")
            print(f"  Financial Breakdown:")
            print(f"    Subtotal: ${form['subtotal_amount']:.2f} CAD")
            print(f"    Discount: -${form['discount_amount']:.2f} CAD")
            print(f"    HST/GST: ${form['hst_gst_amount']:.2f} CAD")
            print(f"    Shipping: ${form['shipping_amount']:.2f} CAD")
            print(f"    Total Amount: ${form['total_amount']:.2f} CAD")
            print(f"  Items:")
            for i, item in enumerate(form['items'], 1):
                print(f"    {i}. {item['name']}")
                print(f"       Usage: {item['usage']}")
                print(f"       Quantity: {item['quantity']}")
                print(f"       Unit Price: ${item['unit_price']:.2f}")
                print(f"       Total: ${item['total']:.2f}")
            print("-" * 40)
        
        print("=" * 60)
    else:
        print("No forms were submitted (all forms were empty)")
    
    # Redirect back to home with success message
    return RedirectResponse(url="/?success=true", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
