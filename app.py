from typing import Annotated
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import uvicorn, yaml, json, copy
import random
from collections import defaultdict

with open("./config.yml") as f:
    config = yaml.safe_load(f)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# In-memory storage for quiz sessions
quiz_sessions = {}
user_scores = defaultdict(lambda: {"total_correct": 0, "total_answered": 0})

def load_question_data():
    with open("./data/full_questions.json") as f:
        return json.load(f)

question_data = load_question_data()
# Get the list of unique topics
questions_by_topic = {
    k:v for k,v in question_data
}

topics_data = sorted(questions_by_topic.keys())

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "topic_selection.html",
        {"topics": topics_data, "scores": user_scores, "questions_by_topic": questions_by_topic}
    )

@app.post("/start_quiz")
def start_quiz(request: Request, topic: str = Form(...), num_questions: int = Form(5)):
    # Create a new quiz session
    session_id = str(random.randint(100000, 999999))
    
    # Get questions for the selected topic
    topic_questions = questions_by_topic.get(topic, [])
    
    # Select random questions if we have enough
    if len(topic_questions) > num_questions:
        selected_questions = random.sample(topic_questions, num_questions)
    else:
        selected_questions = topic_questions
    
    # Deep copy to avoid modifying the original data
    selected_questions = copy.deepcopy(selected_questions)
    
    # Shuffle answer order for each question
    for q in selected_questions:
        answers = q.get("question_answers", [])
        correct_idx = q.get("question_answer_correct_index", 0)
        
        # Store original correct index before shuffling
        q["original_correct_index"] = correct_idx
        
        # Create pairs of (answer, is_correct)
        answer_pairs = list(enumerate(answers))
        random.shuffle(answer_pairs)
        
        # Find new position of correct answer
        new_answers = []
        for i, (orig_idx, answer) in enumerate(answer_pairs):
            new_answers.append(answer)
            if orig_idx == correct_idx:
                q["correct_index"] = i
        
        q["shuffled_answers"] = new_answers
    
    # Store session
    quiz_sessions[session_id] = {
        "topic": topic,
        "questions": selected_questions,
        "current_question": 0,
        "score": 0,
        "user_answers": [],
        "total_questions": len(selected_questions),
        "num_questions": num_questions
    }
    
    response = RedirectResponse(f"/question/{session_id}", status_code=303)
    response.set_cookie(key="quiz_session", value=session_id)
    return response

@app.get("/question/{session_id}")
def show_question(request: Request, session_id: str):
    if session_id not in quiz_sessions:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    session = quiz_sessions[session_id]
    current_q = session["current_question"]
    
    if current_q >= len(session["questions"]):
        return RedirectResponse(f"/results/{session_id}", status_code=303)
    
    question = session["questions"][current_q]
    
    return templates.TemplateResponse(
        request,
        "question.html",
        {
            "request": request,
            "question": question,
            "session_id": session_id,
            "current_q": current_q + 1,
            "total_questions": session["total_questions"],
            "score": session["score"],
            "scores": user_scores
        }
    )

@app.post("/answer/{session_id}")
def submit_answer(request: Request, session_id: str, answer_index: int = Form(...)):
    if session_id not in quiz_sessions:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    session = quiz_sessions[session_id]
    current_q = session["current_question"]
    
    if current_q >= len(session["questions"]):
        return RedirectResponse(f"/results/{session_id}", status_code=303)
    
    question = session["questions"][current_q]
    
    # Validate answer_index is within bounds
    if not (0 <= answer_index < len(question.get("shuffled_answers", []))):
        # If out of bounds, treat as incorrect and don't crash
        is_correct = False
    else:
        is_correct = (answer_index == question.get("correct_index", -1))
    
    # Update score
    if is_correct:
        session["score"] += 1
    
    # Store user's answer
    session["user_answers"].append({
        "question_index": current_q,
        "answer_index": answer_index,
        "is_correct": is_correct
    })
    
    # Move to next question
    session["current_question"] += 1
    
    # Update overall user scores (simplified - in real app would use user auth)
    user_ip = request.client.host
    user_scores[user_ip]["total_answered"] += 1
    if is_correct:
        user_scores[user_ip]["total_correct"] += 1
    
    # Check if quiz is complete
    if session["current_question"] >= len(session["questions"]):
        return RedirectResponse(f"/results/{session_id}", status_code=303)
    
    return RedirectResponse(f"/question/{session_id}", status_code=303)

@app.get("/results/{session_id}")
def show_results(request: Request, session_id: str):
    if session_id not in quiz_sessions:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    session = quiz_sessions[session_id]
    
    # Prepare detailed results
    detailed_results = []
    for i, q in enumerate(session["questions"]):
        user_answer = None
        if i < len(session["user_answers"]):
            user_ans = session["user_answers"][i]
            # Safely get the user's answer text
            answer_index = user_ans["answer_index"]
            shuffled_answers = q.get("shuffled_answers", [])
            if 0 <= answer_index < len(shuffled_answers):
                answer_text = shuffled_answers[answer_index]
            else:
                answer_text = "Invalid answer index"
            
            user_answer = {
                "index": answer_index,
                "text": answer_text,
                "is_correct": user_ans["is_correct"]
            }
        
        # Safely get the correct answer text
        correct_index = q.get("correct_index", 0)
        shuffled_answers = q.get("shuffled_answers", [])
        if 0 <= correct_index < len(shuffled_answers):
            correct_answer_text = shuffled_answers[correct_index]
        else:
            correct_answer_text = "Invalid correct index"
        
        detailed_results.append({
            "question": q["question_name"],
            "description": q["question_description"],
            "correct_answer": correct_answer_text,
            "user_answer": user_answer,
            "hint": q.get("question_hint", "")
        })
    
    return templates.TemplateResponse(
        request,
        "question_answer.html",
        {
            "request": request,
            "session": session,
            "detailed_results": detailed_results,
            "percentage": (session["score"] / session["total_questions"] * 100) if session["total_questions"] > 0 else 0,
            "scores": user_scores,
            "num_questions": session.get("num_questions", 10)
        }
    )

@app.get("/new_quiz")
def new_quiz(request: Request):
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(key="quiz_session")
    return response

def main():
    uvicorn.run(
        app,
        **config.get("uvicorn")
    )

if __name__ == "__main__":
    main()
