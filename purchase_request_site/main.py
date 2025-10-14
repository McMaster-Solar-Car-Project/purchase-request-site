import asyncio
import os
import secrets
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime

from data_processing import create_expense_report, create_purchase_request
from database import get_db, init_database
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google_drive import (
    create_drive_folder_and_get_url,
    download_file_from_drive,
    upload_session_to_drive,
)
from google_sheets import GoogleSheetsClient
from image_processing import convert_signature_to_png
from logging_utils import setup_logger
from request_logging import RequestLoggingMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from user_service import (
    get_user_by_email,
    get_user_signature_as_data_url,
    is_user_profile_complete,
    save_signature_to_file,
)

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
                    except Exception:
                        logger.exception(
                            f"Failed to delete session folder {folder_name}"
                        )

            # Only log if many folders were deleted (indicates potential issue)
            if deleted_count > 10:
                logger.info(f"🧹 Deleted {deleted_count} old session folders")

            # Wait before next cleanup check
            await asyncio.sleep(SESSION_CLEANUP_CHECK_INTERVAL)

        except Exception:
            logger.exception("Error during session cleanup")

            # Sleep for a bit to avoid tight loop in case of persistent error
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown"""
    global cleanup_task

    logger.info(f"Starting application lifespan on {datetime.now().isoformat()}")

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

# Generate a random secret key for this session (Note: users will be logged out on restart)
session_secret = secrets.token_urlsafe(32)

# Add session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Set up templates
templates_dir = (
    "purchase_request_site/templates"
    if os.path.exists("purchase_request_site/templates")
    else "templates"
)
templates = Jinja2Templates(directory=templates_dir)


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
    # Check user database
    user = get_user_by_email(db, email)
    if user and user.password == password:
        request.session["authenticated"] = True
        request.session["user_email"] = email
        logger.info(f"🔐 User login: {user.name} ({email})")

        # Check if user profile is complete
        if is_user_profile_complete(user):
            # Redirect directly to dashboard
            return RedirectResponse(
                url=f"/dashboard?user_email={email}",
                status_code=303,
            )

        # If profile incomplete, go to edit profile page
        return RedirectResponse(
            url=f"/edit-profile?user_email={email}", status_code=303
        )
    else:
        logger.warning(f"🚫 Failed login attempt: {email}")
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


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/download-excel")
async def download_excel(
    request: Request,
    drive_folder_id: str,
    excel_file: str,
    _: None = Depends(require_auth),
):
    """Download the generated Excel file from Google Drive"""
    try:
        file_content = download_file_from_drive(drive_folder_id, excel_file)
        # Return the file content as a streaming response
        from fastapi.responses import Response

        return Response(
            content=file_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={excel_file}"},
        )

    except Exception:
        logger.exception(f"Failed to download {excel_file} from Google Drive")
        raise HTTPException(
            status_code=404, detail="Excel file not found in Google Drive"
        ) from None


def create_session_folder(name):
    """Create a session folder with user name and timestamp"""
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
    updated: bool = False,
    error: str = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    # Get user from database
    user = get_user_by_email(db, user_email)
    if not user:
        logger.exception(f"User not found in database: {user_email}")
        raise HTTPException(status_code=404, detail="User not found")

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
            "error_message": error_message,
            "success_message": success_message,
        },
    )


@app.post("/submit-all-requests")
async def submit_all_requests(
    request: Request, db: Session = Depends(get_db), _: None = Depends(require_auth)
):
    # Get form data
    form_data = await request.form()

    # Extract user information
    name = form_data.get("name")
    email = form_data.get("email")
    e_transfer_email = form_data.get("e_transfer_email")
    address = form_data.get("address")
    team = form_data.get("team")

    # Create session folder dynamically
    session_folder = create_session_folder(name)

    # Get user from database to fetch signature
    user = get_user_by_email(db, email)
    if not user:
        logger.exception(f"User not found in database: {email}")
        raise HTTPException(status_code=404, detail="User not found")

    # Save user's signature to session folder
    signature_filename = "signature.png"
    signature_path = f"{session_folder}/{signature_filename}"
    if not save_signature_to_file(user, signature_path):
        logger.warning(f"Could not save signature for user {email}")

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
            us_total = float(form_data.get(f"us_total_{form_num}") or 0)
            usd_taxes = float(form_data.get(f"usd_taxes_{form_num}") or 0)
            canadian_amount = float(form_data.get(f"canadian_amount_{form_num}") or 0)
            subtotal_amount = discount_amount = shipping_amount = 0
            hst_gst_amount = usd_taxes
            total_amount = canadian_amount
        else:
            subtotal_amount = float(form_data.get(f"subtotal_amount_{form_num}") or 0)
            discount_amount = float(form_data.get(f"discount_amount_{form_num}") or 0)
            hst_gst_amount = float(form_data.get(f"hst_gst_amount_{form_num}") or 0)
            shipping_amount = float(form_data.get(f"shipping_amount_{form_num}") or 0)
            total_amount = float(form_data.get(f"total_amount_{form_num}") or 0)
            us_total = usd_taxes = canadian_amount = 0

        # Extract items for this form
        items = []
        for item_num in range(1, 50):  # Reasonable limit
            item_name = form_data.get(f"item_name_{form_num}_{item_num}")
            if not item_name:
                break
            item_usage = form_data.get(f"item_usage_{form_num}_{item_num}")
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")

            if item_name and item_usage and item_quantity and item_price:
                items.append(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": int(item_quantity),
                        "unit_price": float(item_price),
                        "total": float(item_total or 0),
                    }
                )

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
        proof_of_payment_filename = proof_of_payment_location = None
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
            with open(proof_of_payment_location, "wb") as file_object:
                file_object.write(await proof_of_payment_file.read())

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
        try:
            create_purchase_request(user_info, submitted_forms, session_folder)
        except Exception:
            logger.exception("Failed to create purchase request (continuing anyway)")

        # Copy expense report template to session folder
        try:
            create_expense_report(session_folder, user_info, submitted_forms)
        except Exception:
            logger.exception(
                "Failed to copy and populate expense report template (continuing anyway)"
            )

        # Create Google Drive folder and get URL
        drive_folder_url = ""
        drive_folder_id = ""
        try:
            drive_folder_url, drive_folder_id = create_drive_folder_and_get_url(
                session_folder, user_info
            )
        except Exception:
            logger.exception("Failed to create Google Drive folder (continuing anyway)")

        # Log to Google Sheets (with Drive folder URL)
        try:
            sheets_client = GoogleSheetsClient()
            sheets_client.log_purchase_request(
                user_info, submitted_forms, session_folder, drive_folder_url
            )
            sheets_client.close()
        except Exception:
            logger.exception("Failed to log to Google Sheets (continuing anyway)")

        # Upload files to both Google Drive and Supabase concurrently
        drive_upload_success = False
        supabase_upload_success = False

        def upload_to_drive():
            """Upload to Google Drive and return success status"""
            try:
                return upload_session_to_drive(
                    session_folder, user_info, drive_folder_id
                )
            except Exception:
                logger.exception(
                    "Failed to start Google Drive upload (continuing anyway)"
                )
                return False

        # Run both uploads concurrently
        logger.info("Starting concurrent uploads to Google Drive and Supabase...")
        drive_upload_success = False
        supabase_upload_success = False
        try:
            drive_upload_success = upload_to_drive()
            logger.info(
                f"Google Drive upload completed: {'✅ Success' if drive_upload_success else '❌ Failed'}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error in upload task: {e}")

        # Clean up session folder if at least one upload was successful
        if drive_upload_success or supabase_upload_success:
            try:
                shutil.rmtree(session_folder)
                logger.info(f"🗑️ Cleaned up session folder: {session_folder}")
            except Exception:
                logger.exception(f"Failed to delete session folder {session_folder}")

    else:
        logger.warning("No forms were submitted (all forms were empty)")
        # Redirect back to dashboard with error message instead of success
        return RedirectResponse(
            url=f"/dashboard?user_email={email}&error=no_forms",
            status_code=303,
        )

    # Redirect back to home with success message and session info for download
    return RedirectResponse(
        url=f"/success?drive_folder_id={drive_folder_id}&excel_file=purchase_request.xlsx&user_email={email}",
        status_code=303,
    )


@app.get("/success")
async def success_page(
    request: Request,
    drive_folder_id: str = None,
    excel_file: str = None,
    user_email: str = None,
    _: None = Depends(require_auth),
):
    """Display success page after purchase request submission"""
    download_info = None
    current_time = datetime.now()

    if drive_folder_id and excel_file:
        download_info = {
            "drive_folder_id": drive_folder_id,
            "excel_file": excel_file,
            "download_url": f"/download-excel?drive_folder_id={drive_folder_id}&excel_file={excel_file}",
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
                # Create a temporary file to save the uploaded signature
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{signature.filename.split('.')[-1]}"
                ) as temp_file:
                    temp_file.write(signature_content)
                    temp_signature_path = temp_file.name

                # Create a temporary PNG file path
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".png"
                ) as temp_png_file:
                    temp_png_path = temp_png_file.name

                try:
                    # Convert signature to PNG
                    if convert_signature_to_png(temp_signature_path, temp_png_path):
                        # Read the converted PNG content
                        with open(temp_png_path, "rb") as png_file:
                            png_content = png_file.read()
                        # Save PNG content to database
                        user.signature_data = png_content
                        logger.info(
                            f"Signature converted to PNG and saved for user {email}"
                        )
                    else:
                        logger.warning(
                            f"Failed to convert signature to PNG for user {email}"
                        )
                        # Fallback: save original content
                        user.signature_data = signature_content
                finally:
                    # Clean up temporary files
                    try:
                        os.unlink(temp_signature_path)
                        os.unlink(temp_png_path)
                    except OSError:
                        pass  # Ignore cleanup errors

        # Save changes to database
        db.commit()

        # Redirect back to dashboard with success message
        redirect_url = f"/dashboard?user_email={email}&updated=true"
        return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.exception(f"Error updating profile for {user_email}: {str(e)}")
        db.rollback()

        # Redirect back to edit form with error
        return RedirectResponse(
            url=f"/edit-profile?user_email={user_email}&error=update_failed",
            status_code=303,
        )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
