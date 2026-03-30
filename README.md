# This is a simple website that allows you to study DSA questions.

# How to run

Use `uv` package manager to sync dependencies, use 
```bash 
$ uv sync
```

# If you want to edit or generate new questions

Then, if you want to generate some questions, edit the `./data/topics.json`. You can change it to questions you want the AI to generate.
Run
```bash 
$ uv run generate_questions.py
```
to start generating questions

# Run web server
By default, it runs on host 0.0.0.0, and on port 8090. You can edit the config in `./config.yml`.
Run the webserver by running
```bash
$ uv run app.py
```
