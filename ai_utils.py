import google.generativeai as genai
import os
import json
import PyPDF2

# Configure Gemini with a hypothetical valid API key setup from environment
# In a real setup, we would read this from os.environ.get("GEMINI_API_KEY")
import dotenv
dotenv.load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "
"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def parse_questions_with_ai(text):
    if not API_KEY:
        # Dummy fallback if no API key is provided
        return [
            {
                "question": "Sample Question 1 extracted from PDF",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "marks": 1
            },
            {
                "question": "Sample Question 2 extracted from PDF",
                "options": ["True", "False"],
                "correct_answer": "True",
                "marks": 1
            }
        ]
        
    prompt_instruction = """
    You are an expert exam parser. I will provide you with the raw text extracted from a question paper PDF.
    Your task is to extract all the multiple choice questions and return them as a valid JSON array.
    Each object in the array should have the following exact schema:
    {
        "question": "The question text",
        "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "correct_answer": "The exact string of the correct option. Guess if not provided in the text.",
        "marks": 1
    }
    """

    prompt = f"""
    {prompt_instruction}
    
    Return ONLY valid JSON and nothing else. No markdown blocks.

    Raw Text:
    {text}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        # Clean potential markdown
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(res_text)
        return data
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return []

def chat_with_agent(message, history=None):
    if history is None:
        history = []
        
    if not API_KEY:
        return "I am a dummy AI assistant since no API key is provided. How can I help you with Examify today?"
    
    prompt_instruction = """
    You are an enthusiastic and helpful AI assistant for Examify, a platform where users can upload PDFs to automatically generate multiple-choice exams.
    Your job is to help users navigate the site, understand its capabilities (such as uploading an exam paper, taking tests, viewing dashboards and results), and answer questions about the platform in a friendly and professional manner.
    Keep your answers concise and highly readable.
    """
    
    # Simple formatting of recent conversation to provide context
    formatted_history = ""
    for item in history[-6:]: # Keep last few messages for quick context
        role = "User" if item.get('role') == 'user' else "Agent"
        formatted_history += f"{role}: {item.get('text', '')}
"
    
    prompt = f"{prompt_instruction}\n\nRecent Conversation:\n{formatted_history}\nUser: {message}\nAgent:"
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI Chat Error: {e}")
        return "I'm sorry, I'm having trouble retrieving a response right now."
