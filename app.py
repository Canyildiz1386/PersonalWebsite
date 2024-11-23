from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import os
import pandas as pd
import json
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/perfume_db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx'}
app.config['CHATGPT_API_KEY'] = os.getenv('CHATGPT_API_KEY', 'your_chatgpt_api_key')

mongo = PyMongo(app)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('لطفاً ابتدا وارد حساب کاربری خود شوید.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def initialize_questions():
    base_questions = [
        {
            'id': 'q1',
            'text': 'عطر دلخواه تو چه حسی رو باید منتقل کنه؟',
            'type': 'single',
            'options': ["شاد و پرانرژی", "آرامش‌بخش", "رازآلود و اغواگر", "کلاسیک و شیک"]
        },
        {
            'id': 'q2',
            'text': 'این عطر برای کدوم فصل طراحی بشه؟',
            'type': 'single',
            'options': ["بهار", "تابستان", "پاییز", "زمستان"]
        },
        {
            'id': 'q3',
            'text': 'کدوم دسته از بوها برات جذاب‌تره؟',
            'type': 'multiple',
            'options': ["میوه‌ای", "گلی", "چوبی", "ادویه‌ای"]
        },
        {
            'id': 'q4',
            'text': 'عطری می‌خوای که تو رو به یاد کجا بندازه؟',
            'type': 'single',
            'options': ["طبیعت", "ساحل", "شهر", "کوهستان"]
        },
        {
            'id': 'q5',
            'text': 'این عطر رو بیشتر برای چه موقعیتی می‌خوای؟',
            'type': 'single',
            'options': ["استفاده روزمره", "مجالس رسمی", "قرار ملاقات", "لحظات خاص"]
        },
        {
            'id': 'q6',
            'text': 'دوست داری عطرت چقدر قوی باشه؟',
            'type': 'single',
            'options': ["سبک و ملایم", "متوسط", "قوی و برجسته"]
        },
        {
            'id': 'q7',
            'text': 'ماندگاری عطر برات چقدر مهمه؟',
            'type': 'single',
            'options': ["کم (1-3 ساعت)", "متوسط (3-6 ساعت)", "زیاد (بیش از 6 ساعت)"]
        },
        {
            'id': 'q8',
            'text': 'آیا بوی خاصی هست که تو رو یاد خاطره یا لحظه‌ای بیندازه؟',
            'type': 'text',
            'options': []
        },
        {
            'id': 'q9',
            'text': 'دوست داری عطر تو چه چیزی درباره شخصیتت بگه؟',
            'type': 'single',
            'options': ["جسور", "خلاق", "آرام", "اجتماعی"]
        },
        {
            'id': 'q10',
            'text': 'چه رنگی بیشتر با حس عطر دلخواهت هم‌خوانی داره؟',
            'type': 'single',
            'options': ["قرمز", "آبی", "سبز", "زرد"]
        },
        {
            'id': 'q11',
            'text': 'کدام عطرهایی که قبلاً استفاده کردی یا دوست داشتی؟',
            'type': 'text',
            'options': []
        }
    ]
    for question in base_questions:
        existing = mongo.db.questions.find_one({'id': question['id']})
        if not existing:
            mongo.db.questions.insert_one(question)

@app.before_request
def setup():
    initialize_questions()

@app.route('/')
def home():
    return render_template('index.html', page='home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('با موفقیت وارد شدید.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('نام کاربری یا رمز عبور نادرست است.', 'error')
            return redirect(url_for('login'))
    return render_template('index.html', page='login')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('با موفقیت خارج شدید.', 'success')
    return redirect(url_for('home'))

@app.route('/design', methods=['GET', 'POST'])
def design():
    if request.method == 'POST':
        responses = {}
        questions = list(mongo.db.questions.find())
        for q in questions:
            q_id = q['id']
            q_type = q['type']
            if q_type == 'multiple':
                responses[q_id] = request.form.getlist(q_id)
            else:
                responses[q_id] = request.form.get(q_id)
        size = request.form.get('bottle_size')
        gift = 'yes' if request.form.get('gift') == 'on' else 'no'
        note = request.form.get('note')
        preferred_scents = responses.get('q3', [])
        prompt = f"""
Based on the following user preferences, create a personalized perfume design. First, provide a user-friendly description of the perfume's composition for display to the user. Then, provide a detailed manufacturing formula for the admin panel.

User preferences:
1. Mood: {responses.get('q1', '')}
2. Season: {responses.get('q2', '')}
3. Preferred scents: {', '.join(preferred_scents)}
4. Location inspiration: {responses.get('q4', '')}
5. Usage: {responses.get('q5', '')}
6. Strength: {responses.get('q6', '')}
7. Longevity: {responses.get('q7', '')}
8. Nostalgic scent: {responses.get('q8', '')}
9. Personality trait: {responses.get('q9', '')}
10. Color: {responses.get('q10', '')}
11. Previous perfumes used or liked: {responses.get('q11', '')}
Bottle size: {size}ml
Gift: {gift}
Note: {note}
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {app.config["CHATGPT_API_KEY"]}'
        }
        data_payload = {
            "prompt": prompt,
            "temperature": 0.7,
            "max_tokens": 300
        }
        response = requests.post('https://api.openai.com/v1/engines/davinci/completions', headers=headers, json=data_payload)
        if response.status_code == 200:
            result = response.json()
            text = result.get('choices', [{}])[0].get('text', '')
            parts = text.strip().split('\n\n')
            user_description = parts[0].strip() if len(parts) > 0 else "Unable to generate description at the moment."
            admin_formula = parts[1].strip() if len(parts) > 1 else "N/A"
        else:
            user_description = "Unable to generate description at the moment."
            admin_formula = "N/A"
        
        # Retrieve base price from db
        pricing = mongo.db.pricing.find_one({'size': size})
        base_price = pricing['price'] if pricing else 0

        order = {
            'responses': responses,
            'size': size,
            'gift': gift,
            'note': note,
            'user_description': user_description,
            'admin_formula': admin_formula,
            'paid': False,
            'price': base_price
        }
        order_id = mongo.db.orders.insert_one(order).inserted_id
        return redirect(url_for('result', order_id=str(order_id)))
    else:
        questions = list(mongo.db.questions.find())
        return render_template('index.html', page='design', questions=questions)

@app.route('/result/<order_id>')
def result(order_id):
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        flash('سفارش یافت نشد.', 'error')
        return redirect(url_for('home'))
    # Retrieve base price
    size = order.get('size')
    pricing = mongo.db.pricing.find_one({'size': size})
    base_price = pricing['price'] if pricing else 0
    return render_template('index.html', page='result', order=order, price=base_price)

@app.route('/payment/<order_id>', methods=['POST'])
def payment(order_id):
    # Here you would integrate with a payment gateway
    # For demonstration, we'll just mark as paid
    mongo.db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'paid': True}})
    return redirect(url_for('confirmation', order_id=order_id))

@app.route('/confirmation/<order_id>')
def confirmation(order_id):
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        flash('سفارش یافت نشد.', 'error')
        return redirect(url_for('home'))
    return render_template('index.html', page='confirmation', order=order)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    pricing = list(mongo.db.pricing.find())
    questions = list(mongo.db.questions.find())
    orders = list(mongo.db.orders.find())
    return render_template('index.html', page='admin_dashboard', pricing=pricing, questions=questions, orders=orders)

@app.route('/admin/upload_questions', methods=['POST'])
@login_required
def upload_questions():
    if 'file' not in request.files:
        flash('فایلی انتخاب نشده است.', 'error')
        return redirect(url_for('admin_dashboard'))
    file = request.files['file']
    if file.filename == '':
        flash('فایلی انتخاب نشده است.', 'error')
        return redirect(url_for('admin_dashboard'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        try:
            df = pd.read_excel(filepath)
            for _, row in df.iterrows():
                q_id = row['id']
                question = {
                    'id': q_id,
                    'text': row['text'],
                    'type': row['type'],
                    'options': json.loads(row['options']) if pd.notna(row['options']) else []
                }
                mongo.db.questions.update_one({'id': q_id}, {'$set': question}, upsert=True)
            flash('سوالات با موفقیت آپلود و بروزرسانی شدند.', 'success')
        except Exception as e:
            flash('خطا در پردازش فایل: ' + str(e), 'error')
        finally:
            os.remove(filepath)
        return redirect(url_for('admin_dashboard'))
    else:
        flash('فرمت فایل نامعتبر است. لطفاً یک فایل اکسل (.xlsx) آپلود کنید.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/manage_pricing', methods=['POST'])
@login_required
def manage_pricing():
    size = request.form.get('size')
    price = request.form.get('price')
    if size not in ['35', '50']:
        flash('حجم عطر نامعتبر است.', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        price = float(price)
        mongo.db.pricing.update_one({'size': size}, {'$set': {'price': price}}, upsert=True)
        flash('قیمت با موفقیت بروزرسانی شد.', 'success')
    except ValueError:
        flash('قیمت نامعتبر است.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_question', methods=['POST'])
@login_required
def add_question():
    q_id = request.form.get('id')
    text = request.form.get('text')
    q_type = request.form.get('type')
    options = request.form.get('options')
    if q_type in ['single', 'multiple']:
        options = [opt.strip() for opt in options.split(',')]
    else:
        options = []
    question = {
        'id': q_id,
        'text': text,
        'type': q_type,
        'options': options
    }
    existing = mongo.db.questions.find_one({'id': q_id})
    if existing:
        mongo.db.questions.update_one({'id': q_id}, {'$set': question})
        flash('سوال بروزرسانی شد.', 'success')
    else:
        mongo.db.questions.insert_one(question)
        flash('سوال اضافه شد.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_question/<question_id>', methods=['POST'])
@login_required
def edit_question(question_id):
    text = request.form.get('text')
    q_type = request.form.get('type')
    options = request.form.get('options')
    if q_type in ['single', 'multiple']:
        options = [opt.strip() for opt in options.split(',')]
    else:
        options = []
    question = {
        'text': text,
        'type': q_type,
        'options': options
    }
    mongo.db.questions.update_one({'id': question_id}, {'$set': question})
    flash('سوال بروزرسانی شد.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_question/<question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    mongo.db.questions.delete_one({'id': question_id})
    flash('سوال حذف شد.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
