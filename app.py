# -*- coding: utf-8 -*-
import re
from flask import Flask, render_template, request, redirect, url_for, abort, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
import base64

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30) # იუზერი სისტემაში დარჩება 30 დღე
)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300 
app.config['SECRET_KEY'] = 'noventra_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_o6plSifKNIc9@ep-damp-thunder-asbmmuxu.c-4.eu-central-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # საიტზე გამოსაჩენი ნიკნეიმი
    full_name = db.Column(db.String(100), default="") # სრული სახელი და გვარი (მხოლოდ ადმინისთვის/ვერიფიკაციისთვის)
    email = db.Column(db.String(100), default="")     # მეილის ველი
    phone = db.Column(db.String(20), unique=True, nullable=False) # ტელეფონი
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    reputation = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    bank_account = db.Column(db.String(50), default="")
    holder_name = db.Column(db.String(100), default="") # 🛠️ მიმღების სახელი და გვარი საბანკო გადარიცხვისთვის
    clicks_left = db.Column(db.Integer, default=250)
    total_clicks = db.Column(db.Integer, default=0)
    region = db.Column(db.String(50), default="tbilisi")
    is_banned = db.Column(db.Boolean, default=False)
    
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    withdrawals = db.relationship('WithdrawalRequest', backref='user', lazy=True)
    last_seen_board = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 🪪 KYC ვერიფიკაციის ველები (შეცვლილია TEXT-ად ბაზის ლიმიტის ასაცილებლად)
    verification_status = db.Column(db.String(20), default='none') # none, pending, approved
    personal_number = db.Column(db.String(11), nullable=True)
    verification_photo = db.Column(db.Text, nullable=True)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reward = db.Column(db.Float, default=5.0)
    is_completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

class WithdrawalRequest(db.Model):
    __tablename__ = 'withdrawal_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(20), default="")
    bank_account = db.Column(db.String(50), default="")
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(50))
    user_phone = db.Column(db.String(20))
    region_id = db.Column(db.String(50), default="tbilisi")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Advertisement(db.Model):
    __tablename__ = 'advertisements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class UserAdView(db.Model):
    __tablename__ = 'user_ad_views'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ad_id = db.Column(db.Integer, db.ForeignKey('advertisements.id'), nullable=False)

class RegionScore(db.Model):
    __tablename__ = 'region_scores'
    id = db.Column(db.Integer, primary_key=True)
    region_id = db.Column(db.String(50), unique=True, nullable=False)
    region_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, default=0)
    
class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

# ----------------- ვიქტორინის მოდელები -----------------

class UserQuizAnswer(db.Model):
    __tablename__ = 'user_quiz_answers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), nullable=False)

# 🏢 საჯარო პარტნიორების / სპონსორების ცხრილი
class PartnerSponsor(db.Model):
    __tablename__ = 'partner_sponsors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    website_url = db.Column(db.String(255), nullable=False)
    logo = db.Column(db.Text, nullable=False) # <-- შეცვლილია TEXT-ად

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    sponsor_name = db.Column(db.String(100), nullable=False)
    sponsor_image = db.Column(db.Text, default="") # <-- შეცვლილია TEXT-ად
    package_type = db.Column(db.String(20), default="Bronze")
    question_text = db.Column(db.Text, nullable=False)
    option_1 = db.Column(db.String(150), nullable=False)
    option_2 = db.Column(db.String(150), nullable=False)
    option_3 = db.Column(db.String(150), nullable=False)
    option_4 = db.Column(db.String(150), nullable=False)
    correct_option = db.Column(db.Integer, nullable=False)

# ----------------- ვიქტორინის API-ები -----------------

@app.route('/api/get_random_quiz')
@login_required
def get_random_quiz():
    import random
    
    answered_ids = db.session.query(UserQuizAnswer.quiz_id).filter_by(user_id=current_user.id).all()
    answered_ids = [ans[0] for ans in answered_ids]
    
    questions = QuizQuestion.query.filter(~QuizQuestion.id.in_(answered_ids)).all() if answered_ids else QuizQuestion.query.all()
    
    if not questions:
        UserQuizAnswer.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        questions = QuizQuestion.query.all()
        
    if not questions:
        return jsonify({"success": False, "message": "კითხვები არ არის ბაზაში"})
    
    weighted_pool = []
    for q in questions:
        weight = 3 if q.package_type == 'Gold' else (2 if q.package_type == 'Silver' else 1)
        for _ in range(weight):
            weighted_pool.append(q)
            
    selected_q = random.choice(weighted_pool)
    
    return jsonify({
        "success": True,
        "id": selected_q.id,
        "sponsor_name": selected_q.sponsor_name,
        "sponsor_image": selected_q.sponsor_image,
        "package_type": selected_q.package_type,
        "question_text": selected_q.question_text,
        "options": [selected_q.option_1, selected_q.option_2, selected_q.option_3, selected_q.option_4],
        "correct_option": selected_q.correct_option
    })

@app.route('/api/check_quiz', methods=['POST'])
@login_required
def check_quiz():
    data = request.get_json() or {}
    q_id = data.get('question_id')
    chosen_opt = int(data.get('chosen_option', 0))
    
    q = QuizQuestion.query.get(q_id)
    if not q:
        return jsonify({"success": False, "message": "კითხვა ვერ მოიძებნა"})
         
    is_correct = (chosen_opt == q.correct_option)
    
    existing_answer = UserQuizAnswer.query.filter_by(user_id=current_user.id, quiz_id=q_id).first()
    if not existing_answer:
        new_ans = UserQuizAnswer(user_id=current_user.id, quiz_id=q_id)
        db.session.add(new_ans)
        db.session.commit()

    return jsonify({
        "success": True,
        "is_correct": is_correct,
        "correct_option": q.correct_option
    })

