from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
from bson.objectid import ObjectId  # Added to handle MongoDB ObjectId
from flask import abort


app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SESSION_TYPE'] = 'filesystem'

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["paws_database"]
users_collection = db["users"]

# Ensure uploads folder exists
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create')
def create():
    return render_template('create.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users_collection.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            # Store user in session
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['profile_type'] = user.get('profile_type', 'personal')
            
            return jsonify({
                'success': True,
                'message': f"Welcome back, {user['username']}!",
                'redirect': url_for('home')
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid username or password. Please try again.'
            })

def save_profile_image(file):
    if file and allowed_file(file.filename):
        # Generate unique filename to prevent overwriting
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        return filename
    return None

@app.route('/create_profile/<profile_type>', methods=['GET', 'POST'])
def create_profile(profile_type):
    if request.method == 'GET':
        return redirect(url_for('create'))
        
    if profile_type not in ['personal', 'seller']:
        return jsonify({
            'success': False,
            'message': 'Invalid profile type.'
        })
    
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    
    # Check if username already exists
    existing_user = users_collection.find_one({'username': username})
    if existing_user:
        return jsonify({
            'success': False,
            'message': 'Username already taken! Please choose another one.'
        })
    
    # Check if email already exists
    existing_email = users_collection.find_one({'email': email})
    if existing_email:
        return jsonify({
            'success': False,
            'message': 'Email already registered! Please use another email or login.'
        })
    
    # Handle profile image
    profile_image = request.files.get('profile_image')
    image_filename = save_profile_image(profile_image) if profile_image else None
    
    # Create user document
    user_data = {
        'username': username,
        'email': email,
        'password': generate_password_hash(password),
        'profile_type': profile_type,
        'created_at': datetime.utcnow(),
    }
    
    if image_filename:
        user_data['profile_image'] = image_filename
    
    # Add shop name for seller profiles
    if profile_type == 'seller' and 'shop_name' in request.form:
        user_data['shop_name'] = request.form['shop_name']
    
    # Insert into database
    result = users_collection.insert_one(user_data)
    
    # Log the user in
    user_id = str(result.inserted_id)
    session['user_id'] = user_id
    session['username'] = username
    session['profile_type'] = profile_type
    
    return jsonify({
        'success': True,
        'message': 'Account created successfully!',
        'redirect': url_for('home')
    })

@app.route('/home')
def home():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Get user data - convert string ID back to ObjectId
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    if not user:
        # Session exists but user doesn't - clear session and redirect
        session.clear()
        return redirect(url_for('index'))
    
    return render_template('home.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.template_filter('image_url')
def image_url(image_filename):
    if image_filename:
        return url_for('static', filename=f'uploads/{image_filename}')
    return url_for('static', filename='images/default-profile.jpg')

@app.route('/profile/<username>')
def profile(username):
    user = users_collection.find_one({'username': username})
    if not user:
        abort(404)
    return render_template('profile.html', user=user)


if __name__ == '__main__':
    app.run(debug=True)