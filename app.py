from flask import Flask, render_template, request, redirect
import sqlite3
import os
import json
from utils import summarize_bill
from reportlab.pdfgen import canvas
from flask import send_file
import io


app = Flask(__name__)
DB_PATH = "db.sqlite3"
VOTE_FILE = "votes.json"

# Initialize database
def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                neighborhood TEXT,
                message TEXT,
                response TEXT,
                location TEXT
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                neighborhood TEXT,
                alert TEXT
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                option1 TEXT,
                option2 TEXT,
                option3 TEXT
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER,
                option_chosen TEXT
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS impact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                neighborhood TEXT,
                impact_level INTEGER  -- from 0 (low) to 10 (high)
            );
        ''')
  

        conn.close()

# Routes
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    neighborhood = request.form['neighborhood']
    message = request.form['message']
    location = request.form.get('location', '')

    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO feedback (name, neighborhood, message, location) VALUES (?, ?, ?, ?)",
                 (name, neighborhood, message, location))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    neighborhood_filter = None
    if request.method == 'POST':
        neighborhood_filter = request.form.get('neighborhood')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if neighborhood_filter:
        cursor.execute("SELECT * FROM feedback WHERE neighborhood = ? ORDER BY id DESC", (neighborhood_filter,))
    else:
        cursor.execute("SELECT * FROM feedback ORDER BY id DESC")

    feedbacks = cursor.fetchall()
    conn.close()

    return render_template("dashboard.html", feedbacks=feedbacks, selected=neighborhood_filter)

@app.route('/respond/<int:feedback_id>', methods=['POST'])
def respond(feedback_id):
    response = request.form['response']
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE feedback SET response = ? WHERE id = ?", (response, feedback_id))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

@app.route('/summarize', methods=['GET', 'POST'])
def summarize():
    summary = ""
    if request.method == 'POST':
        bill_text = request.form['bill_text']
        summary = summarize_bill(bill_text)
    return render_template("summarize.html", summary=summary)

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    results = None
    if request.method == 'POST':
        user_vote = request.form['vote']
        votes = load_votes()
        if user_vote in votes:
            votes[user_vote] += 1
        save_votes(votes)
        total = sum(votes.values())
        results = {k: round((v / total) * 100, 1) if total > 0 else 0 for k, v in votes.items()}
    return render_template('vote.html', results=results)

def load_votes():
    try:
        with open(VOTE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"for": 0, "against": 0, "neutral": 0}

def save_votes(votes):
    with open(VOTE_FILE, "w") as f:
        json.dump(votes, f)

@app.route('/new-alert', methods=['GET', 'POST'])
def new_alert():
    if request.method == 'POST':
        neighborhood = request.form['neighborhood']
        alert = request.form['alert']
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO alerts (neighborhood, alert) VALUES (?, ?)", (neighborhood, alert))
        conn.commit()
        conn.close()
        return redirect('/alerts')
    return render_template("new_alert.html")

@app.route('/alerts')
def view_alerts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT neighborhood, alert FROM alerts ORDER BY id DESC")
    alerts = cursor.fetchall()
    conn.close()
    return render_template("alerts.html", alerts=alerts)

@app.route('/create-poll', methods=['GET', 'POST'])
def create_poll():
    if request.method == 'POST':
        question = request.form['question']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO polls (question, option1, option2, option3) VALUES (?, ?, ?, ?)",
                     (question, option1, option2, option3))
        conn.commit()
        conn.close()
        return redirect('/poll')
    return render_template("create_poll.html")

@app.route('/poll', methods=['GET', 'POST'])
def poll():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM polls ORDER BY id DESC LIMIT 1")
    poll = cursor.fetchone()

    if request.method == 'POST':
        selected = request.form['option']
        cursor.execute("INSERT INTO votes (poll_id, option_chosen) VALUES (?, ?)", (poll[0], selected))
        conn.commit()
        conn.close()
        return redirect('/poll-results')

    conn.close()
    return render_template("poll.html", poll=poll)

@app.route('/poll-results')
def poll_results():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get the latest poll
    cursor.execute("SELECT * FROM polls ORDER BY id DESC LIMIT 1")
    poll = cursor.fetchone()
    
    # Get vote counts per option
    cursor.execute("SELECT option_chosen, COUNT(*) FROM votes WHERE poll_id = ? GROUP BY option_chosen", (poll[0],))
    vote_counts = cursor.fetchall()
    
    # ✅ Calculate total number of votes
    total_votes = sum([count for _, count in vote_counts])

    conn.close()
    return render_template("poll_results.html", poll=poll, vote_counts=vote_counts, total_votes=total_votes)

@app.route('/impact', methods=['GET', 'POST'])
def impact():
    if request.method == 'POST':
        neighborhood = request.form['neighborhood']
        impact_level = int(request.form['impact_level'])

        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO impact (neighborhood, impact_level) VALUES (?, ?)", (neighborhood, impact_level))
        conn.commit()
        conn.close()
        return redirect('/impact-view')

    return render_template("impact.html")

@app.route('/impact-view')
def impact_view():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT neighborhood, impact_level FROM impact")
    data = cursor.fetchall()
    conn.close()

    return render_template("impact_view.html", data=data)

@app.route('/export-pdf')
def export_pdf():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback ORDER BY id DESC")
    feedbacks = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    y = 800

    p.setFont("Helvetica", 14)
    p.drawString(200, y, "Feedback Report")
    y -= 40

    p.setFont("Helvetica", 10)
    for fb in feedbacks:
        name, neighborhood, message, response = fb[1], fb[2], fb[3], fb[4]
        p.drawString(50, y, f"Name: {name} | Neighborhood: {neighborhood}")
        y -= 15
        p.drawString(50, y, f"Message: {message}")
        y -= 15
        if response:
            p.drawString(50, y, f"Response: {response}")
            y -= 15
        p.drawString(50, y, "-" * 80)
        y -= 25
        if y < 100:
            p.showPage()
            y = 800

    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="feedback_report.pdf", mimetype='application/pdf')


@app.route('/map')
def show_map():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, message, location FROM feedback WHERE location IS NOT NULL")
    feedbacks = [{"name": row[0], "message": row[1], "location": row[2]} for row in cursor.fetchall()]
    conn.close()
    return render_template("map.html", feedbacks=feedbacks)

@app.route('/feedback')
def feedback():
    return render_template("feedback.html")


# Run the app
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