def init_regions():
    regions = [
        ("tbilisi", "თბილისი"),
        ("imereti", "იმერეთი"),
        ("adjara", "აჭარის ა.რ."),
        ("kakheti", "კახეთი"),
        ("samegrelo", "სამეგრელო-ზემო სვანეთი"),
        ("guria", "გურია"),
        ("racha_lechkhumi", "რაჭა-ლეჩხუმი"),
        ("samtskhe_javakheti", "სამცხე-ჯავახეთი"),
        ("shida_kartli", "შიდა ქართლი"),
        ("kvemo_kartli", "ქვემო ქართლი"),
        ("mtskheta_mtianeti", "მცხეთა-მთიანეთი"),
        ("abkhazia", "აფხაზეთის ა.რ.")
    ]
    for r_id, r_name in regions:
        exists = RegionScore.query.filter_by(region_id=r_id).first()
        if not exists:
            db.session.add(RegionScore(region_id=r_id, region_name=r_name, score=0))
    db.session.commit()

def is_safe(text):
    if re.search(r'(http|https|www|\.com|\.ge|\.org)', text, re.IGNORECASE):
        return False
    if re.search(r'\d{7,12}', text):
        return False
    return True

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/api/check_new_messages')
@login_required
def api_check_new_messages():
    # ვამოწმებთ არის თუ არა მესიჯები მომხმარებლის რეგიონში, რომლებიც მის ბოლო ნახვის დროზე გვიანია
    last_seen = current_user.last_seen_board or datetime.datetime.utcnow()
    new_msg_count = Question.query.filter(
        Question.region_id == current_user.region,
        Question.created_at > last_seen,
        Question.username != current_user.username # საკუთარ მესიჯებზე რომ არ აინთოს
    ).count()

    return jsonify({
        "success": True,
        "has_new": new_msg_count > 0,
        "count": new_msg_count
    })

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.phone = request.form.get('phone')
        current_user.bank_account = request.form.get('bank_account')
        current_user.holder_name = request.form.get('holder_name')  # 🛠️ აი ეს ველი დავამატეთ
        db.session.commit()
        flash("მონაცემები წარმატებით დამახსოვრებულია!", "success")
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/region_chat/<region_id>', methods=['GET', 'POST'])
@login_required
def region_chat(region_id):
    if current_user.region != region_id and not current_user.is_admin:
        flash("შენ არ გაქვს სხვა რეგიონის ჩატზე წვდომა!", "danger")
        return redirect(url_for('region_chat', region_id=current_user.region))
    
    if request.method == 'POST':
        text = request.form.get('message')
        if text and text.strip():
            if is_safe(text):
                new_q = Question(
                    text=text.strip(), 
                    username=current_user.username, 
                    user_phone=current_user.phone,
                    region_id=region_id
                )
                db.session.add(new_q)
                db.session.commit()
            else:
                flash("მესიჯი არღვევს წესებს!", "danger")
        return redirect(url_for('region_chat', region_id=region_id))
         
    # 🛠️ აქ ვანახლებთ ბოლო ნახვის დროს, რომ ახალი მესიჯების ინდიკატორი გაქრეს
    current_user.last_seen_board = datetime.datetime.utcnow()
    db.session.commit()
    
    messages = Question.query.filter_by(region_id=region_id).order_by(Question.id.asc()).all()
    return render_template('board.html', region_id=region_id, messages=messages)

