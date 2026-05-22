# 🧠 Setup virtual environment
venv:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

# 🔧 Internal run target
run:
	. venv/bin/activate && python3 main.py

# 🧹 Clean up venv
clean:
	rm -rf venv

# 🔍 Check Python version
version:
	python3 --version

# 📦 Freeze dependencies
freeze:
	. venv/bin/activate && pip freeze > requirements.txt

