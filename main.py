import os
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv()

app = FastAPI(title="Purchase Request Site")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

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
):
    # Redirect to dashboard with user information
    return RedirectResponse(
        url=f"/dashboard?name={name}&email={email}&e_transfer_email={e_transfer_email}&address={address}&team={team}",
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
        print(f"Bulk submission received from:")
        print(f"Name: {name}")
        print(f"McMaster Email: {email}")
        print(f"E-Transfer Email: {e_transfer_email}")
        print(f"Address: {address}")
        print(f"Team: {team}")
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
