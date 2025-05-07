from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
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
        return jsonify({'success': True, 'redirect': url_for('home')})
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

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))

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
    
@app.route('/marketplace')
def marketplace():
    return render_template('marketplace.html')

@app.route('/sell_stuff')
def sell_stuff():
    return render_template('sell_stuff.html')

@app.route('/sell')
def sell():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        return redirect(url_for('login'))

    account_type = user.get('profile_type')
    if not account_type:
        flash("Account type not defined. Please update your profile.", "error")
        return redirect(url_for('profile', username=user['username']))

    shop = None
    products = []

    if account_type == 'personal':
        shop_id = user.get('shop_id')
        if shop_id:
            shop = db.shops.find_one({'_id': ObjectId(shop_id)})
    elif account_type == 'seller':
        shop = db.shops.find_one({'owner_id': ObjectId(user_id)})

    if shop:
        products = list(db.products.find({'shop_id': shop['_id']}))

    return render_template('sell_stuff.html', user=user, shop=shop, products=products)


@app.route('/create_shop', methods=['POST'])
def create_shop():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    name = request.form['name']
    description = request.form.get('description', '')
    image_url = request.form.get('image_url', '')

    shop = {
        'name': name,
        'description': description,
        'image': image_url,
        'owner_id': ObjectId(user_id)
    }

    shop_id = db.shops.insert_one(shop).inserted_id
    users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'shop_id': shop_id}})
    return redirect(url_for('sell'))

@app.route('/add_product', methods=['POST'])
def add_product():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        return redirect(url_for('login'))

    shop_id = user.get('shop_id') or db.shops.find_one({'owner_id': ObjectId(user_id)})['_id']
    
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    image_url = request.form['image_url']

    if not image_url:
        flash("Product image is required.", "error")
        return redirect(url_for('sell'))

    product = {
        'shop_id': shop_id,
        'name': name,
        'description': description,
        'price': price,
        'image': image_url
    }

    db.products.insert_one(product)
    return redirect(url_for('sell'))

@app.route('/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    db.products.delete_one({'_id': ObjectId(product_id)})
    return redirect(url_for('sell'))

@app.route('/edit_product/<product_id>', methods=['POST'])
def edit_product(product_id):
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])

    update_data = {
        'name': name,
        'description': description,
        'price': price
    }

    if 'image' in request.files:
        image_file = request.files['image']
        if image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            update_data['image'] = image_path

    db.products.update_one({'_id': ObjectId(product_id)}, {'$set': update_data})
    return redirect(url_for('sell'))


if __name__ == '__main__':
    app.run(debug=True)
