from typing import Annotated
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import uvicorn, yaml, json

with open("./config.yml") as f:
    config = yaml.safe_load(f)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def load_question_data():
    with open("./data/full_questions.json") as f:
        return json.load(f)

question_data = load_question_data()

@app.get("/"):
def _index(request: Request):
    templates.TemplateResponse(
        request,
        "topic_selection.html"
    )

def main():
    uvicorn.run(
        app,
        **config.get("uvicorn")
    )

if __name__ == "__main__":
    main()

