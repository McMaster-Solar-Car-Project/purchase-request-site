import os
import shutil
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Request,
    Form,
    File,
    UploadFile,
    HTTPException,
    Depends,
    status,
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from data_processing import create_excel_report, copy_expense_report_template
from logging_utils import setup_logger
from google_sheets import log_purchase_request_to_sheets
from google_drive import (
    upload_session_to_drive_background,
    create_drive_folder_and_get_url,
)
from database import get_db, init_database
from user_service import (
    get_user_by_email,
    get_user_signature_as_data_url,
    is_user_profile_complete,
    save_signature_to_file,
)
from request_logging import RequestLoggingMiddleware

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Configuration
SESSION_CLEANUP_AGE_SECONDS = 60 * 24 * 60 * 60  # Delete sessions older than 60 days
SESSION_CLEANUP_CHECK_INTERVAL = (
    60 * 60
)  # Check for old sessions every hour (3600 seconds)

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions", "static", "templates", "excel_templates"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)


# Background task control
cleanup_task = None


async def cleanup_old_sessions():
    """Background task to clean up session folders older than configured age"""
    while True:
        try:
            current_time = datetime.now()
            sessions_dir = "sessions"

            if not os.path.exists(sessions_dir):
                await asyncio.sleep(SESSION_CLEANUP_CHECK_INTERVAL)
                continue

            deleted_count = 0

            # Check each session folder
            for folder_name in os.listdir(sessions_dir):
                folder_path = os.path.join(sessions_dir, folder_name)

                # Skip if not a directory
                if not os.path.isdir(folder_path):
                    continue

                # Get folder creation time
                folder_creation_time = datetime.fromtimestamp(
                    os.path.getctime(folder_path)
                )

                # Check if folder is older than configured age
                age = current_time - folder_creation_time
                if age.total_seconds() > SESSION_CLEANUP_AGE_SECONDS:
                    try:
                        shutil.rmtree(folder_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to delete session folder {folder_name}: {e}"
                        )

            # Only log if many folders were deleted (indicates potential issue)
            if deleted_count > 10:
                logger.info(f"🧹 Deleted {deleted_count} old session folders")

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

        # Wait before next cleanup check
        await asyncio.sleep(SESSION_CLEANUP_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown"""
    global cleanup_task

    # Initialize database on startup
    init_database()

    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_old_sessions())

    yield  # Application runs here

    # Shutdown: Stop cleanup task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Purchase Request Site", lifespan=lifespan)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-this"),
)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Set up templates
templates = Jinja2Templates(directory="templates")

# Authentication configuration
LOGIN_EMAIL = os.getenv("LOGIN_EMAIL", "admin@example.com")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "admin123")


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated via session"""
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    """Dependency to require authentication"""
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )


@app.get("/login")
async def login_page(request: Request, error: str = None):
    """Display login page"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error_message": "Invalid email or password"
            if error == "invalid"
            else None,
        },
    )


@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission"""
    # Check if it's the admin login
    if email == LOGIN_EMAIL and password == LOGIN_PASSWORD:
        request.session["authenticated"] = True
        request.session["user_email"] = email
        request.session["is_admin"] = True
        return RedirectResponse(url="/", status_code=303)

    # Check user database
    user = get_user_by_email(db, email)
    if user and user.password == password:
        request.session["authenticated"] = True
        request.session["user_email"] = email
        request.session["is_admin"] = False

        # Check if user profile is complete
        if is_user_profile_complete(user):
            # Create a session folder with existing user data
            session_folder = create_session_folder(user.name)

            # Save user's signature to session folder for dashboard use
            signature_filename = "signature.png"
            signature_path = f"{session_folder}/{signature_filename}"
            if save_signature_to_file(user, signature_path):
                # Redirect directly to dashboard, skipping user info form
                return RedirectResponse(
                    url=f"/dashboard?user_email={email}&session_folder={session_folder}&signature={signature_filename}",
                    status_code=303,
                )

        # If profile incomplete, go to edit profile page
        return RedirectResponse(
            url=f"/edit-profile?user_email={email}", status_code=303
        )
    else:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error_message": "Invalid email or password",
                "email": email,
            },
        )


@app.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/")
async def home(request: Request):
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


