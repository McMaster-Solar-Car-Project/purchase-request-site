import os
import shutil
from PIL import Image
from openpyxl.drawing import image
import matplotlib.pyplot as plt
import cv2
import numpy as np

def detect_and_crop_signature(input_path, output_path=None):
    """Convert image to grayscale and apply basic processing
    
    Args:
        input_path: Path to input image file
        output_path: Path to save processed image
    
    Returns:
        True if processing successful, False otherwise
    """
    try:
        # Read the image in color first
        img = cv2.imread(input_path)
        if img is None:
            print(f"Could not read image: {input_path}")
            return False
            
        print(f"Processing image: {input_path}")
        print(f"Original image dimensions: {img.shape}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Background subtraction approach for signature enhancement
        dilated_img = cv2.dilate(gray, np.ones((7,7), np.uint8)) 
        bg_img = cv2.medianBlur(dilated_img, 21)
        diff_img = 255 - cv2.absdiff(gray, bg_img)
        norm_img = diff_img.copy() # Needed for 3.x compatibility
        cv2.normalize(diff_img, norm_img, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
        _, thr_img = cv2.threshold(norm_img, 230, 0, cv2.THRESH_TRUNC)
        cv2.normalize(thr_img, thr_img, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)

        # Apply final threshold to clean up the image
        retval, final_result = cv2.threshold(thr_img, thresh=0, maxval=255, type=cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Save the result
        if output_path:
            cv2.imwrite(output_path, final_result)
            trim_whitespace(output_path, output_path)
            print(f"Processed image saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"Error in image processing: {e}")
        import traceback
        traceback.print_exc()
        return False

def trim_whitespace(image_path, output_path=None):
    """
    Trim whitespace from all edges of an image.
    A row/column is considered whitespace if ALL pixels have RGB values > (245, 245, 245).
    
    Args:
        image_path (str): Path to the input image
        output_path (str, optional): Path to save the trimmed image. If None, overwrites original.
    
    Returns:
        PIL.Image: The trimmed image
    """
    # Open the image
    img = Image.open(image_path)
    
    # Convert to RGB if necessary
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Convert to numpy array for easier processing
    img_array = np.array(img)
    height, width = img_array.shape[:2]
    
    def is_all_white(pixels):
        """Check if ALL pixels in a row or column have RGB > (245, 245, 245)"""
        # Check if all pixels have R > 245 AND G > 245 AND B > 245
        return np.all(pixels > 235)
    
    def is_all_black(pixels):
        """Check if ALL pixels in a row or column have RGB > (245, 245, 245)"""
        # Check if all pixels have R > 245 AND G > 245 AND B > 245
        return np.all(pixels < 20)
    
    # Find top boundary
    top = 0
    for i in range(height):
        if not is_all_white(img_array[i]) and not is_all_black(img_array[i]):
            top = i
            break
    
    # Find bottom boundary
    bottom = height - 1
    for i in range(height - 1, -1, -1):
        if not is_all_white(img_array[i]) and not is_all_black(img_array[i]):
            bottom = i
            break
    
    # Find left boundary
    left = 0
    for i in range(width):
        if not is_all_white(img_array[:, i]) and not is_all_black(img_array[:, i]):
            left = i
            break   
    
    # Find right boundary
    right = width - 1
    for i in range(width - 1, -1, -1):
        if not is_all_white(img_array[:, i]) and not is_all_black(img_array[:, i]):
            right = i
            break
    
    # Handle edge case where entire image is white
    if top > bottom or left > right:
        print("Warning: Entire image appears to be white")
        return img
    
    # Crop the image
    cropped_img = img.crop((left, top, right + 1, bottom + 1))
    
    # Save the result
    if output_path:
        cropped_img.save(output_path)
    else:
        cropped_img.save(image_path)
    
    return cropped_img



def convert_signature_to_png(signature_path, output_path):
    """Convert signature image to PNG format for Excel compatibility
    Supports: PNG, JPG, JPEG, GIF, PDF formats"""
    try:
        print(f"Processing signature: {signature_path}")
        
        # Check if it's a PDF file first
        if signature_path.lower().endswith('.pdf'):
            # Handle PDF files - convert to image first
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(signature_path, first_page=1, last_page=1)
                if pages:
                    img = pages[0]
                    print("PDF converted to image successfully")
                else:
                    print(f"No pages found in PDF: {signature_path}")
                    return False
            except ImportError:
                print("pdf2image library not installed. Cannot convert PDF files.")
                return False
            except Exception as e:
                print(f"Error converting PDF: {e}")
                return False
        else:
            # For regular image formats, try intelligent cropping first
            success = detect_and_crop_signature(signature_path, output_path)
            
            if success:
                # Signature detected and cropped successfully
                return True
            else:
                # Fallback: basic format conversion without cropping
                print("Falling back to basic format conversion")
                img = Image.open(signature_path)
        
        # Convert to RGBA (supports transparency)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Resize if too large (max 400px width for initial conversion)
        max_width = 400
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
    # Look for the cropped signature first, then fall back to original
    cropped_signature_path = f"{session_folder}/signature.png"
    original_signature_path = f"{session_folder}/{user_info['signature']}"
    
    signature_path = cropped_signature_path if os.path.exists(cropped_signature_path) else original_signature_path
    
    if os.path.exists(signature_path):
        # Convert signature to PNG for Excel (if not already PNG)
        signature_png_path = f"{session_folder}/signature.png"
        if signature_path.endswith('.png'):
            # Already PNG, check if it's the same file
            if os.path.abspath(signature_path) != os.path.abspath(signature_png_path):
                # Different files, copy it
                shutil.copy2(signature_path, signature_png_path)
            # If it's the same file, no need to copy
            conversion_success = True
        else:
            # Convert to PNG
            conversion_success = convert_signature_to_png(signature_path, signature_png_path)
        
        if conversion_success:
            try:
                # Insert signature image at cell B25 (signature area)
                img = image.Image(signature_png_path)
                img.anchor = 'B25'  # Position at cell B25
                img.width = 280   # Set width for 5 cells wide (approximately)
                img.height = 70    # Set height for 3 cells high (approximately)
                ws.add_image(img)
                print(f"Signature inserted at B25 for form {form['form_number']}")
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
    