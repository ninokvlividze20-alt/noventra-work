from app import app, db, User

with app.app_context():
    user = User.query.filter_by(username='ninikoshka').first()
    if user:
        user.is_admin = True
        db.session.commit()
        print("შენ ახლა ადმინი ხარ!")
    else:
        all_users = User.query.all()
        print("იუზერი ვერ მოიძებნა! ბაზაში არსებული იუზერებია:")
        for u in all_users:
            print("- " + u.username)
