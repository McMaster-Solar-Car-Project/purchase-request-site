import os
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import List

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
        success_message = "Your purchase request has been submitted successfully! We'll be in touch soon."
    
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
    # Redirect to step 2 (reimbursement page) with the form data
    return templates.TemplateResponse(
        "reimbursement.html",
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

@app.post("/submit-final-request")
async def submit_final_request(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    e_transfer_email: str = Form(...),
    address: str = Form(...),
    team: str = Form(...),
    vendor_name: str = Form(...),
    invoice_file: UploadFile = File(...),
    subtotal_amount: float = Form(...),
    discount_amount: float = Form(0.0),
    hst_gst_amount: float = Form(0.0),
    shipping_amount: float = Form(0.0),
    total_amount: float = Form(...),
):
    # Process item details from the dynamic form
    form_data = await request.form()
    items = []
    
    # Extract item details including new fields
    for key in form_data:
        if key.startswith("item_name_"):
            item_number = key.split("_")[-1]
            item_name = form_data[key]
            
            # Get all related fields for this item
            item_usage_key = f"item_usage_{item_number}"
            item_quantity_key = f"item_quantity_{item_number}"
            item_price_key = f"item_price_{item_number}"
            item_total_key = f"item_total_{item_number}"
            
            if all(k in form_data for k in [item_usage_key, item_quantity_key, item_price_key, item_total_key]):
                item_usage = form_data[item_usage_key]
                item_quantity = int(form_data[item_quantity_key])
                item_price = float(form_data[item_price_key])
                item_total = float(form_data[item_total_key])
                
                items.append({
                    "name": item_name,
                    "usage": item_usage,
                    "quantity": item_quantity,
                    "unit_price": item_price,
                    "total": item_total
                })
    
    # Save uploaded file (in a real app, you'd save to cloud storage or disk)
    file_location = f"uploads/{invoice_file.filename}"
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    with open(file_location, "wb") as file_object:
        content = await invoice_file.read()
        file_object.write(content)
    
    # Here you would typically save to a database
    # For now, we'll just print the data and redirect
    print(f"New purchase request received:")
    print(f"Name: {name}")
    print(f"McMaster Email: {email}")
    print(f"E-Transfer Email: {e_transfer_email}")
    print(f"Address: {address}")
    print(f"Team: {team}")
    print(f"Vendor: {vendor_name}")
    print(f"Invoice File: {invoice_file.filename} (saved to {file_location})")
    print(f"")
    print(f"Financial Breakdown:")
    print(f"  Subtotal: ${subtotal_amount:.2f} CAD")
    print(f"  Discount: -${discount_amount:.2f} CAD")
    print(f"  HST/GST: ${hst_gst_amount:.2f} CAD")
    print(f"  Shipping: ${shipping_amount:.2f} CAD")
    print(f"  Total Amount: ${total_amount:.2f} CAD")
    print(f"")
    print("Items:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['name']}")
        print(f"     Usage: {item['usage']}")
        print(f"     Quantity: {item['quantity']}")
        print(f"     Unit Price: ${item['unit_price']:.2f}")
        print(f"     Total: ${item['total']:.2f}")
        print()
    print("-" * 50)
    
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
