from app import app
from models import db, User, Exam, Question, Result
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if user exists
    user = User.query.filter_by(email="test@test.com").first()
    if not user:
        user = User(name="Test User", email="test@test.com", password=generate_password_hash("password", method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
    
    # Check if exam exists
    exam = Exam.query.filter_by(title="Sample AI Mock Test").first()
    if not exam:
        exam = Exam(title="Sample AI Mock Test", duration=60, exam_type="general", created_by=user.id)
        db.session.add(exam)
        db.session.commit()
    
    # Check if result exists
    result = Result.query.filter_by(user_id=user.id, exam_id=exam.id).first()
    if not result:
        result = Result(user_id=user.id, exam_id=exam.id, obtained_score=75, total_score=100, correct_answers=15, wrong_answers=5, percentage=75.0, answers={"1":"A"})
        db.session.add(result)
        db.session.commit()
    
    print("Database seeded with test@test.com / password and dummy exam/result.")
