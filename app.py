import os
import secrets
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(storage=None):
    app = Flask(__name__)
    root = Path(storage or app.instance_path)
    root.mkdir(parents=True, exist_ok=True)
    key = root / 'session.key'
    try:
        with key.open('xb') as stream:
            stream.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    app.config.update(SECRET_KEY=key.read_bytes(), SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=16384)
    schema = """
    CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE,password TEXT);
    CREATE TABLE IF NOT EXISTS work(id INTEGER PRIMARY KEY,student INTEGER NOT NULL REFERENCES students(id),course INTEGER NOT NULL,title TEXT NOT NULL,due TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0);
    """
    with sqlite3.connect(root / 'campus.db') as conn:
        conn.executescript(schema)
    courses = [('DS 101', 'Design Studio', 'Studio B', '09:00', '09:50', (0, 2, 4)),
               ('CS 204', 'Creative Coding', 'Lab 04', '11:00', '12:20', (1, 3)),
               ('AH 120', 'Visual Culture', 'Hall A', '14:00', '14:50', (0, 1, 3))]

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(root / 'campus.db')
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close(_error):
        if 'db' in g:
            g.db.close()

    def seed(name, email=None, password=None):
        with db():
            uid = db().execute('INSERT INTO students(name,email,password) VALUES(?,?,?)',
                               (name,email,password)).lastrowid
            for course, title, days, done in [(0,'Develop a modular poster',2,0),(1,'Build a generative sketch',4,0),(2,'Gallery reflection',6,0),(0,'Collect visual references',0,1)]:
                db().execute('INSERT INTO work(student,course,title,due,done) VALUES(?,?,?,?,?)',
                             (uid,course,title,(date.today()+timedelta(days=days)).isoformat(),done))
        return uid

    @app.before_request
    def protect():
        if request.method == 'POST' and not secrets.compare_digest(session.get('token','missing'),request.form.get('token','')):
            abort(403)
        session.setdefault('token', secrets.token_hex(24))

    def student():
        row = db().execute('SELECT * FROM students WHERE id=?',(session.get('uid'),)).fetchone()
        if row is None:
            session['uid'] = seed('Alex')
            return student()
        return row

    @app.route('/account/<mode>', methods=['GET','POST'])
    def account(mode):
        if mode not in ('login','register'):
            abort(404)
        error = None
        if request.method == 'POST':
            email = request.form.get('email','').strip().lower()
            password = request.form.get('password','')
            if mode == 'register':
                name = request.form.get('name','').strip()
                if not name or len(name)>60 or '@' not in email or len(email)>254 or len(password)<8:
                    error = 'Enter a name, email and a password of at least eight characters.'
                else:
                    try:
                        user = student()
                        if user['email'] is None:
                            with db():
                                db().execute('UPDATE students SET name=?,email=?,password=? WHERE id=?',(name,email,generate_password_hash(password),user['id']))
                            uid = user['id']
                        else:
                            uid = seed(name,email,generate_password_hash(password))
                    except sqlite3.IntegrityError:
                        error = 'This email is already registered.'
            else:
                user = db().execute('SELECT * FROM students WHERE email=?',(email,)).fetchone()
                if user and check_password_hash(user['password'],password):
                    uid = user['id']
                else:
                    error = 'Email or password is incorrect.'
            if not error:
                session.clear()
                session['uid'] = uid
                return redirect('/')
        return render_template('account.html',mode=mode,error=error)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect('/account/login')

    @app.get('/')
    def dashboard():
        user = student()
        today = date.today()
        rows = db().execute('SELECT * FROM work WHERE student=? ORDER BY done,due,id',(user['id'],)).fetchall()
        page = request.args.get('view','Overview')
        if page not in ('Overview','Assignments','Timetable'):
            abort(404)
        return render_template('home.html', user=user, rows=rows, courses=courses, today=today,
                               week=[today+timedelta(days=n) for n in range(7)],page=page,
                               pending=sum(1 for r in rows if not r['done']))

    @app.post('/assignments')
    def add():
        title = request.form.get('title','').strip()
        try:
            course = int(request.form['course'])
            due = date.fromisoformat(request.form['due']).isoformat()
        except (KeyError, ValueError):
            abort(400)
        if not title or len(title)>120 or course not in range(len(courses)):
            abort(400)
        uid = student()['id']
        with db():
            db().execute('INSERT INTO work(student,course,title,due) VALUES(?,?,?,?)',(uid,course,title,due))
        return redirect(url_for('dashboard',view='Assignments'))

    @app.post('/assignments/<int:item>/status')
    def status(item):
        uid = student()['id']
        value = request.form.get('done')
        if value not in ('0','1'):
            abort(400)
        with db():
            if not db().execute('UPDATE work SET done=? WHERE id=? AND student=?',(value,item,uid)).rowcount:
                abort(404)
        return redirect(url_for('dashboard',view='Assignments'))

    return app
