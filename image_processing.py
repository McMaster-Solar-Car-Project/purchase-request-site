import os
import cv2
import numpy as np
from PIL import Image
from openpyxl.drawing import image

def crop_signature(input_image, output_path=None):
    """Crop signature to remove excess whitespace using OpenCV
    
    Args:
        input_image: Can be either a file path (str) or PIL Image object
        output_path: Optional path to save cropped image (only used if input_image is a path)
    
    Returns:
        - If input_image is a path: returns output_path or None if failed
        - If input_image is PIL Image: returns cropped PIL Image
    """
    try:
        # Handle input type
        if isinstance(input_image, str):
            # Input is a file path
            img = cv2.imread(input_image)
            if img is None:
                print(f"Could not load image: {input_image}")
                return None
            is_file_input = True
            original_pil = None
        else:
            # Input is a PIL Image
            original_pil = input_image
            img_array = np.array(input_image)
            
            # Handle different image modes
            if len(img_array.shape) == 3:
                if img_array.shape[2] == 4:  # RGBA
                    img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                else:  # RGB
                    img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:  # Grayscale
                img = img_array
            is_file_input = False
            
        # Resize if image is very large (width > 1000px)
        height, width = img.shape[:2]
        scale_factor = 1.0
        if width > 1000:
            scale_factor = 1000 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            img = cv2.resize(img, (new_width, new_height))
        
        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Apply adaptive threshold to isolate signature
        thresh_gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 10
        )
        
        # Invert so signature pixels are white (255)
        thresh_gray = cv2.bitwise_not(thresh_gray)
        
        # Find signature pixels
        points = np.argwhere(thresh_gray == 255)
        
        if len(points) == 0:
            print("No signature content found")
            return original_pil if not is_file_input else None
            
        # Get bounding rectangle
        points = np.fliplr(points)  # Convert row,col to x,y
        x, y, w, h = cv2.boundingRect(points)
        
        # Add padding (10% of dimensions, minimum 10 pixels)
        padding_x = max(10, int(w * 0.1))
        padding_y = max(10, int(h * 0.1))
        
        # Apply scale factor back to coordinates if image was resized
        if scale_factor != 1.0:
            x = int(x / scale_factor)
            y = int(y / scale_factor)
            w = int(w / scale_factor)
            h = int(h / scale_factor)
            padding_x = int(padding_x / scale_factor)
            padding_y = int(padding_y / scale_factor)
        
        # Expand bounding box with padding
        if is_file_input:
            # Use original image dimensions
            original_img = cv2.imread(input_image)
            img_height, img_width = original_img.shape[:2]
            x = max(0, x - padding_x)
            y = max(0, y - padding_y)
            w = min(img_width - x, w + 2 * padding_x)
            h = min(img_height - y, h + 2 * padding_y)
            
            # Crop the original image
            cropped = original_img[y:y+h, x:x+w]
            
            # Save cropped image
            if output_path is None:
                base, ext = os.path.splitext(input_image)
                output_path = f"{base}_cropped{ext}"
            
            cv2.imwrite(output_path, cropped)
            print(f"Signature cropped and saved to: {output_path}")
            return output_path
        else:
            # Use PIL image dimensions
            img_width, img_height = original_pil.size
            x = max(0, x - padding_x)
            y = max(0, y - padding_y)
            w = min(img_width - x, w + 2 * padding_x)
            h = min(img_height - y, h + 2 * padding_y)
            
            # Crop the PIL image
            cropped_pil = original_pil.crop((x, y, x + w, y + h))
            print(f"Signature cropped (removed {x}px left, {y}px top)")
            return cropped_pil
            
    except Exception as e:
        print(f"Error cropping signature: {e}")
        return original_pil if not is_file_input else None

def convert_signature_to_png(signature_path, output_path):
    """Convert signature image to PNG format for Excel compatibility
    Supports: PNG, JPG, JPEG, GIF, PDF formats
    Includes automatic cropping to remove excess whitespace"""
    try:
        # Check if it's a PDF file
        if signature_path.lower().endswith('.pdf'):
            try:
                from pdf2image import convert_from_path
                # Convert PDF to images (take first page only for signature)
                pages = convert_from_path(signature_path, first_page=1, last_page=1)
                if pages:
                    img = pages[0]  # Use first page
                    # Crop the PDF-converted image
                    img = crop_signature(img)
                else:
                    print(f"No pages found in PDF: {signature_path}")
                    return False
            except ImportError:
                print("pdf2image library not installed. Cannot convert PDF files.")
                print("Install with: pip install pdf2image")
                return False
            except Exception as e:
                print(f"Error converting PDF: {e}")
                return False
        else:
            # Handle regular image formats (PNG, JPG, GIF, etc.)
            img = Image.open(signature_path)
            # Crop the regular image
            img = crop_signature(img)
        
        # Convert to RGBA (supports transparency)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Resize if too large (max 200px width, maintain aspect ratio)
        max_width = 200
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Save as PNG
        img.save(output_path, 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f"Error converting signature: {e}")
        return False

def insert_signature_into_worksheet(ws, user_info, form, session_folder):
    """Insert signature image into Excel worksheet"""
    signature_path = f"{session_folder}/{user_info['signature']}"
    if os.path.exists(signature_path):
        # Convert signature to PNG
        signature_png_path = f"{session_folder}/signature_form_{form['form_number']}.png"
        if convert_signature_to_png(signature_path, signature_png_path):
            try:
                # Insert signature image at cell G3 (next to user info)
                img = image.Image(signature_png_path)
                img.anchor = 'G3'  # Position at cell G3
                img.width = 150   # Set width (adjust as needed)
                img.height = 50   # Set height (adjust as needed)
                ws.add_image(img)
                print(f"Signature inserted for form {form['form_number']}")
                return True
            except Exception as e:
                print(f"Error inserting signature for form {form['form_number']}: {e}")
                return False
        else:
            print(f"Failed to convert signature for form {form['form_number']}")
            return False
    else:
        print(f"Signature file not found: {signature_path}")
        return False 