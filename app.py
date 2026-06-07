from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from models import db, User, Exam, Question, Result
from ai_utils import extract_text_from_pdf, parse_questions_with_ai, chat_with_agent

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///examify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

# Initialize DB
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'register':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already exists')
                return redirect(url_for('auth'))
                
            hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(name=name, email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful, please login.')
            return redirect(url_for('auth'))
            
        elif action == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['user_name'] = user.name
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password')
                return redirect(url_for('auth'))
                
    return render_template('auth.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    user_id = session['user_id']
    user = User.query.get(user_id)
    my_exams = Exam.query.filter_by(created_by=user_id).order_by(Exam.created_at.desc()).all()
    my_results = Result.query.filter_by(user_id=user_id).order_by(Result.created_at.desc()).all()
    
    return render_template('dashboard.html', user=user, exams=my_exams, results=my_results)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        exam_type = request.form.get('exam_type', 'general')
        
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
            
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)
            
            # Process PDF
            try:
                text = extract_text_from_pdf(filepath)
                questions_data = parse_questions_with_ai(text, exam_type)
                
                if not questions_data:
                    flash('Failed to extract questions from the PDF. Please try a clearer document.')
                    return redirect(request.url)
                    
                # Calculate duration automatically based on question difficulty
                calculated_duration = 0
                for q_data in questions_data:
                    diff = q_data.get('difficulty', 'medium').lower()
                    if diff == 'easy':
                        calculated_duration += 1
                    elif diff == 'hard':
                        calculated_duration += 3
                    else:
                        calculated_duration += 2
                
                if calculated_duration == 0:
                    calculated_duration = 60 # fallback

                # Create Exam
                new_exam = Exam(
                    title=title,
                    duration=float(calculated_duration),
                    exam_type=exam_type,
                    created_by=session['user_id']
                )
                db.session.add(new_exam)
                db.session.commit()
                
                # Create Questions
                total_marks = 0
                for q_data in questions_data:
                    q = Question(
                        exam_id=new_exam.id,
                        question=q_data.get('question'),
                        options=q_data.get('options', []),
                        correct_answer=q_data.get('correct_answer'),
                        marks=q_data.get('marks', 1),
                        difficulty=q_data.get('difficulty', 'medium').lower(),
                        question_type=q_data.get('question_type', 'mcq').lower()
                    )
                    db.session.add(q)
                
                db.session.commit()
                flash('Exam created successfully!')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                flash(f'An error occurred during processing: {e}')
                return redirect(request.url)
                
    return render_template('upload.html')

@app.route('/exam/<int:exam_id>', methods=['GET', 'POST'])
def take_exam(exam_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).all()
    # Sort questions: mcq first, then numerical
    questions.sort(key=lambda x: 0 if x.question_type == 'mcq' else 1)
    
    if request.method == 'POST':
        user_id = session['user_id']
        answers = {}
        correct = 0
        wrong = 0
        obtained = 0
        total = 0
        
        for q in questions:
            total += q.marks
            ans = request.form.get(f'question_{q.id}')
            answers[str(q.id)] = ans
            if ans == q.correct_answer:
                correct += 1
                obtained += q.marks
            else:
                wrong += 1
                
        percentage = (obtained / total * 100) if total > 0 else 0
        
        result = Result(
            user_id=user_id,
            exam_id=exam.id,
            obtained_score=obtained,
            total_score=total,
            correct_answers=correct,
            wrong_answers=wrong,
            percentage=percentage,
            answers=answers
        )
        db.session.add(result)
        db.session.commit()
        
        return redirect(url_for('view_result', result_id=result.id))
        
    return render_template('exam.html', exam=exam, questions=questions)

@app.route('/result/<int:result_id>')
def view_result(result_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    result = Result.query.get_or_404(result_id)
    if result.user_id != session['user_id']:
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
        
    exam = Exam.query.get(result.exam_id)
    return render_template('result.html', result=result, exam=exam)

@app.route('/analysis/<int:result_id>')
def view_analysis(result_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    result = Result.query.get_or_404(result_id)
    if result.user_id != session['user_id']:
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
        
    exam = Exam.query.get(result.exam_id)
    
    # Generate dummy complex analytical data for the new dashboard
    analysis_data = {
        'percentile': 88,
        'avg_score': int(result.total_score * 0.65),
        'topper_score': int(result.total_score * 0.95),
        'time_taken_mins': 45,
        'accuracy': int(result.percentage),
        'improvement_potential': min(100, int(result.percentage) + 16),
        'weak_areas': [
            {'topic': 'Quadratic Equations', 'accuracy': 40, 'time_multiplier': 2.5, 'reason': 'Mistakes in formula application.'},
            {'topic': 'Kinematics', 'accuracy': 55, 'time_multiplier': 1.8, 'reason': 'Calculation errors under time pressure.'}
        ],
        'mistake_patterns': {
            'Conceptual': 2,
            'Calculation': 4,
            'Silly Mistakes': 3,
            'Time Pressure': 1,
            'Guesswork': 2
        },
        'study_plan': [
            {'day': 'Day 1', 'task': 'Quadratic Equations Revision + 20 Practice Qs'},
            {'day': 'Day 2', 'task': 'Kinematics formula memorization + 10 Timed Qs'}
        ]
    }
    
    return render_template('analysis.html', result=result, exam=exam, analytics=analysis_data)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400
        
    message = data.get('message', '')
    history = data.get('history', [])
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
        
    ai_response = chat_with_agent(message, history)
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    app.run(debug=True)
