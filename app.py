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
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

# Create Database tables (simple fallback, in production use Flask-Migrate)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if action == 'register':
            if User.query.filter_by(email=email).first():
                flash('Email already registered.')
                return redirect(url_for('auth'))
            hashed_pw = generate_password_hash(password, method='scrypt')
            new_user = User(name=name, email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('auth'))
            
        elif action == 'login':
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password, password):
                flash('Invalid email or password.')
                return redirect(url_for('auth'))
            session['user_id'] = user.id
            session['user_name'] = user.name
            return redirect(url_for('dashboard'))
            
    return render_template('auth.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    exams = Exam.query.filter_by(created_by=session['user_id']).all()
    results = Result.query.filter_by(user_id=session['user_id']).all()
    return render_template('dashboard.html', exams=exams, results=results)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        duration = request.form.get('duration', 60)
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
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(pdf_path)
            
            # Extract questions using Gemini API
            pdf_text = extract_text_from_pdf(pdf_path)
            if not pdf_text.strip():
                flash('Could not read PDF contents.')
                return redirect(request.url)
                
            questions_data = parse_questions_with_ai(pdf_text, exam_type)
            
            if questions_data:
                # Create Exam
                new_exam = Exam(
                    title=title,
                    duration=float(duration),
                    exam_type=exam_type,
                    created_by=session['user_id']
                )
                db.session.add(new_exam)
                db.session.commit()
                
                # Create Questions
                for q_data in questions_data:
                    q = Question(
                        exam_id=new_exam.id,
                        question=q_data.get('question'),
                        options=q_data.get('options', []),
                        correct_answer=q_data.get('correct_answer'),
                        marks=q_data.get('marks', 1)
                    )
                    db.session.add(q)
                db.session.commit()
                
                flash(f'Exam "{title}" successfully generated with {len(questions_data)} questions!')
                return redirect(url_for('dashboard'))
            else:
                flash('Failed to extract questions from the PDF. Please try a clearer document.')
                return redirect(request.url)
                
    return render_template('upload.html')

@app.route('/exam/<int:exam_id>', methods=['GET', 'POST'])
def take_exam(exam_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
        
    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).all()
    
    if request.method == 'POST':
        user_id = session['user_id']
        score = 0
        total_marks = 0
        answers = {}
        
        for q in questions:
            user_ans = request.form.get(f'question_{q.id}', '').strip()
            answers[q.id] = user_ans
            total_marks += q.marks
            
            # Simple exact match grading (case insensitive)
            if user_ans.lower() == q.correct_answer.strip().lower():
                score += q.marks
                
        # Save Result
        result = Result(
            user_id=user_id,
            exam_id=exam.id,
            score=score,
            total_marks=total_marks,
            answers=answers
        )
        db.session.add(result)
        db.session.commit()
        
        return redirect(url_for('result', result_id=result.id))
        
    return render_template('exam.html', exam=exam, questions=questions)

@app.route('/result/<int:result_id>')
def result(result_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    result = Result.query.get_or_404(result_id)
    exam = Exam.query.get(result.exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).all()
    
    # Calculate detailed stats
    correct = 0
    incorrect = 0
    unanswered = 0
    
    for q in questions:
        user_ans = result.answers.get(str(q.id), '').strip()
        if not user_ans:
            unanswered += 1
        elif user_ans.lower() == q.correct_answer.strip().lower():
            correct += 1
        else:
            incorrect += 1
            
    return render_template(
        'result.html',
        result=result,
        exam=exam,
        questions=questions,
        correct=correct,
        incorrect=incorrect,
        unanswered=unanswered
    )

@app.route('/analysis/<int:result_id>')
def analysis(result_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    result = Result.query.get_or_404(result_id)
    exam = Exam.query.get(result.exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).all()
    return render_template('analysis.html', result=result, exam=exam, questions=questions)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    message = data.get('message')
    history = data.get('history', [])
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
        
    ai_response = chat_with_agent(message, history)
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    app.run(debug=True)
