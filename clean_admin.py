from app import app, db, User

with app.app_context():
    # 1. ninikoshka-ს წაშლა
    old_admin = User.query.filter_by(username='ninikoshka').first()
    if old_admin:
        db.session.delete(old_admin)
        print("ninikoshka წაიშალა!")
    
    # 2. admin-ის გაადმინება (თუ უკვე დარეგისტრირებული გაქვს)
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        admin_user.is_admin = True
        print("admin ახლა უკვე ადმინია!")
    
    db.session.commit()
    print("ყველაფერი გასწორდა!")
