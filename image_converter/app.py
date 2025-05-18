from flask import Flask, request, send_file, send_from_directory
from PIL import Image
import cv2
import numpy as np
import io

app = Flask(__name__)

@app.route('/')
def index():
    return send_from_directory('.', 'comic_converter.html')

def create_edge_mask(image, line_threshold=7, blur_value=7):
    """Create bold comic-style edges"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.medianBlur(gray, blur_value)
    
    # Create edge mask using adaptive threshold
    edges = cv2.adaptiveThreshold(
        gray_blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
        cv2.THRESH_BINARY, line_threshold, blur_value
    )
    
    return edges

def reduce_colors(image, k=8):
    """Reduce color palette for comic effect"""
    # Reshape image to a 2D array of pixels
    data = image.reshape((-1, 3))
    data = np.float32(data)
    
    # Apply K-means clustering to reduce colors
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 5, 1.0)
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Convert back to uint8 and reshape
    centers = np.uint8(centers)
    reduced_data = centers[labels.flatten()]
    reduced_image = reduced_data.reshape(image.shape)
    
    return reduced_image

def enhance_colors(image, saturation_boost=80, brightness_boost=30):
    """Enhance colors for vibrant comic look"""
    # Convert to HSV for better color manipulation
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    # Boost saturation
    s = cv2.add(s, saturation_boost)
    s = np.clip(s, 0, 255)
    
    # Boost brightness/value
    v = cv2.add(v, brightness_boost)
    v = np.clip(v, 0, 255)
    
    # Merge channels back
    enhanced_hsv = cv2.merge([h, s, v])
    enhanced_bgr = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)
    
    return enhanced_bgr

def cartoonize_image(image_np):
    """Advanced cartoon effect with bright colors"""
    # Apply bilateral filter to smooth the image while keeping edges sharp
    smooth = cv2.bilateralFilter(image_np, 15, 60, 60)
    smooth = cv2.bilateralFilter(smooth, 15, 60, 60)
    
    # Reduce color palette
    reduced_colors = reduce_colors(smooth, k=8)
    
    # Create edge mask
    edges = create_edge_mask(image_np)
    edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    edges = edges / 255.0  # Normalize to 0-1
    
    # Combine reduced colors with edges
    cartoon = reduced_colors * edges
    cartoon = np.uint8(cartoon)
    
    # Enhance colors for vibrant comic look
    vibrant_cartoon = enhance_colors(cartoon, saturation_boost=80, brightness_boost=30)
    
    # Optional: Apply slight gaussian blur for smoother look
    final_cartoon = cv2.GaussianBlur(vibrant_cartoon, (3, 3), 0)
    
    return final_cartoon

@app.route('/convert-comic', methods=['POST'])
def convert_comic():
    if 'image' not in request.files:
        return 'No image uploaded', 400
    
    file = request.files['image']
    if file.filename == '':
        return 'No image selected', 400
    
    try:
        # Read image from memory
        in_memory_file = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(in_memory_file, cv2.IMREAD_COLOR)
        
        if img is None:
            return 'Failed to decode image', 400
        
        # Apply comic conversion
        cartoon = cartoonize_image(img)
        
        # Encode as PNG
        success, buffer = cv2.imencode('.png', cartoon)
        if not success:
            return 'Failed to encode image', 500
        
        # Send the processed image
        io_buf = io.BytesIO(buffer)
        return send_file(io_buf, mimetype='image/png', as_attachment=False)
        
    except Exception as e:
        return f'Error processing image: {str(e)}', 500

if __name__ == '__main__':
    app.run(debug=True)