@app.get("/download-excel")
async def download_excel(
    request: Request,
    session_folder: str,
    excel_file: str,
    _: None = Depends(require_auth),
):
    """Download the generated Excel file for a session"""
    file_path = f"{session_folder}/{excel_file}"

    # Security check: ensure the path is within the sessions directory
    if not session_folder.startswith("sessions/"):
        raise HTTPException(status_code=400, detail="Invalid session folder")

    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="Excel file not found")

    # Return the file for download
    return FileResponse(
        path=file_path,
        filename=excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def create_session_folder(name):
    """Create a unique session folder name with user name and timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").lower()
    session_folder = f"sessions/{safe_name}_{timestamp}"

    # Create the session directory if it doesn't exist
    os.makedirs(session_folder, exist_ok=True)

    return session_folder


@app.get("/dashboard")
async def dashboard(
    request: Request,
    user_email: str,
    session_folder: str = None,
    signature: str = None,
    use_saved: bool = False,
    updated: bool = False,
    error: str = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    # Get user from database
    user = get_user_by_email(db, user_email)
    if not user:
        logger.error(f"User not found in database: {user_email}")
        raise HTTPException(status_code=404, detail="User not found")

    # If use_saved is True, create session folder and signature for existing user
    if use_saved and not session_folder:
        session_folder = create_session_folder(user.name)
        signature_filename = "signature.png"
        signature_path = f"{session_folder}/{signature_filename}"
        if save_signature_to_file(user, signature_path):
            signature = signature_filename
        else:
            logger.warning(f"Could not save signature for user {user_email}")
            signature = "signature.png"  # Default filename

    error_message = None
    success_message = None

    if error == "no_forms":
        error_message = "Please complete at least one invoice form before submitting. Make sure to fill in the vendor name, upload an invoice file, and add at least one item."
    elif updated:
        success_message = "✅ Your profile has been updated successfully!"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "user_name": user.name,
            "user_email": user.email,
            "name": user.name,
            "email": user.email,
            "e_transfer_email": user.personal_email,
            "address": user.address,
            "team": user.team,
            "session_folder": session_folder,
            "signature": signature,
            "error_message": error_message,
            "success_message": success_message,
        },
    )


@app.post("/submit-all-requests")
async def submit_all_requests(request: Request, _: None = Depends(require_auth)):
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
        currency = form_data.get(
            f"currency_{form_num}", "CAD"
        )  # Default to CAD if not specified

        # Skip empty forms (no vendor name or invoice)
        if not vendor_name or not invoice_file or not hasattr(invoice_file, "filename"):
            continue

        # For USD purchases, proof of payment is required
        if currency == "USD" and (
            not proof_of_payment_file or not hasattr(proof_of_payment_file, "filename")
        ):
            logger.warning(
                f"Form {form_num} in USD currency missing proof of payment - skipping"
            )
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
            total_amount = (
                canadian_amount  # Use Canadian amount as total for reimbursement
            )
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
                parsed_total = float(item_total) if item_total else 0
                items.append(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": int(item_quantity),
                        "unit_price": float(item_price),
                        "total": parsed_total,
                    }
                )

            item_num += 1

        # Skip forms with no items
        if not items:
            continue

        # Save uploaded invoice file in session folder
        invoice_extension = (
            invoice_file.filename.split(".")[-1]
            if "." in invoice_file.filename
            else "pdf"
        )
        invoice_filename = f"{form_num}_{vendor_name}.{invoice_extension}"
        invoice_file_location = f"{session_folder}/{invoice_filename}"

        # Save the invoice file
        with open(invoice_file_location, "wb") as file_object:
            content = await invoice_file.read()
            file_object.write(content)

        # Save proof of payment file only for USD currency
        proof_of_payment_filename = None
        proof_of_payment_location = None
        if (
            currency == "USD"
            and proof_of_payment_file
            and hasattr(proof_of_payment_file, "filename")
        ):
            payment_extension = (
                proof_of_payment_file.filename.split(".")[-1]
                if "." in proof_of_payment_file.filename
                else "pdf"
            )
            proof_of_payment_filename = (
                f"{form_num}_proof_of_payment.{payment_extension}"
            )
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
            "items": items,
        }

        submitted_forms.append(form_submission)

    # Print all submitted forms
    if submitted_forms:
        # Create Excel export in session folder
        user_info = {
            "name": name,
            "email": email,
            "e_transfer_email": e_transfer_email,
            "address": address,
            "team": team,
            "signature": signature_filename,
        }

        create_excel_report(user_info, submitted_forms, session_folder)

        # Copy expense report template to session folder
        try:
            copy_expense_report_template(session_folder, user_info, submitted_forms)
        except Exception as e:
            logger.error(
                f"Failed to copy and populate expense report template (continuing anyway): {e}"
            )

        # Create Google Drive folder and get URL
        drive_folder_url = ""
        drive_folder_id = ""
        try:
            drive_folder_url, drive_folder_id = create_drive_folder_and_get_url(
                session_folder, user_info
            )
        except Exception as e:
            logger.error(
                f"Failed to create Google Drive folder (continuing anyway): {e}"
            )

        # Log to Google Sheets (with Drive folder URL)
        try:
            log_purchase_request_to_sheets(
                user_info, submitted_forms, session_folder, drive_folder_url
            )
        except Exception as e:
            logger.error(f"Failed to log to Google Sheets (continuing anyway): {e}")

        # Upload files to Google Drive (in background)
        try:
            upload_session_to_drive_background(
                session_folder, user_info, drive_folder_id
            )
        except Exception as e:
            logger.error(
                f"Failed to start Google Drive upload (continuing anyway): {e}"
            )

    else:
        logger.warning("No forms were submitted (all forms were empty)")
        # Redirect back to dashboard with error message instead of success
        return RedirectResponse(
            url=f"/dashboard?user_email={email}&session_folder={session_folder}&signature={signature_filename}&error=no_forms",
            status_code=303,
        )

    # Redirect back to home with success message and session info for download
    return RedirectResponse(
        url=f"/success?session_folder={session_folder}&excel_file=purchase_request.xlsx&user_email={email}",
        status_code=303,
    )


@app.get("/success")
async def success_page(
    request: Request,
    session_folder: str = None,
    excel_file: str = None,
    user_email: str = None,
    _: None = Depends(require_auth),
):
    """Display success page after purchase request submission"""
    download_info = None
    current_time = datetime.now()

    if session_folder and excel_file:
        download_info = {
            "session_folder": session_folder,
            "excel_file": excel_file,
            "download_url": f"/download-excel?session_folder={session_folder}&excel_file={excel_file}",
        }

    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "download_info": download_info,
            "user_email": user_email,
            "current_time": current_time,
        },
    )


@app.get("/edit-profile")
async def edit_profile_get(
    request: Request,
    user_email: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = get_user_by_email(db, user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert signature to data URL for display
    signature_data_url = get_user_signature_as_data_url(user)

    return templates.TemplateResponse(
        "edit_profile.html",
        {
            "request": request,
            "title": "Edit Profile - Purchase Request Site",
            "user": user,
            "signature_data_url": signature_data_url,
            "google_api_key": os.getenv("GOOGLE_PLACES_API_KEY"),
        },
    )


@app.post("/edit-profile")
async def edit_profile_post(
    request: Request,
    user_email: str,
    name: str = Form(...),
    email: str = Form(...),
    personal_email: str = Form(...),
    team: str = Form(...),
    address: str = Form(...),
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    signature: UploadFile = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    try:
        # Get existing user
        user = get_user_by_email(db, user_email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user information (strip whitespace from all fields)
        user.name = name.strip()
        user.email = email.strip()
        user.personal_email = personal_email.strip()
        user.team = team.strip()
        user.address = address.strip()

        # Handle password change if provided (strip whitespace from passwords too)
        current_password = current_password.strip()
        new_password = new_password.strip()
        confirm_password = confirm_password.strip()

        password_error = None
        if new_password or current_password:
            if not current_password:
                password_error = "Current password is required to change password"
            elif not new_password:
                password_error = "New password cannot be empty"
            elif len(new_password) < 5:
                password_error = "New password must be at least 5 characters"
            elif new_password != confirm_password:
                password_error = "New password and confirmation do not match"
            elif user.password != current_password:
                password_error = "Current password is incorrect"
            else:
                # All validations passed, update password
                user.password = new_password

        if password_error:
            logger.warning(f"Password change failed for {email}: {password_error}")
            # You could redirect with error, but for now we'll continue with other updates
            # and show the error in logs

        # Handle signature update if provided
        if signature and signature.filename:
            # Read the signature file content
            signature_content = await signature.read()
            if signature_content:
                # Save signature content directly to database as binary data
                user.signature_data = signature_content

        # Save changes to database
        db.commit()

        # Redirect back to dashboard with success message
        redirect_url = f"/dashboard?user_email={email}&use_saved=true&updated=true"
        return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.error(f"Error updating profile for {user_email}: {str(e)}")
        db.rollback()

        # Redirect back to edit form with error
        return RedirectResponse(
            url=f"/edit-profile?user_email={user_email}&error=update_failed",
            status_code=303,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