@app.route('/board')
@login_required
def board():
    return redirect(url_for('region_chat', region_id=current_user.region))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        full_name = request.form.get('full_name').strip()  # 🛠️ სრული სახელი და გვარი (ვერიფიკაციისთვის)
        email = request.form.get('email').strip()         # 🛠️ მეილის ველი
        phone = request.form.get('phone').strip()
        password = request.form.get('password')
        region = request.form.get('region')
        
        # ⚖️ ასაკისა და წესების ვერიფიკაციის შემოწმება
        is_adult = request.form.get('is_adult')
        terms_agreed = request.form.get('terms_agreed')
        
        if not is_adult or not terms_agreed:
            flash("რეგისტრაციისთვის სავალდებულოა სრულწლოვანებისა და წესების მონიშვნა!", "danger")
            return redirect(url_for('register'))
        
        if not region or region == "":
            flash("გთხოვთ, აირჩიოთ რეგიონი!", "danger")
            return redirect(url_for('register'))
         
        if User.query.filter_by(username=username).first():
            flash("მომხმარებელი ამ სახელით უკვე არსებობს!", "danger")
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash("მომხმარებელი ამ მეილით უკვე რეგისტრირებულია!", "danger")
            return redirect(url_for('register'))
            
        if User.query.filter_by(phone=phone).first():
            flash("მომხმარებელი ამ მობილურის ნომრით უკვე არსებობს!", "danger")
            return redirect(url_for('register'))
             
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # 🛠️ ვუმატებთ full_name-სა და email-ს ბაზაში შესანახად
        new_user = User(
            username=username, 
            full_name=full_name, 
            email=email,
            phone=phone, 
            password=hashed_password, 
            region=region
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            import traceback
            return f"<pre>{traceback.format_exc()}</pre>", 500
            
    return render_template('signup_new.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            # 👑 თუ ეს შენი ადმინ ექაუნთია, ავტომატურად ვუწერთ True-ს
            if user.username == 'noventra_admin':
                user.is_admin = True
                db.session.commit()

            login_user(user, remember=True) # მუდმივი სესია
            return redirect(url_for('dashboard'))
        flash("მომხმარებლის სახელი ან პაროლი არასწორია!", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # შევამოწმოთ, სწორია თუ არა ძველი პაროლი
    if not check_password_hash(current_user.password, current_password):
        flash("მიმდინარე პაროლი არასწორია!", "danger")
        return redirect(url_for('dashboard')) # ან იმ გვერდის ლინკი სადაც პაროლის შეცვლაა
        
    if new_password != confirm_password:
        flash("ახალი პაროლები ერთმანეთს არ ემთხვევა!", "danger")
        return redirect(url_for('dashboard'))
        
    if len(new_password) < 6:
        flash("ახალი პაროლი უნდა შედგებოდეს მინიმუმ 6 სიმბოლოსგან!", "danger")
        return redirect(url_for('dashboard'))
        
    # ვანახლებთ პაროლს უსაფრთხო ჰეშით
    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()
    
    flash("პაროლი წარმატებით შეიცვალა!", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    all_tasks = Task.query.all()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(is_completed=True).count()
    
    completion_rate = 0
    if total_tasks > 0:
        completion_rate = int((completed_tasks / total_tasks) * 100)
    
    new_questions_count = Question.query.filter(Question.created_at > current_user.last_seen_board).count()
    regions = RegionScore.query.order_by(RegionScore.score.desc()).all()

    prize_setting = Settings.query.filter_by(key='prize_pool').first()
    current_week_prize_pool = prize_setting.value if prize_setting else "1200"

    winner_setting = Settings.query.filter_by(key='last_winner').first()
    last_winner_region = winner_setting.value if winner_setting else "იმერეთი"

    game_status_setting = Settings.query.filter_by(key='game_status').first()
    game_status = game_status_setting.value if game_status_setting else "active"

    return render_template('dashboard.html', 
                         tasks=all_tasks, 
                         new_questions_count=new_questions_count,
                         total_tasks=total_tasks,
                         completion_rate=completion_rate,
                         regions=regions,
                         current_week_prize_pool=current_week_prize_pool,
                         last_winner_region=last_winner_region,
                         game_status=game_status)

@app.route('/api/score', methods=['POST'])
@login_required
def add_score():
    data = request.get_json() or {}
    region_id = data.get('region_id')
    points = int(data.get('points', 1))
    
    region = RegionScore.query.filter_by(region_id=region_id).first()
    if region:
        region.score += points
        current_user.total_clicks += points 
        
        if current_user.clicks_left >= points:
            current_user.clicks_left -= points
        else:
            current_user.clicks_left = 0
            
        db.session.commit()
        return jsonify({"success": True, "new_score": region.score, "clicks_left": current_user.clicks_left})
    
    return jsonify({"success": False, "message": "Region not found"}), 400

@app.route('/api/get_next_ad')
@login_required
def get_next_ad():
    viewed_ads_subq = db.session.query(UserAdView.ad_id).filter_by(user_id=current_user.id)
    next_ad = Advertisement.query.filter(~Advertisement.id.in_(viewed_ads_subq)).first()
    
    if not next_ad:
        UserAdView.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        next_ad = Advertisement.query.first()

    if next_ad:
        new_view = UserAdView(user_id=current_user.id, ad_id=next_ad.id)
        db.session.add(new_view)
        db.session.commit()
        return jsonify({"success": True, "title": next_ad.title, "video_url": next_ad.video_url})
    
    return jsonify({"success": False, "message": "რეკლამები არ არის"})

@app.route('/complete_task/<int:task_id>')
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not task.is_completed:
        task.is_completed = True
        current_user.balance += task.reward
        new_trans = Transaction(user_id=current_user.id, task_title=task.title, amount=task.reward)
        db.session.add(new_trans)
        db.session.commit()
    return redirect(url_for('dashboard') + '#tasks-section')

@app.route('/leaderboard')
@login_required
def leaderboard():
    top_users = User.query.order_by(User.balance.desc()).limit(10).all()
    return render_template('leaderboard.html', users=top_users)

@app.route('/request_withdrawal', methods=['POST'])
@login_required
def request_withdrawal():
    amount = float(request.form.get('amount', 0))
    if amount > current_user.balance:
        flash("ბალანსი არასაკმარისია!", "danger")
    else:
        new_request = WithdrawalRequest(
            user_id=current_user.id, 
            amount=amount, 
            phone=current_user.phone, 
            bank_account=current_user.bank_account
        )
        db.session.add(new_request)
        db.session.commit()
        flash("მოთხოვნა გაგზავნილია ადმინისტრატორთან!", "success")
    return redirect(url_for('dashboard'))

@app.route('/task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        if task.is_completed:
            flash("ეს დავალება უკვე შესრულებულია!", "warning")
            return redirect(url_for('dashboard') + '#tasks-section')
         
        user_answer = request.form.get('user_answer')
        if not user_answer:
            flash("გთხოვთ, შეიყვანოთ პასუხი!", "danger")
            return redirect(url_for('task_detail', task_id=task.id))

        task.is_completed = True
        task.user_id = current_user.id
        current_user.balance += task.reward
         
        new_trans = Transaction(user_id=current_user.id, task_title=task.title, amount=task.reward)
        db.session.add(new_trans)
        db.session.commit()
         
        flash(f"დავალება წარმატებით შესრულდა! დაირიცხა {task.reward} ₾", "success")
        return redirect(url_for('dashboard') + '#tasks-section')

    return render_template('task_detail.html', task=task)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        reward = float(request.form.get('reward', 5.0))
        if title and description:
            new_task = Task(title=title, description=description, reward=reward, is_completed=False)
            db.session.add(new_task)
            db.session.commit()
            flash("ახალი დავალება წარმატებით დაემატა!", "success")
            return redirect(url_for('admin_dashboard'))
    return render_template('add_task.html')

# 🛠️ დაამატე ეს მარშრუტი ვერიფიკაციის მართვისთვის
@app.route('/admin/verify-user/<int:user_id>/<action>', methods=['POST'])
@login_required
def admin_verify_user(user_id, action):
    if not current_user.is_admin:
        abort(403)
    
    user = User.query.get_or_404(user_id)
    if action == 'approve':
        user.verification_status = 'approved'
        flash(f'მომხმარებელი {user.username} წარმატებით დავერიფიცირდა!', 'success')
    elif action == 'reject':
        user.verification_status = 'rejected'
        # ფოტოს ვშლით უარის შემთხვევაში, რომ ადგილი არ დაიკავოს
        user.verification_photo = None
        user.personal_number = None
        flash(f'მომხმარებელი {user.username} ვერიფიკაცია უარყოფილია.', 'error')
        
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>/verification_image')
@login_required
def get_verification_image(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if not user.verification_photo:
        return "ფოტო არ მოიძებნა", 404
    
    try:
        # ბაზიდან წამოღებული Base64-ის დამუშავება
        if "," in user.verification_photo:
            header, encoded = user.verification_photo.split(",", 1)
        else:
            encoded = user.verification_photo
            
        data = base64.b64decode(encoded)
        from flask import Response
        return Response(data, mimetype='image/jpeg')
    except Exception as e:
        return "ფოტოს დამუშავების შეცდომა", 500

# 🛠️ შესწორებული ადმინ-დაშბორდის მარშრუტი (დაამატე partners)
@app.route('/admin')
@login_required
def admin_dashboard():
    # 👑 ავტორიზაცია
    admin_user = User.query.filter_by(username='noventra_admin').first()
    if admin_user:
        admin_user.is_admin = True
        db.session.commit()
        if not current_user.is_admin:
            login_user(admin_user)
    
    users = User.query.all()
    regions = RegionScore.query.order_by(RegionScore.score.desc()).all()
    partners = PartnerSponsor.query.all() # 🛠️ ეს აკლდა შენს კოდს
    
    prize_setting = Settings.query.filter_by(key='prize_pool').first()
    current_week_prize_pool = float(prize_setting.value) if prize_setting else 1200.0

    top_region = RegionScore.query.order_by(RegionScore.score.desc()).first()
    top_region_users = []
    
    if top_region:
        region_users = [u for u in users if u.region == top_region.region_id and not u.is_admin]
        top_region_users = sorted(region_users, key=lambda x: (x.total_clicks or 0), reverse=True)

    user_stats = {}
    for u in users:
        watched_ads_count = UserAdView.query.filter_by(user_id=u.id).count()
        user_stats[u.id] = {
            'watched_ads': watched_ads_count,
            'activity_score': (u.total_clicks or 0) + (watched_ads_count * 2)
        }

    users_sorted = sorted(users, key=lambda x: user_stats[x.id]['activity_score'], reverse=True)

    users_by_region = {}
    for reg in regions:
        users_by_region[reg.region_id] = {
            'name': reg.region_name,
            'users': [u for u in users_sorted if u.region == reg.region_id]
        }
    
    region_sponsors = {}
    for reg in regions:
        if reg.sponsor_image and reg.sponsor_image.strip() != "":
            region_sponsors[reg.region_id] = reg.sponsor_image
        else:
            region_sponsors[reg.region_id] = None

    quiz_questions = QuizQuestion.query.all()

    return render_template('admin_dashboard.html', 
                           users=users_sorted, 
                           users_by_region=users_by_region,
                           user_stats=user_stats,
                           regions=regions, 
                           partners=partners, # 🛠️ გადავცემთ partners
                           region_sponsors=region_sponsors,
                           current_week_prize_pool=current_week_prize_pool,
                           top_region=top_region,
                           top_region_users=top_region_users,
                           quiz_questions=quiz_questions)

# ... (დანარჩენი ფუნქციები დატოვე ისე, როგორც იყო) ...

@app.route('/admin/user/<int:user_id>/update', methods=['POST'])
@login_required
def admin_full_update_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.balance = float(request.form.get('balance', user.balance))
    user.reputation = int(request.form.get('reputation', user.reputation))
    user.clicks_left = int(request.form.get('clicks_left', user.clicks_left))
    
    # 🛠️ ადმინს შეუძლია სრული სახელისა და მეილის განახლებაც
    if request.form.get('full_name'):
        user.full_name = request.form.get('full_name').strip()
    if request.form.get('email'):
        user.email = request.form.get('email').strip()
        
    # 🛠️ ახალი პაროლის შეცვლა ადმინ-პანელიდან (თუ ადმინმა ახალი ჩაწერა)
    new_password = request.form.get('new_password')
    if new_password and new_password.strip():
        user.password = generate_password_hash(new_password.strip(), method='pbkdf2:sha256')

    user.region = request.form.get('region', user.region)
    user.is_admin = True if request.form.get('is_admin') == 'on' else False
    user.is_banned = True if request.form.get('is_banned') == 'on' else False
    
    db.session.commit()
    flash(f"მომხმარებელი {user.username} წარმატებით განახლდა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("საკუთარ თავს ვერ წაშლი!", "danger")
        return redirect(url_for('admin_dashboard'))
    db.session.delete(user)
    db.session.commit()
    flash("მომხმარებელი წარმატებით წაიშალა ბაზიდან!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/withdrawal/<int:req_id>/<action>')
@login_required
def admin_withdrawal_action(req_id, action):
    if not current_user.is_admin:
        abort(403)
    req = WithdrawalRequest.query.get_or_404(req_id)
    if req.status != 'pending':
        flash("ეს მოთხოვნა უკვე დამუშავებულია!", "warning")
        return redirect(url_for('admin_dashboard'))

    if action == 'approve':
        req.status = 'approved'
        flash("მოთხოვნა დამტკიცებულია!", "success")
    elif action == 'reject':
        req.status = 'rejected'
        user = User.query.get(req.user_id)
        if user:
            user.balance += req.amount 
        flash("მოთხოვნა უარყოფილია, თანხა დაბრუნდა ბალანსზე.", "warning")
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/task/<int:task_id>/delete')
@login_required
def admin_delete_task(task_id):
    if not current_user.is_admin:
        abort(403)
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("დავალება წაშლილია!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/region/sponsor', methods=['POST'])
@login_required
def admin_update_sponsor():
    if not current_user.is_admin:
        abort(403)
    region_id = request.form.get('region_id')
    file = request.files.get('sponsor_image')
    
    if file and region_id and allowed_file(file.filename):
        # 🛠️ ვცვლით ფაილად შენახვას ბაზაში Base64 ტექსტად შენახვით
        encoded_string = base64.b64encode(file.read()).decode('utf-8')
        image_data = f"data:image/jpeg;base64,{encoded_string}"
        
        region = RegionScore.query.filter_by(region_id=region_id).first()
        if region:
            region.sponsor_image = image_data  # ვწერთ ბაზის სვეტში
            db.session.commit()
            flash("სპონსორის ფოტო წარმატებით შეინახა ბაზაში!", "success")
        else:
            flash("რეგიონი ვერ მოიძებნა ბაზაში.", "danger")
    else:
        flash("გთხოვთ ატვირთოთ სწორი ფოტო.", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/region/<region_id>/delete_sponsor', methods=['POST'])
@login_required
def admin_delete_sponsor(region_id):
    if not current_user.is_admin:
        abort(403)
    
    region = RegionScore.query.filter_by(region_id=region_id).first()
    if region:
        region.sponsor_image = ""  # ვასუფთავებთ ბაზაში სურათის ველს
        db.session.commit()
        flash("სპონსორის ფოტო წაშლილია!", "success")
    else:
        flash("რეგიონი ვერ მოიძებნა.", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/region/<region_id>/reset_score', methods=['POST'])
@login_required
def admin_reset_region_score(region_id):
    if not current_user.is_admin:
        abort(403)
    region = RegionScore.query.filter_by(region_id=region_id).first_or_404()
    region.score = 0
    db.session.commit()
    flash(f"რეგიონის ({region.region_name}) კლიკები განულდა!", "success")
    return redirect(url_for('admin_dashboard'))

# 🛠️ ახალი: რეგიონის ყველა მომხმარებლის კლიკებისა და ბალანსის მასობრივი განულება
@app.route('/admin/region/<region_id>/reset_users_data/<action_type>', methods=['POST'])
@login_required
def admin_reset_region_users(region_id, action_type):
    if not current_user.is_admin:
        abort(403)
    
    users_in_region = User.query.filter_by(region=region_id).all()
    for u in users_in_region:
        if action_type == 'clicks':
            u.total_clicks = 0
            u.clicks_left = 250
        elif action_type == 'balance':
            u.balance = 0.0
            
    db.session.commit()
    flash(f"რეგიონის მომხმარებლების {action_type} წარმატებით განულდა!", "success")
    return redirect(url_for('admin_dashboard'))

# 🛠️ ახალი: მთელი პლატფორმის მასშტაბით სრული განულება
@app.route('/admin/reset_all_global', methods=['POST'])
@login_required
def admin_reset_all_global():
    if not current_user.is_admin:
        abort(403)
    
    User.query.update({User.total_clicks: 0, User.clicks_left: 250, User.balance: 0.0})
    RegionScore.query.update({RegionScore.score: 0})
    db.session.commit()
    
    flash("მთელი პლატფორმის მასშტაბით ყველა იუზერის კლიკები და ბალანსი განულდა!", "success")
    return redirect(url_for('admin_dashboard'))

# 🛠️ ახალი: API მომხმარებლის რეგიონის წევრების ლაივ სიისთვის (დაშბორდისთვის)
@app.route('/api/region_team_stats')
@login_required
def api_region_team_stats():
    team_users = User.query.filter_by(region=current_user.region).order_by(User.total_clicks.desc()).all()
    
    users_data = [{
        "username": u.username,
        "total_clicks": u.total_clicks,
        "is_current": u.id == current_user.id
    } for u in team_users]
    
    return jsonify({
        "success": True,
        "region_id": current_user.region,
        "users": users_data
    })

@app.route('/admin/ads', methods=['GET', 'POST'])
@login_required
def admin_manage_ads():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        title = request.form.get('title')
        video_url = request.form.get('video_url')
        video_file = request.files.get('video_file')
         
        final_url = ""
        if video_file and video_file.filename != '':
            filename = f"ad_{datetime.datetime.now().timestamp()}.mp4"
            ads_folder = os.path.join(app.root_path, 'static', 'ads_videos')
            os.makedirs(ads_folder, exist_ok=True)
            filepath = os.path.join(ads_folder, filename)
            video_file.save(filepath)
            final_url = url_for('static', filename=f'ads_videos/{filename}')
        elif video_url:
            final_url = video_url

        if title and final_url:
            new_ad = Advertisement(title=title, video_url=final_url)
            db.session.add(new_ad)
            db.session.commit()
            flash("რეკლამა წარმატებით დაემატა!", "success")
        return redirect(url_for('admin_manage_ads'))
    
    ads = Advertisement.query.all()
    return render_template('admin_ads.html', ads=ads)

@app.route('/admin/ads/delete/<int:ad_id>', methods=['POST'])
@login_required
def admin_delete_ad(ad_id):
    if not current_user.is_admin:
        abort(403)
    ad = Advertisement.query.get_or_404(ad_id)
    db.session.delete(ad)
    db.session.commit()
    flash("რეკლამა წარმატებით წაიშალა!", "success")
    return redirect(url_for('admin_manage_ads'))

@app.route('/admin/settings/prize', methods=['POST'])
@login_required
def admin_update_prize():
    if not current_user.is_admin:
        abort(403)
    new_prize = request.form.get('prize_pool')
    if new_prize:
        setting = Settings.query.filter_by(key='prize_pool').first()
        if setting:
            setting.value = new_prize
        else:
            db.session.add(Settings(key='prize_pool', value=new_prize))
        db.session.commit()
        flash("საპრიზო ფონდი წარმატებით განახლდა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings/toggle_game', methods=['POST'])
@login_required
def admin_toggle_game():
    if not current_user.is_admin:
        abort(403)
    setting = Settings.query.filter_by(key='game_status').first()
    if setting:
        setting.value = 'paused' if setting.value == 'active' else 'active'
    else:
        db.session.add(Settings(key='game_status', value='paused'))
    db.session.commit()
    flash("თამაშის რეჟიმი შეიცვალა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/season/reset', methods=['POST'])
@login_required
def admin_reset_season():
    if not current_user.is_admin:
        abort(403)
    
    top_region = RegionScore.query.order_by(RegionScore.score.desc()).first()
    if top_region:
        winner_name = top_region.region_name
        setting = Settings.query.filter_by(key='last_winner').first()
        if setting:
            setting.value = winner_name
        else:
            db.session.add(Settings(key='last_winner', value=winner_name))

    # ვანულებთ რეგიონების ქულებს
    RegionScore.query.update({RegionScore.score: 0})
    
    # ვანულებთ იუზერების კლიკებს, უბრუნებთ ენერგიას და სურვილისამებრ ვანულებთ ბალანსსაც (სურვილისამებრ მიამატე balance: 0.0)
    User.query.update({
        User.clicks_left: 250, 
        User.total_clicks: 0,
        User.balance: 0.0  # <-- ჩაურთე ეს ხაზი, თუ ფულის ბალანსის განულებაც გინდა სეზონის თავიდან დასაწყებად
    })
    
    db.session.commit()
    
    flash("სეზონი დასრულდა! გამარჯვებული შენახულია და ქულები/კლიკები განულდა.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/chats')
@login_required
def admin_chats():
    if not current_user.is_admin:
        abort(403)
    regions = RegionScore.query.all()
    selected_region = request.args.get('region', 'tbilisi')
    messages = Question.query.filter_by(region_id=selected_region).order_by(Question.id.asc()).all()
    return render_template('admin_chats.html', regions=regions, selected_region=selected_region, messages=messages)

@app.route('/admin/chats/send', methods=['POST'])
@login_required
def admin_chats_send():
    if not current_user.is_admin:
        abort(403)
    region_id = request.form.get('region_id')
    text = request.form.get('message')
    if text and text.strip() and region_id:
        new_q = Question(text=text.strip(), username=f"👑 ადმინი ({current_user.username})", user_phone="", region_id=region_id)
        db.session.add(new_q)
        db.session.commit()
    return redirect(url_for('admin_chats', region=region_id))

@app.route('/admin/chats/delete/<int:msg_id>', methods=['POST'])
@login_required
def admin_chats_delete_msg(msg_id):
    if not current_user.is_admin:
        abort(403)
    msg = Question.query.get_or_404(msg_id)
    region_id = msg.region_id
    db.session.delete(msg)
    db.session.commit()
    flash("შეტყობინება წაშლილია ჩატიდან.", "success")
    return redirect(url_for('admin_chats', region=region_id))

@app.route('/admin/distribute_prizes', methods=['POST'])
@login_required
def admin_distribute_prizes():
    if not current_user.is_admin:
        abort(403)
    
    top_region = RegionScore.query.order_by(RegionScore.score.desc()).first()
    if not top_region:
        flash("რეგიონები ვერ მოიძებნა!", "danger")
        return redirect(url_for('admin_dashboard'))

    prize_setting = Settings.query.filter_by(key='prize_pool').first()
    total_prize = float(prize_setting.value) if prize_setting else 1200.0

    # 🛠️ ფილტრი: ვტოვებთ მხოლოდ იმ იუზერებს, ვისაც აქვთ მინიმუმ 5000 კლიკი და არ არიან ადმინები
    region_users = [u for u in User.query.filter_by(region=top_region.region_id).all() if not u.is_admin and u.total_clicks >= 5000]
    
    if not region_users:
        flash("გამარჯვებულ რეგიონში არ არიან მომხმარებლები, რომლებმაც დააგროვეს მინიმუმ 5000 კლიკი!", "warning")
        return redirect(url_for('admin_dashboard'))

    sorted_r_users = sorted(region_users, key=lambda x: x.total_clicks, reverse=True)

    p1, p2, rest = 0, 0, 0
    if len(sorted_r_users) == 1:
        p1 = total_prize
        sorted_r_users[0].balance += p1
    elif len(sorted_r_users) == 2:
        p1 = total_prize * 0.60
        p2 = total_prize * 0.40
        sorted_r_users[0].balance += p1
        sorted_r_users[1].balance += p2
    else:
        p1 = total_prize * 0.50
        p2 = total_prize * 0.30
        sorted_r_users[0].balance += p1
        sorted_r_users[1].balance += p2
        rest_share = (total_prize * 0.20) / (len(sorted_r_users) - 2)
        for u in sorted_r_users[2:]:
            u.balance += rest_share

    winner_st = Settings.query.filter_by(key='last_winner').first()
    winner_text = f"{top_region.region_name} (1-ლი ადგილი: {sorted_r_users[0].username} - {p1:.1f} ₾ | მინ. 5000 კლიკი დაკმაყოფილებულია)"
    if winner_st:
        winner_st.value = winner_text
    else:
        db.session.add(Settings(key='last_winner', value=winner_text))

    db.session.commit()
    flash(f"საპრიზო თანხები წარმატებით ჩაერიცხა იმ მოთამაშეებს, რომლებმაც გადალახეს 5000 კლიკის ზღვარი!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/quiz/add', methods=['POST'])
@login_required
def admin_add_quiz_question():
    if not current_user.is_admin:
        abort(403)
    
    sponsor_name = request.form.get('sponsor_name')
    package_type = request.form.get('package_type', 'Bronze')
    question_text = request.form.get('question_text')
    option_1 = request.form.get('option_1')
    option_2 = request.form.get('option_2')
    option_3 = request.form.get('option_3')
    option_4 = request.form.get('option_4')
    correct_option = int(request.form.get('correct_option', 1))
    
    image_url = ""
    file = request.files.get('sponsor_image')
    if file and file.filename != '' and allowed_file(file.filename):
        encoded_string = base64.b64encode(file.read()).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{encoded_string}"

    if sponsor_name and question_text:
        new_q = QuizQuestion(
            sponsor_name=sponsor_name,
            sponsor_image=image_url,
            package_type=package_type,
            question_text=question_text,
            option_1=option_1,
            option_2=option_2,
            option_3=option_3,
            option_4=option_4,
            correct_option=correct_option
        )
        db.session.add(new_q)
        db.session.commit()
        flash("სპონსორის ვიქტორინის კითხვა და ბანერი წარმატებით დაემატა!", "success")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/quiz/delete/<int:quiz_id>', methods=['POST'])
@login_required
def admin_delete_quiz(quiz_id):
    if not current_user.is_admin:
        abort(403)
    quiz = QuizQuestion.query.get_or_404(quiz_id)
    
    # 🛠️ ჯერ ვშლით მიბმულ პასუხებს UserQuizAnswer ცხრილიდან, რომ ForeignKey შეზღუდვამ ხელი არ შეუშალოს წაშლას
    UserQuizAnswer.query.filter_by(quiz_id=quiz_id).delete()

    if quiz.sponsor_image:
        try:
            img_path = os.path.join(app.root_path, quiz.sponsor_image.lstrip('/'))
            if os.path.exists(img_path):
                os.remove(img_path)
        except:
            pass
    db.session.delete(quiz)
    db.session.commit()
    flash("ვიქტორინის კითხვა წარმატებით წაიშალა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/quiz/edit/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_quiz(quiz_id):
    if not current_user.is_admin:
        abort(403)
    quiz = QuizQuestion.query.get_or_404(quiz_id)
    if request.method == 'POST':
        quiz.sponsor_name = request.form.get('sponsor_name')
        quiz.package_type = request.form.get('package_type', 'Bronze')
        quiz.question_text = request.form.get('question_text')
        quiz.option_1 = request.form.get('option_1')
        quiz.option_2 = request.form.get('option_2')
        quiz.option_3 = request.form.get('option_3')
        quiz.option_4 = request.form.get('option_4')
        quiz.correct_option = int(request.form.get('correct_option', 1))
        
        file = request.files.get('sponsor_image')
        if file and file.filename != '':
            filename = f"quiz_{datetime.datetime.now().timestamp()}.jpg"
            ads_folder = os.path.join(app.root_path, 'static', 'quiz_ads')
            os.makedirs(ads_folder, exist_ok=True)
            filepath = os.path.join(ads_folder, filename)
            file.save(filepath)
            quiz.sponsor_image = url_for('static', filename=f'quiz_ads/{filename}')
            
        db.session.commit()
        flash("ვიქტორინის კითხვა წარმატებით განახლდა!", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_quiz.html', quiz=quiz)

@app.route('/admin/quiz/delete_all', methods=['POST'])
@login_required
def admin_delete_all_quizzes():
    if not current_user.is_admin:
        abort(403)
    UserQuizAnswer.query.delete()
    QuizQuestion.query.delete()
    db.session.commit()
    flash("ყველა ვიქტორინის კითხვა წარმატებით წაიშალა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/api/restore_energy', methods=['POST'])
@login_required
def restore_energy():
    current_user.clicks_left = 250
    db.session.commit()
    return jsonify({"success": True, "new_clicks": 250})

# 🛠️ აპლიკაციის ინიციალიზაცია და ბაზის ცხრილების/სვეტების შექმნა
with app.app_context():
    db.create_all()
    
    # პირველი ბლოკი
    try:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clicks_left INTEGER DEFAULT 250;"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_clicks INTEGER DEFAULT 0;"))
        db.session.execute(db.text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS region_id VARCHAR(50) DEFAULT 'tbilisi';"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100) DEFAULT '';"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100) DEFAULT '';"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS holder_name VARCHAR(100) DEFAULT '';"))
        
        db.session.execute(db.text("ALTER TABLE region_scores ADD COLUMN IF NOT EXISTS sponsor_image TEXT DEFAULT '';"))
        
        db.session.execute(db.text("CREATE TABLE IF NOT EXISTS quiz_questions (id SERIAL PRIMARY KEY, sponsor_name VARCHAR(100) NOT NULL, sponsor_image TEXT DEFAULT '', package_type VARCHAR(20) DEFAULT 'Bronze', question_text TEXT NOT NULL, option_1 VARCHAR(150) NOT NULL, option_2 VARCHAR(150) NOT NULL, option_3 VARCHAR(150) NOT NULL, option_4 VARCHAR(150) NOT NULL, correct_option INTEGER NOT NULL);"))
        db.session.execute(db.text("CREATE TABLE IF NOT EXISTS user_quiz_answers (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), quiz_id INTEGER REFERENCES quiz_questions(id));"))
        
        # 🛠️ ვზრდით ლიმიტებს TEXT ტიპზე, რომ დიდი ბაზის ფოტოები ჩაეტიოს
        db.session.execute(db.text("ALTER TABLE quiz_questions ALTER COLUMN sponsor_image TYPE TEXT;"))
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    # რეგიონების ინიციალიზაცია გადავიტანეთ აქ, სვეტების შექმნის მერე
    init_regions()

    # მეორე ბლოკი (ვერიფიკაცია და პარტნიორები)
    try:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) DEFAULT 'none';"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_number VARCHAR(11);"))
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_photo TEXT;"))
        db.session.execute(db.text("CREATE TABLE IF NOT EXISTS partner_sponsors (id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, website_url VARCHAR(255) NOT NULL, logo TEXT NOT NULL);"))
        
        # 🛠️ ვზრდით ლიმიტებს ვერიფიკაციისა და პარტნიორების ფოტოებისთვისაც
        db.session.execute(db.text("ALTER TABLE users ALTER COLUMN verification_photo TYPE TEXT;"))
        db.session.execute(db.text("ALTER TABLE partner_sponsors ALTER COLUMN logo TYPE TEXT;"))
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    if not Settings.query.filter_by(key='prize_pool').first():
        db.session.add(Settings(key='prize_pool', value='1200'))
    if not Settings.query.filter_by(key='last_winner').first():
        db.session.add(Settings(key='last_winner', value='იმერეთი'))
    
    game_status_st = Settings.query.filter_by(key='game_status').first()
    if not game_status_st:
        db.session.add(Settings(key='game_status', value='active'))
    
    # 👑 ავტომატურად ვანიჭებთ ადმინის უფლებას მხოლოდ noventra_admin-ს
    admin_user = User.query.filter_by(username='noventra_admin').first()
    if admin_user:
        admin_user.is_admin = True

    db.session.commit()

# 🪪 ვერიფიკაციის მოთხოვნის გაგზავნა იუზერის მიერ
@app.route('/submit_verification', methods=['POST'])
@login_required
def submit_verification():
    personal_number = request.form.get('personal_number')
    photo = request.files.get('verification_photo')

    if not personal_number or len(personal_number) != 11:
        flash('გთხოვთ შეიყვანოთ სწორი 11-ნიშნა პირადი ნომერი.', 'danger')
        return redirect(url_for('dashboard'))

    if photo and allowed_file(photo.filename):
        encoded_string = base64.b64encode(photo.read()).decode('utf-8')
        image_data = f"data:image/jpeg;base64,{encoded_string}"
        
        current_user.personal_number = personal_number
        current_user.verification_photo = image_data  # ინახება ბაზაში ტექსტად
        current_user.verification_status = 'pending'
        db.session.commit()
        
        flash('ვერიფიკაციის მოთხოვნა წარმატებით გაიგზავნა!', 'success')
    else:
        flash('გთხოვთ ატვირთოთ სწორი ფოტო ფორმატი.', 'danger')

    return redirect(url_for('dashboard'))

# 🏢 საჯარო სპონსორების კატალოგის გვერდი
@app.route('/sponsors')
def sponsors_catalog():
    sponsors = PartnerSponsor.query.all()
    return render_template('sponsors_catalog.html', sponsors=sponsors)

# ⚙️ ადმინი: პარტნიორი სპონსორის დამატება კატალოგში
@app.route('/admin/add_partner_sponsor', methods=['POST'])
@login_required
def admin_add_partner_sponsor():
    if not current_user.is_admin:
        abort(403)
        
    name = request.form.get('name')
    website_url = request.form.get('website_url')
    logo = request.files.get('logo')

    if logo and allowed_file(logo.filename):
        encoded_string = base64.b64encode(logo.read()).decode('utf-8')
        image_data = f"data:image/jpeg;base64,{encoded_string}"
         
        new_sponsor = PartnerSponsor(
            name=name,
            website_url=website_url,
            logo=image_data  # ინახება ბაზაში ტექსტად
        )
        db.session.add(new_sponsor)
        db.session.commit()
        flash('პარტნიორი სპონსორი წარმატებით დაემატა კატალოგში!', 'success')
    else:
        flash('გთხოვთ ატვირთოთ სწორი ლოგოს ფოტო.', 'danger')

    return redirect(url_for('admin_dashboard'))

# ⚙️ ადმინი: პარტნიორი სპონსორის წაშლა კატალოგიდან
@app.route('/admin/delete_partner_sponsor/<int:sponsor_id>', methods=['POST'])
@login_required
def admin_delete_partner_sponsor(sponsor_id):
    if not current_user.is_admin:
        abort(403)
        
    sponsor = PartnerSponsor.query.get_or_404(sponsor_id)
    db.session.delete(sponsor)
    db.session.commit()
    flash('პარტნიორი წაიშალა კატალოგიდან.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/api/user_status')
@login_required
def api_user_status():
    game_status_setting = Settings.query.filter_by(key='game_status').first()
    game_status = game_status_setting.value if game_status_setting else "active"

    prize_setting = Settings.query.filter_by(key='prize_pool').first()
    prize_pool = prize_setting.value if prize_setting else "1200"

    regions = RegionScore.query.all()
    regions_data = {r.region_id: r.score for r in regions}

    return jsonify({
        "success": True,
        "balance": current_user.balance,
        "clicks_left": current_user.clicks_left,
        "reputation": current_user.reputation,
        "game_status": game_status,
        "prize_pool": prize_pool,
        "regions": regions_data
    })

if __name__ == '__main__':
    app.run(debug=True)
