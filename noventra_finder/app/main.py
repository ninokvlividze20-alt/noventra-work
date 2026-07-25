from flask import Flask, render_template, request, session, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'noventra_secret_key_2026'

UPLOAD_FOLDER = 'app/static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

daily_visits = 0

# გაერთიანებული და გამართული ქეშის კონტროლი
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.before_request
def update_visitor_count():
    global daily_visits
    daily_visits += 1

def get_db_connection():
    conn = psycopg2.connect(
        host='localhost',
        database='noventra_db',
        user='mac',
        password='noventra2026'
    )
    return conn

def get_slot_data(slot_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM portfolios WHERE slot_id = %s", (slot_id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return data

def render_page(template, **kwargs):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. ყველა სლოტი და კოორდინატები რუკისთვის
    cur.execute("SELECT slot_id, business_name, is_paid, latitude, longitude FROM portfolios")
    portfolios = cur.fetchall()
    
    # 2. Live Hub-ისთვის ბიზნესები (რომ არასოდეს გაქრეს)
    cur.execute("SELECT business_name, category_type, subcategory, location, slot_id FROM portfolios ORDER BY slot_id DESC LIMIT 10")
    live_businesses = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # ვუზრუნველყოფთ, რომ ყველა საჭირო მონაცემი გადაეცეს შაბლონს
    context = {
        'portfolios': portfolios, 
        'live_businesses': live_businesses, 
        'daily_visits': daily_visits, 
        **kwargs
    }
    
    if request.headers.get('HX-Request'):
        return render_template(template, **context)
    
    return render_template('index.html', content_template=template, **context)

# დამხმარე ფუნქცია მთავარი გვერდისთვის
def get_index_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. ყველა სლოტი და კოორდინატები რუკისთვის
    cur.execute("SELECT slot_id, business_name, is_paid, latitude, longitude FROM portfolios")
    portfolios = cur.fetchall()
    
    # 2. ბოლო რეგისტრირებული ბიზნესები Live Hub-ისთვის (უზრუნველყოფს მხოლოდ შევსებული ბიზნესების გამოტანას)
    cur.execute("SELECT business_name, category_type, subcategory, location, slot_id FROM portfolios WHERE business_name IS NOT NULL AND business_name != '' ORDER BY slot_id DESC LIMIT 10")
    live_businesses = cur.fetchall()
    
    cur.close()
    conn.close()
    return portfolios, live_businesses, daily_visits

business_categories = {
    'natural': {
        'title': 'ეკო-პროდუქტები',
        'subcategories': ['ნატურალური რძის ნაწარმი', 'ხელნაკეთი ნივთები', 'თაფლი, ჩურჩხელა', 'ეკო-კოსმეტიკა']
    },
    'services': {
        'title': 'სერვის-ჰაბი',
        'subcategories': ['სანტექნიკა/ელექტრიკოსი', 'ავეჯის შემკეთებელი', 'სალონები/მასაჟი', 'ავტო-სერვისი']
    },
    'education': {
        'title': 'ცოდნის ბაზა',
        'subcategories': ['კერძო რეპეტიტორები', 'კომპიუტერული პროგრამები', 'უცხო ენები', 'კრეატიული სტუდია']
    },
    'startups': {
        'title': 'ბიზნეს-კატალოგი',
        'subcategories': ['სახლის საკონდიტროები', 'IT სერვისები', 'კრეატიული ბიზნესები', 'ონლაინ სტარტაპები']
    }
}

@app.route('/')
def index():
    portfolios, live_businesses, visits = get_index_data()
    return render_template('index.html', portfolios=portfolios, live_businesses=live_businesses, daily_visits=visits)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/my-profile')
def my_profile():
    if not session.get('user_id'):
        return redirect(url_for('register'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT slot_id FROM portfolios WHERE user_id = %s", (session.get('user_id'),))
    portfolio = cur.fetchone()
    cur.close()
    conn.close()
    
    if portfolio:
        return redirect(url_for('view_business_profile', slot_id=portfolio['slot_id']))
    else:
        return redirect(url_for('register_business'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        # პაროლის დაშიფვრა უსაფრთხოებისთვის
        password = generate_password_hash(request.form['password'])
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # 1. ვრეგისტრირებთ მომხმარებელს და ვთხოვთ დაბრუნდეს მისი ID
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id", 
                        (username, email, password))
            new_user = cur.fetchone()
            conn.commit()
            
            # 2. ავტომატურად ვანთებთ სესიას (Auto-login)
            session['user_id'] = new_user['id']
            session['username'] = username
            
            # 3. ვამოწმებთ აქვს თუ არა უკვე პორტფოლიო (ახლისთვის იქნება ცარიელი)
            cur.execute("SELECT slot_id FROM portfolios WHERE user_id = %s", (new_user['id'],))
            portfolio_data = cur.fetchone()
            if portfolio_data:
                session['slot_id'] = portfolio_data['slot_id']
            else:
                session['slot_id'] = None
            
            # 4. რეგისტრაციის შემდეგ პირდაპირ ბიზნესის რეგისტრაციაზე გადავამისამართოთ
            return redirect(url_for('register_business'))
        except Exception as e:
            conn.rollback()
            # შეცდომის დროს ვაბრუნებთ ერთიან auth.html-ს შეტყობინებით
            return render_template('auth.html', error=f"რეგისტრაციის შეცდომა (შეიძლება სახელი ან მეილი დაკავებულია): {e}")
        finally:
            cur.close()
            conn.close()
            
    # GET მოთხოვნისას (როცა ღილაკით გადმოვა) ვტვირთვათ ერთიან ავტორიზაციის გვერდს
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    identifier = request.form['email_or_username']
    password = request.form['password']
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (identifier, identifier))
        user = cur.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            cur.execute("SELECT slot_id FROM portfolios WHERE user_id = %s", (user['id'],))
            portfolio = cur.fetchone()
            session['slot_id'] = portfolio['slot_id'] if portfolio else None
            
            return redirect(url_for('register_business'))
        else:
            return render_template('auth.html', error="არასწორი სახელი/მეილი ან პაროლი")
    except Exception as e:
        return render_template('auth.html', error=f"შეცდომა: {e}")
    finally:
        cur.close()
        conn.close()

@app.route('/ad-builder', defaults={'slot_id': None})
@app.route('/ad-builder/<int:slot_id>')
def ad_builder(slot_id):
    return render_page('ad_builder.html', slot_id=slot_id or 1)

@app.route('/save-portfolio/<int:slot_id>', methods=['POST'])
def save_portfolio(slot_id):
    file = request.files.get('photo')
    existing_data = get_slot_data(slot_id)
    photo_path = existing_data['photo_path'] if existing_data else None

    if file and file.filename != '':
        filename = secure_filename(f"slot_{slot_id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        photo_path = f"uploads/{filename}"

    # ვკითხულობთ კოორდინატებს ფორმიდან
    lat = request.form.get('latitude')
    lng = request.form.get('longitude')
    lat = float(lat) if lat else None
    lng = float(lng) if lng else None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO portfolios (slot_id, business_name, description, phone, email, photo_path, 
                                    social_fb, social_ig, social_tt, social_yt, location, category_type, subcategory, user_id, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slot_id) DO UPDATE SET 
            business_name=EXCLUDED.business_name, description=EXCLUDED.description, 
            phone=EXCLUDED.phone, email=EXCLUDED.email, photo_path=EXCLUDED.photo_path,
            social_fb=EXCLUDED.social_fb, social_ig=EXCLUDED.social_ig, 
            social_tt=EXCLUDED.social_tt, social_yt=EXCLUDED.social_yt,
            location=EXCLUDED.location, category_type=EXCLUDED.category_type, subcategory=EXCLUDED.subcategory, user_id=EXCLUDED.user_id,
            latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude
        """, (slot_id, request.form['business_name'], request.form['description'], 
              request.form['phone'], request.form.get('email', ''), photo_path,
              request.form.get('social_fb', ''), request.form.get('social_ig', ''), 
              request.form.get('social_tt', ''), request.form.get('social_yt', ''),
              f"{request.form.get('location_district', 'თბილისი')}, {request.form.get('address', 'მისამართი არ არის მითითებული')}", 
              request.form.get('category_type', 'none'), 
              request.form.get('subcategory', ''),
              session.get('user_id'), lat, lng))
        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('view_business_profile', slot_id=slot_id))
    except Exception as e:
        return f"შეცდომა ბაზასთან: {e}"

# 1. განახლებული view_business_profile, რომელიც ქაჩავს გალერეის ფოტოებსაც
@app.route('/business-profile/<int:slot_id>')
def view_business_profile(slot_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # ამოვიღოთ პორტფოლიო
    cur.execute("SELECT * FROM portfolios WHERE slot_id = %s", (slot_id,))
    portfolio = cur.fetchone()
    
    # ამოვიღოთ ამ სლოტის გალერეის ფოტოები (ORDER BY id DESC აწყობს ახალს პირველ ადგილზე!)
    cur.execute("SELECT * FROM portfolio_gallery WHERE slot_id = %s ORDER BY id DESC", (slot_id,))
    gallery = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not portfolio:
        return "ბიზნესი ვერ მოიძებნა", 404

    # შემოწმება: არის თუ არა შემოსული მომხმარებელი ამ ბიზნესის მფლობელი
    is_owner = (
        session.get('user_id') and 
        portfolio.get('user_id') and 
        int(session.get('user_id')) == int(portfolio['user_id'])
    )

    # თუ მფლობელია, ვაჩვენებთ სამართავ პანელს, თუ სტუმარია - საჯარო გვერდს
    if is_owner:
        return render_template('owner_portfolio.html', portfolio=portfolio, gallery=gallery)
    else:
        return render_template('view_portfolio.html', portfolio=portfolio, gallery=gallery)

# 2. გალერეაში ახალი ფოტოს ატვირთვის მარშრუტი
@app.route('/upload-gallery/<int:slot_id>', methods=['POST'])
def upload_gallery(slot_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT user_id FROM portfolios WHERE slot_id = %s", (slot_id,))
    portfolio = cur.fetchone()
    
    # თუ პორტფოლიო არ მოიძებნა
    if not portfolio:
        cur.close()
        conn.close()
        return "ბიზნესი ვერ მოიძებნა", 404

    file = request.files.get('gallery_photo')
    if file and file.filename != '':
        filename = secure_filename(f"gallery_slot_{slot_id}_{os.urandom(4).hex()}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        photo_path = f"uploads/{filename}"

        cur.execute("INSERT INTO portfolio_gallery (slot_id, photo_path) VALUES (%s, %s)", (slot_id, photo_path))
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for('view_business_profile', slot_id=slot_id))

# 3. გალერეის ფოტოს წაშლის მარშრუტი
@app.route('/delete-gallery-photo/<int:photo_id>')
def delete_gallery_photo(photo_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM portfolio_gallery WHERE id = %s", (photo_id,))
    photo = cur.fetchone()
    
    if photo:
        cur.execute("SELECT user_id FROM portfolios WHERE slot_id = %s", (photo['slot_id'],))
        portfolio = cur.fetchone()
        
        if portfolio and portfolio['user_id'] == session.get('user_id'):
            cur.execute("DELETE FROM portfolio_gallery WHERE id = %s", (photo_id,))
            conn.commit()
            
    cur.close()
    conn.close()
    return redirect(url_for('view_business_profile', slot_id=photo['slot_id'] if photo else 1))

# ეს კი სლოტების მართვისთვის
@app.route('/slot-view/<int:slot_id>')
def view_slot(slot_id):
    # შენი ძველი ლოგიკა, რომელიც იყენებს get_slot_data(slot_id)
    return render_template('portfolio_view.html', portfolio=get_slot_data(slot_id))

@app.route('/edit-portfolio/<int:slot_id>', methods=['GET', 'POST'])
def edit_portfolio(slot_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. ჯერ ამოვიღოთ პორტფოლიო, რომ შევამოწმოთ მისი მფლობელი
    cur.execute("SELECT * FROM portfolios WHERE slot_id = %s", (slot_id,))
    portfolio = cur.fetchone()
    
    # 2. შემოწმება: არსებობს თუ არა ბიზნესი
    if not portfolio:
        cur.close()
        conn.close()
        return "ბიზნესი ვერ მოიძებნა", 404
        
    # [დამატებული დამცავი ხაზი]: თუ ძველი სლოტია და user_id არ აწერია, ავტომატურად მივამაგროთ ახლანდელ მფლობელს
    if not portfolio.get('user_id') and session.get('user_id'):
        cur.execute("UPDATE portfolios SET user_id = %s WHERE slot_id = %s", (session.get('user_id'), slot_id))
        conn.commit()
        portfolio['user_id'] = session.get('user_id')

    # 3. შენი მკაცრი შემოწმება: ეკუთვნის თუ არა ეს ბიზნესი ზუსტად იმ მომხმარებელს, ვინც ახლა სისტემაშია
    if portfolio.get('user_id') != session.get('user_id'):
        cur.close()
        conn.close()
        return "წვდომა აკრძალულია: ეს ბიზნესი თქვენ არ გეკუთვნით", 403

    # 4. თუ მფლობელია და აგზავნის განახლებულ მონაცემებს (POST)
    if request.method == 'POST':
        # ვკითხულობთ კოორდინატებს ფორმიდან (რუკამ რაც გადასცა)
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        lat = float(lat) if lat else None
        lng = float(lng) if lng else None

        cur.execute("""
            UPDATE portfolios SET 
            business_name=%s, description=%s, phone=%s, email=%s,
            social_fb=%s, social_ig=%s, social_tt=%s, social_yt=%s,
            category_type=%s, latitude=%s, longitude=%s
            WHERE slot_id=%s
        """, (request.form['business_name'], request.form['description'], 
              request.form['phone'], request.form.get('email'),
              request.form.get('social_fb'), request.form.get('social_ig'), 
              request.form.get('social_tt'), request.form.get('social_yt'),
              request.form.get('category_type'), lat, lng, slot_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('view_business_profile', slot_id=slot_id))
    
    # 5. თუ არის GET მოთხოვნა, ვუტვირთავთ რედაქტირების გვერდს არსებული მონაცემებით
    cur.close()
    conn.close()
    
    return render_template('edit_portfolio.html', portfolio=portfolio)

@app.route('/update-cover/<int:slot_id>', methods=['POST'])
def update_cover(slot_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT user_id FROM portfolios WHERE slot_id = %s", (slot_id,))
    portfolio = cur.fetchone()
    
    if not portfolio or portfolio['user_id'] != session.get('user_id'):
        cur.close()
        conn.close()
        return "წვდომა აკრძალულია", 403

    file = request.files.get('cover_photo')
    if file and file.filename != '':
        filename = secure_filename(f"cover_slot_{slot_id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        photo_path = f"uploads/{filename}"

        cur.execute("UPDATE portfolios SET photo_path = %s WHERE slot_id = %s", (photo_path, slot_id))
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for('view_business_profile', slot_id=slot_id))

@app.route('/category/<category_name>')
def show_category(category_name):
    valid_categories = ['natural', 'services', 'education', 'startups']
    if category_name not in valid_categories:
        return "კატეგორია ვერ მოიძებნა", 404
        
    # ვიჭერთ ქვეკატეგორიის ფილტრს URL-დან (მაგ: ?sub=უცხო ენები)
    subcategory = request.args.get('sub')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # თუ ქვეკატეგორია არჩეულია, ვფილტრავთ ბაზიდან
    if subcategory:
        cur.execute("SELECT * FROM portfolios WHERE category_type = %s AND subcategory = %s", (category_name, subcategory))
    else:
        # თუ არადა, გამოგვაქვს ამ კატეგორიის ყველა ბიზნესი
        cur.execute("SELECT * FROM portfolios WHERE category_type = %s", (category_name,))
        
    businesses = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_page(f"{category_name}.html", businesses=businesses, category_key=category_name, current_sub=subcategory)

@app.route('/about')
def about(): return render_page('about.html')

# საძიებო სისტემის მარშრუტი (მთლიანი ტექსტის შინაარსისა და ლოკაციის ჭკვიანი ფილტრაციით)
@app.route('/search')
def search_businesses():
    query = request.args.get('q', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if query:
        words = query.split()
        conditions = []
        params = []
        
        # თითოეული სიტყვისთვის ვამოწმებთ დამთხვევას ნებისმიერ ველში (სახელი, აღწერა, ლოკაცია, ქვეკატეგორია)
        for word in words:
            pattern = f"%{word}%"
            conditions.append("(business_name ILIKE %s OR description ILIKE %s OR location ILIKE %s OR subcategory ILIKE %s OR category_type ILIKE %s)")
            params.extend([pattern, pattern, pattern, pattern, pattern])
            
        sql = "SELECT * FROM portfolios WHERE " + " AND ".join(conditions)
        cur.execute(sql, tuple(params))
        results = cur.fetchall()
    else:
        results = []
        
    cur.close()
    conn.close()
    
    return render_template('search_results.html', results=results, query=query)

@app.route('/register-business', defaults={'slot_id': 1})
@app.route('/register-business/<int:slot_id>')
def register_business(slot_id):
    # თუ მომხმარებელი არ არის ავტორიზებული, ვაგზავნით რეგისტრაციის გვერდზე
    if not session.get('user_id'):
        return redirect(url_for('register'))
        
    return render_page('register_business.html', slot_id=slot_id)

@app.route('/register-ad')
def register_ad(): return render_page('register_ad.html')

@app.route('/contact')
def contact(): return render_page('contact.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
