# 🐾 PAWS – Comic Scrapbook & Marketplace

**PAWS** is a comic-themed interactive scrapbook and e-commerce platform that lets users create and personalize comic scrapbooks, manage a storefront, and shop from others. It delivers a vibrant visual experience with a blend of creativity, storytelling, and online commerce.

---

## 📌 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Setup Instructions](#-setup-instructions)
- [Routes Overview](#-routes-overview)
- [Credits](#-credits)

---

## 💡 Features

### 👥 User Management
- Comic-style signup and login with role selection (buyer/seller)
- Session-based login with user dashboard and profile image uploads

### 🎨 Comic Scrapbook Studio
- Drag-and-drop scrapbook editor (`scrapbook_editor.html`)
- Add text, images, stickers, and speech bubbles
- Save, edit, and share scrapbooks (with privacy controls)
- Flipbook-style viewer (`scrapbook_view.html`)

### 🛍️ Marketplace
- Seller storefronts with profile and product showcase (`marketplace.html`)
- Product management: add, update, delete (`sell_stuff.html`)
- Shopping cart and checkout (`cart.html`)
- Order processing system for sellers (`orders.html`)

### 💥 Visual Aesthetic
- Animated homepage (`home.html`, `home_seller.html`) with exploding comic letters
- Comic-themed fonts: Bangers, Comic Neue, Bubblegum Sans
- Bold borders, radial background patterns, and shadows
- Comic-style loading screen (`index.html` with `index.css` animation)

---


## ⚙️ Tech Stack

**Frontend**:  
- HTML5, CSS3, JavaScript  
- Google Fonts + Comic Styling  
- Comic-based design system

**Backend**:  
- Python Flask  
- MongoDB (via PyMongo)  

**Libraries**:  
- OpenCV (for cartoon filters)  
- PIL, NumPy, Werkzeug

---

## 🗂 Project Structure

```
📦 paws/
├── app.py                # Flask application backend
├── static/
│   ├── css/
│   │   ├── style.css
│   │   └── index.css
│   ├── js/
│   │   └── script.js
│   ├── uploads/
│   ├── images/
│   ├── backgrounds/
│   └── stickers/
├── templates/
│   ├── index.html
│   ├── create.html
│   ├── home.html
│   ├── home_seller.html
│   ├── profile.html
│   ├── scrapbook_editor.html
│   ├── scrapbook_view.html
│   ├── sell_stuff.html
│   ├── marketplace.html
│   ├── cart.html
│   └── orders.html
```

---

## 🚀 Setup Instructions

```bash
# Clone the project
git clone https://github.com/yourusername/paws.git
cd paws

# Set up Python environment
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate

# Install dependencies
pip install flask pymongo pillow opencv-python numpy

# Run the Flask app
python app.py
```

---

## 🔗 Routes Overview

### 🔐 Auth & Profiles
- `/create` – Sign Up / Login page  
- `/login` – POST for login  
- `/logout` – Logout  
- `/create_profile/<profile_type>` – Create seller/personal profile  

### 🏠 Home
- `/home` – Personal home view  
- `/home_seller` – Seller dashboard  

### 📓 Scrapbook
- `/scrapbook/new` – Create new scrapbook  
- `/scrapbook/<id>` – View scrapbook  
- `/scrapbook/<id>/edit` – Edit scrapbook  
- `/api/scrapbook/save` – Save scrapbook  
- `/api/scrapbook/<id>/delete` – Delete scrapbook  

### 🛒 E-Commerce
- `/sell_stuff` – Seller product dashboard  
- `/add_product`, `/update_product`, `/delete_product` – Product management  
- `/marketplace` – Browse shops/products  
- `/cart` – View cart  
- `/api/cart` – Get cart items  
- `/api/cart/add`, `/api/cart/update`, `/api/cart/remove` – Modify cart  
- `/api/orders/create` – Checkout  
- `/api/seller/orders` – Get seller orders  
- `/api/orders/update-status` – Update order state  

### 🖼 Assets
- `/api/upload-image` – Upload files  
- `/api/stickers` – Get stickers  
- `/api/backgrounds` – Get backgrounds  
- `/convert-comic` – Cartoonify an image

---

## ✨ Credits

Built by Arisha & Atharva  