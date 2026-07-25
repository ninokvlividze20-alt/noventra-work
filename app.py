# -*- coding: utf-8 -*-
import re
from flask import Flask, render_template, request, redirect, url_for, abort, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True,
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

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    reputation = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), default="")
    bank_account = db.Column(db.String(50), default="")
    clicks_left = db.Column(db.Integer, default=100)
    region = db.Column(db.String(50), default="tbilisi")
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    withdrawals = db.relationship('WithdrawalRequest', backref='user', lazy=True)
    last_seen_board = db.Column(db.DateTime, default=db.func.current_timestamp())

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
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
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Advertisement(db.Model):
    __tablename__ = 'advertisements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(255), nullable=False)  # YouTube embed ან ვიდეო ლინკი
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
        db.session.commit()
        flash("მონაცემები დამახსოვრებულია!")
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/board', methods=['GET', 'POST'])
@login_required
def board():
    if request.method == 'POST':
        text = request.form.get('text')
        if is_safe(text):
            new_q = Question(text=text, username=current_user.username, user_phone=current_user.phone)
            db.session.add(new_q)
            db.session.commit()
        else:
            flash("მესიჯი არღვევს წესებს!", "danger")
    
    current_user.last_seen_board = db.func.current_timestamp()
    db.session.commit()
    
    questions = Question.query.order_by(Question.id.desc()).all()
    return render_template('board.html', questions=questions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        region = request.form.get('region', 'tbilisi')
        
        if User.query.filter_by(username=username).first():
            flash("მომხმარებელი ამ სახელით უკვე არსებობს!", "danger")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password, region=region)
        try:
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            return f"ბაზის შეცდომა: {str(e)}"
    return render_template('signup_new.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("მომხმარებლის სახელი ან პაროლი არასწორია!", "danger")
    return render_template('login.html')

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

    return render_template('dashboard.html', 
                         tasks=all_tasks, 
                         new_questions_count=new_questions_count,
                         total_tasks=total_tasks,
                         completion_rate=completion_rate,
                         regions=regions)

@app.route('/api/score', methods=['POST'])
@login_required
def add_score():
    data = request.get_json() or {}
    region_id = data.get('region_id')
    points = int(data.get('points', 1))
    
    region = RegionScore.query.filter_by(region_id=region_id).first()
    if region:
        region.score += points
        db.session.commit()
        return jsonify({"success": True, "new_score": region.score})
    
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

# 🎯 დავალების დეტალური ნახვა და შესრულება მომხმარებლისთვის
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

# 🎯 ადმინის მიერ ახალი დავალების შექმნა
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

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    users = User.query.all()
    tasks = Task.query.all()
    withdrawals = WithdrawalRequest.query.filter_by(status='pending').all()
    regions = RegionScore.query.all()
    
    ads_folder = os.path.join(app.root_path, 'static', 'ads')
    os.makedirs(ads_folder, exist_ok=True)
    
    region_sponsors = {}
    for reg in regions:
        filename = f"{reg.region_id}.jpg"
        filepath = os.path.join(ads_folder, filename)
        if os.path.exists(filepath):
            region_sponsors[reg.region_id] = url_for('static', filename=f'ads/{filename}')
        else:
            region_sponsors[reg.region_id] = None

    return render_template('admin_dashboard.html', users=users, tasks=tasks, withdrawals=withdrawals, regions=regions, region_sponsors=region_sponsors)

@app.route('/admin/user/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.balance = float(request.form.get('balance', user.balance))
    user.reputation = int(request.form.get('reputation', user.reputation))
    user.is_admin = True if request.form.get('is_admin') == 'on' else False
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
            user.balance += req.amount  # ზუსტად იმდენივე უბრუნდება, რამდენიც ჰქონდა მოთხოვნილი
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
    if file and region_id:
        filename = f"{region_id}.jpg"
        ads_folder = os.path.join(app.root_path, 'static', 'ads')
        os.makedirs(ads_folder, exist_ok=True)
        file.save(os.path.join(ads_folder, filename))
        flash("სპონსორის ფოტო წარმატებით აიტვირთა!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/region/<region_id>/delete_sponsor', methods=['POST'])
@login_required
def admin_delete_sponsor(region_id):
    if not current_user.is_admin:
        abort(403)
    filename = f"{region_id}.jpg"
    filepath = os.path.join(app.root_path, 'static', 'ads', filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash("სპონსორის ფოტო წაშლილია!", "success")
    else:
        flash("ფოტო ვერ მოიძებნა.", "warning")
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
        # თუ ფაილი ატვირთა ადმინმა
        if video_file and video_file.filename != '':
            filename = f"ad_{datetime.datetime.now().timestamp()}.mp4"
            ads_folder = os.path.join(app.root_path, 'static', 'ads_videos')
            os.makedirs(ads_folder, exist_ok=True)
            filepath = os.path.join(ads_folder, filename)
            video_file.save(filepath)
            final_url = url_for('static', filename=f'ads_videos/{filename}')
        # თუ ლინკი ჩაწერა
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

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

with app.app_context():
    db.create_all()
    init_regions()
    try:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clicks_left INTEGER DEFAULT 100;"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

if __name__ == '__main__':
    app.run(debug=True)
