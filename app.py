from typing import Annotated
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import uvicorn, yaml, json
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

def load_topics():
    with open("./data/topics.json") as f:
        return json.load(f)

question_data = load_question_data()
topics_data = load_topics()

# Organize questions by topic for easier access
questions_by_topic = defaultdict(list)
for q in question_data:
    # Assuming each question has a "topic" field
    if "topic" in q:
        questions_by_topic[q["topic"]].append(q)

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "topic_selection.html",
        {"topics": topics_data, "scores": user_scores}
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
        "total_questions": len(selected_questions)
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
            "question": question,
            "session_id": session_id,
            "current_q": current_q + 1,
            "total_questions": session["total_questions"],
            "score": session["score"]
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
            user_answer = {
                "index": user_ans["answer_index"],
                "text": q["shuffled_answers"][user_ans["answer_index"]],
                "is_correct": user_ans["is_correct"]
            }
        
        detailed_results.append({
            "question": q["question_name"],
            "description": q["question_description"],
            "correct_answer": q["shuffled_answers"][q["correct_index"]],
            "user_answer": user_answer,
            "hint": q.get("question_hint", "")
        })
    
    return templates.TemplateResponse(
        request,
        "question_answer.html",
        {
            "session": session,
            "detailed_results": detailed_results,
            "percentage": (session["score"] / session["total_questions"] * 100) if session["total_questions"] > 0 else 0
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
