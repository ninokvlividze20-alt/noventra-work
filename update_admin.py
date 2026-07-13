from app import app, db, User

with app.app_context():
    u = User.query.filter_by(username='ninikoshka').first()
    if u:
        u.username = 'admin'
        db.session.commit()
        print('წარმატებით შეცვლილია: ninikoshka -> admin')
    else:
        print('მომხმარებელი ვერ ვიპოვე! იქნებ უკვე შეცვლილია?')
