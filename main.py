import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import List, Optional
from data_processing import create_excel_report
from image_processing import convert_signature_to_png, crop_signature

# Load environment variables
load_dotenv()

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions", "static", "templates", "excel_templates"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown"""
    # Startup: Log directory status
    print("🚀 Application startup complete - all directories ready!")
    
    yield  # Application runs here
    
    # Shutdown: Cleanup code would go here if needed
    print("👋 Application shutting down...")

app = FastAPI(title="Purchase Request Site", lifespan=lifespan)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

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

def create_session_folder(name):
    """Create a unique session folder name with timestamp and user name"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(' ', '_').lower()
    session_folder = f"sessions/{timestamp}_{safe_name}"
    
    # Create the session directory if it doesn't exist
    os.makedirs(session_folder, exist_ok=True)
    
    return session_folder

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
    # Create session folder for this user
    session_folder = create_session_folder(name)
    
    # Save signature file in session folder
    signature_extension = signature.filename.split('.')[-1] if '.' in signature.filename else 'png'
    signature_filename = f"signature.{signature_extension}"
    signature_location = f"{session_folder}/{signature_filename}"
    
    # Save the original signature file first
    with open(signature_location, "wb") as file_object:
        content = await signature.read()
        file_object.write(content)
    
    # Convert signature to PNG format
    png_signature_filename = "signature.png"
    png_signature_location = f"{session_folder}/{png_signature_filename}"
    
    if convert_signature_to_png(signature_location, png_signature_location):
        # Crop the converted PNG to remove any remaining whitespace
        cropped_signature_filename = "signature_cropped.png"
        cropped_signature_location = f"{session_folder}/{cropped_signature_filename}"
        
        cropped_path = crop_signature(png_signature_location, cropped_signature_location)
        
        if cropped_path:
            # Use the cropped version
            final_signature_filename = cropped_signature_filename
            print(f"Signature cropped and optimized: {cropped_signature_location}")
            
            # Remove the uncropped PNG to save space
            try:
                os.remove(png_signature_location)
                print(f"Uncropped PNG removed: {png_signature_location}")
            except Exception as e:
                print(f"Could not remove uncropped PNG: {e}")
        else:
            # Cropping failed, use the regular PNG
            final_signature_filename = png_signature_filename
            print(f"Signature cropping failed, using converted PNG: {png_signature_location}")
        
        print(f"Signature converted to PNG: {png_signature_location}")
        
        # Optionally remove the original file if conversion was successful
        if signature_extension.lower() != 'png':
            try:
                os.remove(signature_location)
                print(f"Original signature file removed: {signature_location}")
            except Exception as e:
                print(f"Could not remove original signature file: {e}")
    else:
        # Fall back to original file if conversion failed
        final_signature_filename = signature_filename
        print(f"Signature conversion failed, using original: {signature_location}")
    
    # Redirect to dashboard with user information including session folder
    return RedirectResponse(
        url=f"/dashboard?name={name}&email={email}&e_transfer_email={e_transfer_email}&address={address}&team={team}&session_folder={session_folder}&signature={final_signature_filename}",
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
    session_folder: str,
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
            "session_folder": session_folder,
            "signature": signature,
        },
    )

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
    session_folder = form_data.get("session_folder")
    signature_filename = form_data.get("signature")
    
    submitted_forms = []
    
    # Process each of the 10 possible forms
    for form_num in range(1, 11):
        vendor_name = form_data.get(f"vendor_name_{form_num}")
        invoice_file = form_data.get(f"invoice_file_{form_num}")
        proof_of_payment_file = form_data.get(f"proof_of_payment_{form_num}")
        currency = form_data.get(f"currency_{form_num}", "CAD")  # Default to CAD if not specified
        
        # Skip empty forms (no vendor name or invoice)
        if not vendor_name or not invoice_file or not hasattr(invoice_file, 'filename'):
            continue
        
        # For USD purchases, proof of payment is required
        if currency == "USD" and (not proof_of_payment_file or not hasattr(proof_of_payment_file, 'filename')):
            print(f"Warning: Form {form_num} in USD currency missing proof of payment - skipping")
            continue
            
        # Extract financial data based on currency
        if currency == "USD":
            # For USD, use simplified breakdown
            us_total = float(form_data.get(f"us_total_{form_num}") or 0)
            usd_taxes = float(form_data.get(f"usd_taxes_{form_num}") or 0)
            canadian_amount = float(form_data.get(f"canadian_amount_{form_num}") or 0)
            
            # Set other fields to 0 for USD
            subtotal_amount = 0
            discount_amount = 0
            hst_gst_amount = usd_taxes  # Use USD taxes as the tax amount
            shipping_amount = 0
            total_amount = canadian_amount  # Use Canadian amount as total for reimbursement
        else:
            # For CAD, use detailed breakdown
            subtotal_amount = float(form_data.get(f"subtotal_amount_{form_num}") or 0)
            discount_amount = float(form_data.get(f"discount_amount_{form_num}") or 0)
            hst_gst_amount = float(form_data.get(f"hst_gst_amount_{form_num}") or 0)
            shipping_amount = float(form_data.get(f"shipping_amount_{form_num}") or 0)
            total_amount = float(form_data.get(f"total_amount_{form_num}") or 0)
            
            # Set USD fields to 0 for CAD
            us_total = 0
            usd_taxes = 0
            canadian_amount = 0
        
        # Debug logging to see what values we're getting
        print(f"Form {form_num} ({currency}) financial data:")
        print(f"  Raw subtotal_amount: '{form_data.get(f'subtotal_amount_{form_num}')}'")
        print(f"  Raw total_amount: '{form_data.get(f'total_amount_{form_num}')}'")
        print(f"  Raw hst_gst_amount: '{form_data.get(f'hst_gst_amount_{form_num}')}'")
        print(f"  Raw shipping_amount: '{form_data.get(f'shipping_amount_{form_num}')}'")
        if currency == "USD":
            print(f"  Raw us_total: '{form_data.get(f'us_total_{form_num}')}'")
            print(f"  Raw usd_taxes: '{form_data.get(f'usd_taxes_{form_num}')}'")
            print(f"  Raw canadian_amount: '{form_data.get(f'canadian_amount_{form_num}')}'")
        print(f"  Parsed values:")
        print(f"    subtotal_amount: {subtotal_amount}")
        print(f"    discount_amount: {discount_amount}")
        print(f"    hst_gst_amount: {hst_gst_amount}")
        print(f"    shipping_amount: {shipping_amount}")
        print(f"    total_amount: {total_amount}")
        print(f"    us_total: {us_total}")
        print(f"    usd_taxes: {usd_taxes}")
        print(f"    canadian_amount: {canadian_amount}")
        print("---")
        
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
            
            # Debug logging for item values
            print(f"  Item {item_num} raw values:")
            print(f"    name: '{item_name}'")
            print(f"    usage: '{item_usage}'")
            print(f"    quantity: '{item_quantity}'")
            print(f"    price: '{item_price}'")
            print(f"    total: '{item_total}'")
            
            if item_name and item_usage and item_quantity and item_price:
                parsed_total = float(item_total) if item_total else 0
                items.append({
                    "name": item_name,
                    "usage": item_usage,
                    "quantity": int(item_quantity),
                    "unit_price": float(item_price),
                    "total": parsed_total
                })
                print(f"    → Added to items: qty={int(item_quantity)}, price=${float(item_price)}, total=${parsed_total}")
            else:
                print(f"    → Skipped (missing required fields)")
            
            item_num += 1
        
        # Skip forms with no items
        if not items:
            continue
            
        # Save uploaded invoice file in session folder
        invoice_extension = invoice_file.filename.split('.')[-1] if '.' in invoice_file.filename else 'pdf'
        invoice_filename = f"{form_num}_invoice.{invoice_extension}"
        invoice_file_location = f"{session_folder}/{invoice_filename}"
        
        # Save the invoice file
        with open(invoice_file_location, "wb") as file_object:
            content = await invoice_file.read()
            file_object.write(content)
        
        # Save proof of payment file if provided (required for USD)
        proof_of_payment_filename = None
        proof_of_payment_location = None
        if proof_of_payment_file and hasattr(proof_of_payment_file, 'filename'):
            payment_extension = proof_of_payment_file.filename.split('.')[-1] if '.' in proof_of_payment_file.filename else 'pdf'
            proof_of_payment_filename = f"{form_num}_proof_of_payment.{payment_extension}"
            proof_of_payment_location = f"{session_folder}/{proof_of_payment_filename}"
            
            # Save the proof of payment file
            with open(proof_of_payment_location, "wb") as file_object:
                content = await proof_of_payment_file.read()
                file_object.write(content)
        
        # Store form data
        form_submission = {
            "form_number": form_num,
            "vendor_name": vendor_name,
            "currency": currency,
            "invoice_filename": invoice_filename,
            "invoice_file_location": invoice_file_location,
            "proof_of_payment_filename": proof_of_payment_filename,
            "proof_of_payment_location": proof_of_payment_location,
            "subtotal_amount": subtotal_amount,
            "discount_amount": discount_amount,
            "hst_gst_amount": hst_gst_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "us_total": us_total,
            "usd_taxes": usd_taxes,
            "canadian_amount": canadian_amount,
            "items": items
        }
        
        submitted_forms.append(form_submission)
    
    # Print all submitted forms
    if submitted_forms:
        # Create Excel export in session folder
        user_info = {
            'name': name,
            'email': email,
            'e_transfer_email': e_transfer_email,
            'address': address,
            'team': team,
            'signature': signature_filename
        }
        
        excel_report = create_excel_report(user_info, submitted_forms, session_folder)
        
        print(f"Bulk submission received from:")
        print(f"Name: {name}")
        print(f"McMaster Email: {email}")
        print(f"E-Transfer Email: {e_transfer_email}")
        print(f"Address: {address}")
        print(f"Team: {team}")
        print(f"Session Folder: {session_folder}")
        print(f"Digital Signature: {signature_filename} (saved to {session_folder}/{signature_filename})")
        print(f"Excel Report Generated: {excel_report['filename']}")
        print(f"  - Forms processed: {excel_report['forms_processed']}")
        print(f"  - Tabs used: {', '.join(excel_report['tabs_used'])}")
        print(f"  - File location: {excel_report['filepath']}")
        print(f"")
        print(f"Number of forms submitted: {len(submitted_forms)}")
        print("=" * 60)
        
        for form in submitted_forms:
            print(f"Purchase Request #{form['form_number']}:")
            print(f"  Vendor: {form['vendor_name']}")
            print(f"  Currency: {form['currency']}")
            print(f"  Invoice File: {form['invoice_filename']} (saved to {form['invoice_file_location']})")
            if form['proof_of_payment_filename']:
                print(f"  Proof of Payment: {form['proof_of_payment_filename']} (saved to {form['proof_of_payment_location']})")
            print(f"  Financial Breakdown:")
            
            if form['currency'] == "USD":
                # Show USD breakdown
                print(f"    US Total: ${form['us_total']:.2f} USD")
                print(f"    Canadian Amount: ${form['canadian_amount']:.2f} CAD")
                print(f"    Reimbursement Total: ${form['canadian_amount']:.2f} CAD")
            else:
                # Show CAD breakdown
                print(f"    Subtotal: ${form['subtotal_amount']:.2f} {form['currency']}")
                print(f"    Discount: -${form['discount_amount']:.2f} {form['currency']}")
                
                # Use appropriate tax label based on currency
                tax_label = "Taxes" if form['currency'] == "USD" else "HST/GST"
                print(f"    {tax_label}: ${form['hst_gst_amount']:.2f} {form['currency']}")
                
                print(f"    Shipping: ${form['shipping_amount']:.2f} {form['currency']}")
                print(f"    Total Amount: ${form['total_amount']:.2f} {form['currency']}")
            
            print(f"  Items:")
            for i, item in enumerate(form['items'], 1):
                print(f"    {i}. {item['name']}")
                print(f"       Usage: {item['usage']}")
                print(f"       Quantity: {item['quantity']}")
                print(f"       Unit Price: ${item['unit_price']:.2f} {form['currency']}")
                print(f"       Total: ${item['total']:.2f} {form['currency']}")
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
