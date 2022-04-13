from flask import Blueprint, render_template, request
from __init__ import engine
auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_email = request.form.get('email')
        entered_password = request.form.get('password')

        check = engine.execute(f"""
        SELECT COUNT(email) as cnt 
        FROM Users 
        WHERE email = {entered_email} AND password = {entered_password}
        """)

        if check['cnt'][0] != 1:
            return render_template('login.html')
        return render_template('index.html')

    return render_template('login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        entered_email = request.form.get('email')
        entered_password = request.form.get('password')
        matching_email = engine.execute(f"SELECT email FROM Users WHERE email = f{entered_email}")
        for email in matching_email['email']:
            if email == entered_email:
                return render_template('register.html')

        engine.execute(f"INSERT INTO Users(email, password) VALUES ({entered_email},{entered_password})")
        return render_template('index.html')
    return render_template('register.html')
