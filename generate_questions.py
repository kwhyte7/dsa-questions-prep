# we'll use AI to generate the answers - probably going to use deepseek.
import json, os, yaml, asyncio, aiofiles
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from dotenv import load_dotenv
from time import time
from schemas import QuestionAnswers

load_dotenv()

# load topics
def load_topics():
    with open("./data/topics.json") as f:
        topics = json.load(f)

    return topics

# [[topic, [*questions]]]
def load_config():
    with open("./config.yml") as f:
        return yaml.safe_load(f)

config = load_config()

def init_questions_agent():
    model = init_chat_model(
        **config.get("model")
    )

    agent = create_agent(
        model=model,
        system_prompt="You are a DSA question writer. You write the questions and answers for students learning DSA",
        response_format=QuestionAnswers,
    )

    return agent

def load_topics():
    with open("./data/topics.json", "r") as f:
        return json.load(f)

def generate_all_topics(agent, topics:list):
    completed_dataset = []
    for topic in topics: 
        completed_dataset.append(generate_questions_for_topic(topic))

    with open("./data/full_questions.json", "w") as f:
        json.dump(completed_dataset, f)

    return completed_dataset

async def async_generate_all_topics(agent, topics:list):
    completed_dataset = []
    
    # Create tasks for all topics
    tasks = []
    for topic in topics:
        task = asyncio.create_task(generate_questions_for_topic(agent, topic))
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in results:
        if isinstance(result, Exception):
            print(f"Error processing topic: {result}")
        else:
            completed_dataset.append(result)
    
    # Async file write
    async with aiofiles.open("./data/full_questions.json", "w") as f:
        await f.write(json.dumps(completed_dataset))
    
    return completed_dataset

def generate_questions_for_topic(agent, topic_list:list):
    topic, question_names = topic

    completed_questions = []

    for question_name in question_names:
        completed_questions.append(
            generate_question_answers(agent, question_name)
        )

    if config.get("generate_questions_for_topic", {"save_intermittently" : False}).get("save_intermittently""):
        with open(f"./data/{str(time()).replace('.', '_')}.json", "w") as f:
            json.dump([topic, completed_questions], f)

    return [topic, completed_questions]

def generate_question_answers(agent, question: str) -> list:
    try:
        response = agent.invoke({"messages" : [
            {"role" : "user", "content" : f"write the answers for the question {question}."}
        ]})

        if "structured_response" in response.keys():
            # return as dictionary, questionsanswers schema... (it should be json serialisable)
            return response["structured_response"].model_dump()
    except Exception as e:
        print(f"{e}\nThere was an error in the response for question {question}, trying again.")
        return generate_question_answers(agent, question)

def main():
    agent = init_questions_agent()
    topics = load_topics()
    generate_all_topics(agent, topics)

async def async_main():
    agent = init_questions_agent()
    topics = load_topics()
    return await async_generate_all_topics(agent, topics)

def run_async():
    return asyncio.run(async_main())

if __name__ == "__main__":
    run_async()
