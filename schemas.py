from pydantic import BaseModel, Field
from typing import List

class QuestionAnswers(BaseModel):
    question_name: str = Field(description="Name of the question")
    question_description: str = Field(description="Short description and usage example for the question.")
    question_answers: List[str] = Field(description="List of answer options for the question, should include naive, naive improved and optimal responses as options (unlabeled). These are short descriptions [30 to 50 words] of how the algorithm will work.")
    question_answer_correct_index: int = Field(description="The correct (most optimised) answer index for self.question_answers")
    question_hint: str = Field(description="Small hint for the question")
