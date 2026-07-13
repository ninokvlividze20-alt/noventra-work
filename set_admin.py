from app import app, db, User

with app.app_context():
    # ვეძებთ მომხმარებელს სახელით 'admin'
    username_to_set = 'admin'
    u = User.query.filter_by(username=username_to_set).first()
    
    if u:
        u.is_admin = True
        db.session.commit()
        print(f'წარმატებით! {username_to_set} ახლა ადმინია.')
    else:
        print(f'მომხმარებელი {username_to_set} ვერ ვიპოვე. დარწმუნდი რომ უკვე დარეგისტრირებული გაქვს!')
