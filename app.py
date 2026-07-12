# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None', # შეცვალე Lax -> None
    SESSION_COOKIE_SECURE=True,     # დაამატე ეს, რადგან HTTPS გვაქვს
)
app.config['SECRET_KEY'] = 'noventra_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_o6plSifKNIc9@ep-damp-thunder-asbmmuxu.c-4.eu-central-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # გამოსწორდა: იყო 'register'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    reputation = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash("მომხმარებელი ამ სახელით უკვე არსებობს!", "danger")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # ვქმნით ობიექტს მხოლოდ იმ ველებით, რომლებიც ბაზამ 100% იცის
        new_user = User(
            username=username, 
            email=email, 
            password=hashed_password
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash("რეგისტრაციისას დაფიქსირდა შეცდომა ბაზასთან კავშირში.", "danger")
            return redirect(url_for('register'))
            
    return render_template('signup_new.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            # დაამატე ეს ხაზი, რომ დავრწმუნდეთ სესია გააქტიურდა
            return redirect(url_for('dashboard'))
        
        flash("მომხმარებლის სახელი ან პაროლი არასწორია!", "danger")
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    all_tasks = Task.query.all()
    return render_template('dashboard.html', tasks=all_tasks)

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
    return redirect(url_for('dashboard'))

@app.route('/leaderboard')
@login_required
def leaderboard():
    top_users = User.query.order_by(User.balance.desc()).limit(10).all()
    return render_template('leaderboard.html', users=top_users)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        reward = float(request.form.get('reward'))
        new_task = Task(title=title, description=description, reward=reward)
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('add_task.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
