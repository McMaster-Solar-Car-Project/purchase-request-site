import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

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
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Purchase Request Site",
        "heading": "Enter your purchase request information",
        "success_message": success_message,
        "google_api_key": os.getenv("GOOGLE_PLACES_API_KEY")
    })

@app.post("/submit-request")
async def submit_request(
    name: str = Form(...),
    email: str = Form(...),
    address: str = Form(...),
    team: str = Form(...),
    request_details: str = Form("")
):
    # Here you would typically save to a database
    # For now, we'll just print the data and redirect
    print(f"New purchase request received:")
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Address: {address}")
    print(f"Team: {team}")
    print(f"Request Details: {request_details}")
    print("-" * 50)
    
    # Redirect back to home with success message
    return RedirectResponse(url="/?success=true", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=os.getenv("HOST", "0.0.0.0"), 
        port=int(os.getenv("PORT", 8000)), 
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
