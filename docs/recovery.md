# Lumira Recovery Guide

## Project Information

Project Name: Lumira

GitHub Repository:
https://github.com/pdhariharasudhan-hash/Lumira

Local Project Location:
C:\Users\Administrator\Desktop\personal_ai_core

Backup Locations:
GitHub Private Repository
G:\Personal-ai
G:\Lumira_Backups

---

## Restore From GitHub

Install Git.

Clone the repository:

git clone https://github.com/pdhariharasudhan-hash/Lumira.git

Open project:

cd Lumira

Create virtual environment:

python -m venv .venv

Activate virtual environment:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Run application:

python ai.py

---

## Git Workflow

Save changes:

git add .
git commit -m "description"

Upload changes:

git push

Download latest changes:

git pull

Check status:

git status

---

## Critical Data

Important folders:

app/
memory/
artifacts/
generated/
tests/
docs/

Important files:

requirements.txt
ai.py
main.py
README.md
app.db

---

## Emergency Checklist

If project is lost:

1. Install Python
2. Install Git
3. Clone repository
4. Create virtual environment
5. Install requirements
6. Verify memory folder exists
7. Run application

---

Last Updated:
2026-06-12
