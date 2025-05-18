from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort,send_file, send_from_directory
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
import os
import uuid
from datetime import datetime
import base64
import re
import mimetypes
from PIL import Image
import cv2
import numpy as np
import io
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SESSION_TYPE'] = 'filesystem'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["paws_database"]
users_collection = db["users"]
scrapbooks_collection = db["scrapbooks"]

# Upload setup
UPLOAD_FOLDER = 'static/uploads'
STICKERS_FOLDER = 'static/stickers'
BACKGROUNDS_FOLDER = 'static/backgrounds'

# Create necessary directories if they don't exist
for folder in [UPLOAD_FOLDER, STICKERS_FOLDER, BACKGROUNDS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, folder=UPLOAD_FOLDER):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(folder, filename)
        file.save(file_path)
        return filename
    return None

def save_base64_image(base64_str, folder=UPLOAD_FOLDER):
    """Save a base64 encoded image and return the filename"""
    try:
        # Extract the actual base64 string from data URL
        if 'base64,' in base64_str:
            header, base64_str = base64_str.split('base64,', 1)
            mime_type = header.split(':')[1].split(';')[0]
            file_ext = mimetypes.guess_extension(mime_type)
        else:
            file_ext = '.jpg'  # Default extension
            
        # Decode the base64 string
        img_data = base64.b64decode(base64_str)
        
        # Generate unique filename
        filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(folder, filename)
        
        # Save the image
        with open(file_path, 'wb') as f:
            f.write(img_data)
            
        return filename
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return None

# Get list of available stickers and backgrounds
def get_stickers():
    stickers = []
    for file in os.listdir(STICKERS_FOLDER):
        if allowed_file(file):
            stickers.append(url_for('static', filename=f'stickers/{file}'))
    return stickers

def get_backgrounds():
    backgrounds = []
    for file in os.listdir(BACKGROUNDS_FOLDER):
        if allowed_file(file):
            backgrounds.append(url_for('static', filename=f'backgrounds/{file}'))
    return backgrounds

# Template filters
@app.template_filter('format_date')
def format_date(date):
    if not date:
        return "Unknown date"
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date)
        except:
            return date
    return date.strftime("%b %d, %Y")

@app.template_filter('image_url')
def image_url(image_filename):
    if not image_filename:
        return url_for('static', filename='images/default-profile.jpg')
    
    # Check if it's already a URL (starts with http or data:)
    if image_filename.startswith(('http://', 'https://', 'data:')):
        return image_filename
        
    # Otherwise, construct URL for uploaded file
    return url_for('static', filename=f'uploads/{image_filename}')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create')
def create():
    return render_template('create.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = users_collection.find_one({'username': username})
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['profile_type'] = user.get('profile_type', 'personal')
        
        # Determine redirect URL based on profile type
        if user.get('profile_type') == 'seller':
            return jsonify({
                'success': True,
                'redirect': url_for('home_seller'),
                'profile_type': 'seller'
            })
        else:
            return jsonify({
                'success': True,
                'redirect': url_for('home'),
                'profile_type': 'personal'
            })
    
    return jsonify({'success': False, 'message': 'Invalid username or password.'})
    
    return jsonify({'success': False, 'message': 'Invalid username or password.'})
@app.route('/create_profile/<profile_type>', methods=['GET', 'POST'])
def create_profile(profile_type):
    if request.method == 'GET':
        return redirect(url_for('create'))
    if profile_type not in ['personal', 'seller']:
        return jsonify({'success': False, 'message': 'Invalid profile type.'})
    
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    existing_user = users_collection.find_one({'username': username})
    if existing_user:
        return jsonify({'success': False, 'message': 'Username already taken!'})
    existing_email = users_collection.find_one({'email': email})
    if existing_email:
        return jsonify({'success': False, 'message': 'Email already registered!'})

    profile_image = request.files.get('profile_image')
    image_filename = save_file(profile_image) if profile_image else None

    user_data = {
        'username': username,
        'email': email,
        'password': generate_password_hash(password),
        'profile_type': profile_type,
        'created_at': datetime.utcnow()
    }
    if image_filename:
        user_data['profile_image'] = image_filename
    if profile_type == 'seller' and 'shop_name' in request.form:
        user_data['shop_name'] = request.form['shop_name']

    result = users_collection.insert_one(user_data)
    session['user_id'] = str(result.inserted_id)
    session['username'] = username
    session['profile_type'] = profile_type
    return jsonify({'success': True, 'redirect': url_for('home')})

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user:
        session.clear()
        return redirect(url_for('index'))
    return render_template('home.html', user=user)
@app.route('/home_seller')
def home_seller():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Get user from database
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    
    # Verify user exists and is a seller
    if not user:
        session.clear()
        return redirect(url_for('index'))
    
    if user.get('profile_type') != 'seller':
        flash('You need a seller account to access this page', 'error')
        return redirect(url_for('home'))
    
    # Simply render the seller home template without shop data
    return render_template('home_seller.html', user=user)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile/<username>')
def profile(username):
    user = users_collection.find_one({'username': username})
    if not user:
        abort(404)
    
    # Convert ObjectId to string for JSON serialization
    user_id = str(user['_id'])
    user['_id'] = user_id
    
    # Get user's scrapbooks
    scrapbooks = list(scrapbooks_collection.find({"user_id": user_id}))
    
    # Convert ObjectId to string in scrapbooks
    for sb in scrapbooks:
        sb['_id'] = str(sb['_id'])
    
    return render_template("profile.html", user=user, scrapbooks=scrapbooks)

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user:
        session.clear()
        return redirect(url_for('index'))

    updates = {}

    # ✅ Update username
    new_username = request.form.get('username', '').strip()
    if new_username and new_username != user['username']:
        # Check if username already exists
        existing = users_collection.find_one({'username': new_username})
        if existing and str(existing['_id']) != session['user_id']:
            flash('Username already taken!', 'error')
            return redirect(url_for('profile', username=user['username']))
        updates['username'] = new_username
        session['username'] = new_username  # Update session

    # ✅ Update profile image
    profile_image = request.files.get('profile_image')
    if profile_image and profile_image.filename:
        filename = save_file(profile_image)
        if filename:
            updates['profile_image'] = filename

    if updates:
        users_collection.update_one({'_id': user['_id']}, {'$set': updates})

    return redirect(url_for('profile', username=updates.get('username', user['username'])))


    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user:
        session.clear()
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Update user profile
        updates = {}
        
        # Update description
        description = request.form.get('description', '')
        updates['description'] = description
        
        # Update profile image if provided
        profile_image = request.files.get('profile_image')
        if profile_image and profile_image.filename:
            image_filename = save_file(profile_image)
            if image_filename:
                updates['profile_image'] = image_filename
        
        users_collection.update_one({'_id': user['_id']}, {'$set': updates})
        return redirect(url_for('profile', username=user['username']))

    return render_template('edit_profile.html', user=user)

# API routes
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        image_file = request.files.get('image')
        if image_file:
            filename = save_file(image_file)
            if filename:
                image_url = url_for('static', filename=f'uploads/{filename}')
                return jsonify({'success': True, 'url': image_url})
        
        # If no file upload, check for base64 data
        data = request.get_json()
        if data and 'image_data' in data:
            filename = save_base64_image(data['image_data'])
            if filename:
                image_url = url_for('static', filename=f'uploads/{filename}')
                return jsonify({'success': True, 'url': image_url})
                
        return jsonify({'success': False, 'error': 'No valid image provided'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stickers', methods=['GET'])
def list_stickers():
    stickers = get_stickers()
    return jsonify({'success': True, 'stickers': stickers})

@app.route('/api/backgrounds', methods=['GET'])
def list_backgrounds():
    backgrounds = get_backgrounds()
    return jsonify({'success': True, 'backgrounds': backgrounds})

# Scrapbook Routes
@app.route('/scrapbook/new')
def new_scrapbook():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    stickers = get_stickers()
    backgrounds = get_backgrounds()
    
    return render_template('scrapbook_editor.html', 
                           scrapbook=None, 
                           stickers=stickers,
                           backgrounds=backgrounds)

@app.route('/scrapbook/<scrapbook_id>')
def view_scrapbook(scrapbook_id):
    try:
        scrapbook = scrapbooks_collection.find_one({'_id': ObjectId(scrapbook_id)})
        if not scrapbook:
            return "Scrapbook not found", 404
            
        # Convert ObjectId to string
        scrapbook['_id'] = str(scrapbook['_id'])
        
        # Check privacy settings
        if scrapbook['privacy'] == 'private' and str(scrapbook['user_id']) != session.get('user_id'):
            return "This scrapbook is private.", 403
            
        # Get creator info
        creator = users_collection.find_one({'_id': ObjectId(scrapbook['user_id'])})
        if creator:
            creator['_id'] = str(creator['_id'])
        
        return render_template('scrapbook_view.html', scrapbook=scrapbook, creator=creator)
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/scrapbook/<scrapbook_id>/edit')
def edit_scrapbook(scrapbook_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    try:
        scrapbook = scrapbooks_collection.find_one({'_id': ObjectId(scrapbook_id)})
        if not scrapbook:
            return "Scrapbook not found", 404
            
        # Check ownership
        if str(scrapbook['user_id']) != session['user_id']:
            return "You don't have permission to edit this scrapbook.", 403
            
        # Convert ObjectId to string
        scrapbook['_id'] = str(scrapbook['_id'])
        
        # Get stickers and backgrounds
        stickers = get_stickers()
        backgrounds = get_backgrounds()
        
        return render_template('scrapbook_editor.html', 
                               scrapbook=scrapbook,
                               stickers=stickers,
                               backgrounds=backgrounds)
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/api/scrapbook/save', methods=['POST'])
def save_scrapbook():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
    try:
        data = request.get_json()
        scrapbook_id = data.get('_id')
        
        # Process cover image if it's a base64 string
        cover_image = data.get('cover_image', '')
        if cover_image and cover_image.startswith('data:image'):
            filename = save_base64_image(cover_image)
            if filename:
                data['cover_image'] = url_for('static', filename=f'uploads/{filename}')
                
        # Process any base64 images in elements
        if 'pages' in data:
            for page in data['pages']:
                if 'elements' in page:
                    for element in page['elements']:
                        if element['type'] in ['image', 'sticker'] and element.get('content', '').startswith('data:image'):
                            filename = save_base64_image(element['content'])
                            if filename:
                                element['content'] = url_for('static', filename=f'uploads/{filename}')
        
        # Prepare scrapbook data
        scrapbook_data = {
            'title': data.get('title', 'Untitled'),
            'cover_image': data.get('cover_image'),
            'privacy': data.get('privacy', 'private'),
            'pages': data.get('pages', []),
            'user_id': session['user_id'],
            'updated_at': datetime.utcnow()
        }
        
        # Add description if provided
        if 'description' in data:
            scrapbook_data['description'] = data['description']

        if scrapbook_id:
            # Update existing scrapbook
            existing = scrapbooks_collection.find_one({'_id': ObjectId(scrapbook_id)})
            if not existing or existing['user_id'] != session['user_id']:
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403
                
            scrapbooks_collection.update_one({'_id': ObjectId(scrapbook_id)}, {'$set': scrapbook_data})
            return jsonify({'success': True, 'id': scrapbook_id})
        else:
            # Create new scrapbook
            scrapbook_data['created_at'] = datetime.utcnow()
            result = scrapbooks_collection.insert_one(scrapbook_data)
            return jsonify({'success': True, 'id': str(result.inserted_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/scrapbook/<scrapbook_id>/delete', methods=['DELETE'])
def delete_scrapbook(scrapbook_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
    try:
        scrapbook = scrapbooks_collection.find_one({'_id': ObjectId(scrapbook_id)})
        if not scrapbook:
            return jsonify({'success': False, 'error': 'Scrapbook not found'}), 404
            
        # Check ownership
        if str(scrapbook['user_id']) != session['user_id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
            
        # Delete the scrapbook
        scrapbooks_collection.delete_one({'_id': ObjectId(scrapbook_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
# Add these collections at the top with your other collections
products_collection = db["products"]

@app.route('/sell_stuff')
def sell_stuff():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    
    if not user or user.get('profile_type') != 'seller':
        session.clear()
        return redirect(url_for('index'))
    
    # Get products for this seller
    products = list(products_collection.find({'seller_id': str(user['_id'])}))
    
    return render_template('sell_stuff.html',
                         user=user,
                         products=products)
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user or user.get('profile_type') != 'seller':
        return redirect(url_for('index'))
    
    # Handle file upload
    image_file = request.files.get('image')
    if not image_file or image_file.filename == '':
        flash('Product image is required', 'error')
        return redirect(url_for('sell_stuff'))
    
    image_filename = save_file(image_file)
    if not image_filename:
        flash('Invalid image file', 'error')
        return redirect(url_for('sell_stuff'))
    
    # Create new product
    product = {
        'name': request.form['name'],
        'description': request.form['description'],
        'price': float(request.form['price']),
        'image': image_filename,
        'seller_id': str(user['_id']),  # Reference to seller/user
        'created_at': datetime.utcnow()
    }
    
    products_collection.insert_one(product)
    flash('Product added successfully!', 'success')
    return redirect(url_for('sell_stuff'))


@app.route('/update_product', methods=['POST'])
def update_product():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user or user.get('profile_type') != 'seller':
        return redirect(url_for('index'))
    
    product_id = request.form['product_id']
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    
    if not product or product['seller_id'] != str(user['_id']):
        abort(403)
    
    updates = {
        'name': request.form['name'],
        'description': request.form['description'],
        'price': float(request.form['price']),
        'updated_at': datetime.utcnow()
    }
    
    # Handle image update if provided
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file.filename != '':
            filename = save_file(image_file)
            if filename:
                updates['image'] = filename
    
    products_collection.update_one(
        {'_id': ObjectId(product_id)},
        {'$set': updates}
    )
    
    flash('Product updated successfully!', 'success')
    return redirect(url_for('sell_stuff'))

@app.route('/delete_product', methods=['POST'])
def delete_product():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    product_id = request.form['product_id']
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    
    if not product or not user or product['seller_id'] != str(user['_id']):
        abort(403)
    
    products_collection.delete_one({'_id': ObjectId(product_id)})
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('sell_stuff'))

@app.route('/update_seller_profile', methods=['POST'])
def update_seller_profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user or user.get('profile_type') != 'seller':
        return redirect(url_for('index'))
    
    updates = {
        'shop_name': request.form['shop_name'],
        'description': request.form.get('description', '')
    }
    
    # Handle image update if provided
    if 'profile_image' in request.files:
        image_file = request.files['profile_image']
        if image_file.filename != '':
            filename = save_file(image_file)
            if filename:
                updates['profile_image'] = filename
    
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': updates}
    )
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('sell_stuff'))
@app.route('/marketplace')
def marketplace():
    try:
        # Get all sellers who have shops
        sellers_with_shops = users_collection.find({
            'profile_type': 'seller',
            'shop_name': {'$exists': True}
        })
        
        # Prepare shops data from users collection
        shops = []
        for seller in sellers_with_shops:
            shop = {
                '_id': str(seller['_id']),
                'name': seller.get('shop_name', 'Unnamed Shop'),
                'description': seller.get('description', ''),
                'owner_id': str(seller['_id']),
                'owner_name': seller['username'],
                'image': seller.get('profile_image', '')
            }
            # Count products for this seller/shop
            shop['product_count'] = products_collection.count_documents({
                'seller_id': str(seller['_id'])
            })
            shops.append(shop)
        
        # Get featured products
        featured_products = []
        products = list(products_collection.find().limit(8))
        
        for product in products:
            product['_id'] = str(product['_id'])
            # Get seller/shop info
            seller = users_collection.find_one({'_id': ObjectId(product['seller_id'])})
            if seller:
                product['shop_name'] = seller.get('shop_name', 'Unnamed Shop')
                product['seller_name'] = seller['username']
            else:
                product['shop_name'] = 'Unknown Shop'
                product['seller_name'] = 'Unknown'
            featured_products.append(product)
        
        return render_template('marketplace.html', 
                            shops=shops,
                            featured_products=featured_products)
    
    except Exception as e:
        print(f"Error in marketplace route: {str(e)}")
        flash("An error occurred while loading the marketplace", "error")
        return redirect(url_for('home'))
# Add these new routes to your existing app.py
@app.route('/api/sellers/<seller_id>/products')
def get_seller_products(seller_id):
    try:
        products = list(products_collection.find({'seller_id': seller_id}))
        for product in products:
            product['_id'] = str(product['_id'])
            # Get seller/shop info
            seller = users_collection.find_one({'_id': ObjectId(seller_id)})
            if seller:
                product['shop_name'] = seller.get('shop_name', 'Unnamed Shop')
            else:
                product['shop_name'] = 'Unknown Shop'
        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
# API Routes for Marketplace
@app.route('/api/shops')
def get_shops():
    try:
        shops = list(db.shops.find())
        for shop in shops:
            shop['_id'] = str(shop['_id'])
            owner = users_collection.find_one({'_id': ObjectId(shop['owner_id'])})
            shop['owner_name'] = owner['username'] if owner else "Unknown"
        return jsonify({'success': True, 'shops': shops})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/shops/<shop_id>/products')
def get_shop_products(shop_id):
    try:
        products = list(products_collection.find({'shop_id': ObjectId(shop_id)}))
        for product in products:
            product['_id'] = str(product['_id'])
            # Get shop name
            shop = db.shops.find_one({'_id': ObjectId(shop_id)})
            product['shop_name'] = shop['name'] if shop else "Unknown Shop"
        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/orders/create', methods=['POST'])
def create_order():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if not user.get('cart') or len(user['cart']) == 0:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400
        
        # Calculate total
        subtotal = 0
        for item in user['cart']:
            product = products_collection.find_one({'_id': ObjectId(item['product_id'])})
            if product:
                subtotal += product['price'] * item['quantity']
        
        shipping = 100 if subtotal > 0 else 0
        total = subtotal + shipping
        
        # Create order
        order = {
            'user_id': str(user['_id']),
            'items': user['cart'],
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Insert order into database (you'll need to create an orders_collection)
        orders_collection = db["orders"]
        result = orders_collection.insert_one(order)
        
        # Clear user's cart
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'cart': []}}
        )
        
        return jsonify({
            'success': True,
            'order_id': str(result.inserted_id),
            'message': 'Order created successfully!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Cart API Routes
@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user:
        session.clear()
        return redirect(url_for('index'))
    
    return render_template('cart.html', user=user)
@app.route('/api/cart')
def get_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        cart_items = []
        subtotal = 0
        
        # Get cart items with product details
        if 'cart' in user:
            for item in user['cart']:
                product = products_collection.find_one({'_id': ObjectId(item['product_id'])})
                if product:
                    product['_id'] = str(product['_id'])
                    cart_items.append({
                        'product': product,
                        'quantity': item['quantity']
                    })
                    subtotal += product['price'] * item['quantity']
        
        shipping = 100 if subtotal > 0 else 0
        total = subtotal + shipping
        
        return jsonify({
            'success': True,
            'cart_items': cart_items,
            'total': {
                'subtotal': subtotal,
                'shipping': shipping,
                'total': total
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
@app.route('/api/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    
    if not user or user.get('profile_type') != 'seller':
        session.clear()
        return redirect(url_for('index'))
    
    # Get products for this seller
    products = list(products_collection.find({'seller_id': str(user['_id'])}))
    
    return render_template('orders.html',
                         user=user)

@app.route('/api/seller/orders')
def get_seller_orders():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user or user.get('profile_type') != 'seller':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Get all orders that contain products from this seller
        orders = list(orders_collection.find({
            'items': {
                '$elemMatch': {
                    'product.seller_id': str(user['_id'])
                }
            }
        }).sort('created_at', -1))
        
        # Convert ObjectId to string and add product details
        for order in orders:
            order['_id'] = str(order['_id'])
            for item in order['items']:
                if 'product_id' in item:
                    product = products_collection.find_one({'_id': ObjectId(item['product_id'])})
                    if product:
                        product['_id'] = str(product['_id'])
                        item['product'] = product
        
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/orders/update-status', methods=['POST'])
def update_order_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        status = data.get('status')
        
        if not order_id or not status:
            return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user or user.get('profile_type') != 'seller':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Verify the order contains products from this seller
        order = orders_collection.find_one({
            '_id': ObjectId(order_id),
            'items': {
                '$elemMatch': {
                    'product.seller_id': str(user['_id'])
                }
            }
        })
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found or unauthorized'}), 404
        
        # Update order status
        orders_collection.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {
                'status': status,
                'updated_at': datetime.utcnow()
            }}
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        product_id = data.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'}), 400
        
        # Verify product exists
        product = products_collection.find_one({'_id': ObjectId(product_id)})
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Fetch user and their cart
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        cart = user.get('cart', [])
        
        # Check if product is already in cart
        for item in cart:
            if item['product_id'] == product_id:
                item['quantity'] += 1
                break
        else:
            cart.append({
                'product_id': product_id,
                'quantity': 1,
                'added_at': datetime.utcnow()
            })
        
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'cart': cart}}
        )
        
        return jsonify({
            'success': True,
            'message': 'Product added to cart',
            'cart_count': sum(item['quantity'] for item in cart)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/cart/update', methods=['POST'])
def update_cart_item():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        change = data.get('change', 0)
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'})
        
        # Update user's cart
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        cart = user.get('cart', [])
        updated_cart = []
        item_removed = False
        
        for item in cart:
            if item['product_id'] == product_id:
                new_quantity = item['quantity'] + change
                if new_quantity > 0:
                    item['quantity'] = new_quantity
                    updated_cart.append(item)
                else:
                    item_removed = True
            else:
                updated_cart.append(item)
        
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'cart': updated_cart}}
        )
        
        return jsonify({
            'success': True,
            'item_removed': item_removed
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'})
        
        # Update user's cart
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        cart = user.get('cart', [])
        updated_cart = [item for item in cart if item['product_id'] != product_id]
        
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'cart': updated_cart}}
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
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
