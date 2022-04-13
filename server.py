import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, abort, url_for
import flask_login

app = Flask(__name__, instance_relative_config=True)
app.secret_key = 'secret'

DB_USER = 'lrm2188'
DB_PASS = '3846'
DB_SERVER = 'w4111.cisxo09blonu.us-east-1.rds.amazonaws.com'
DB_URI = f'postgresql://{DB_USER}:{DB_PASS}@{DB_SERVER}/proj1part2'
engine = create_engine(DB_URI)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


class User(flask_login.UserMixin):

    def __init__(self, uid, nickname: str, email: str):
        self.uid = uid
        self.nickname = nickname
        self.email = email

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id


@login_manager.user_loader
def user_loader(email):
    info = g.conn.execute(f"""
    SELECT uid, nickname, email
    FROM Users
    WHERE email='{email}'
    """).fetchone()
    user = User(info[0], info[1], info[2])
    user.id = email
    return user


@app.before_request
def before_request():
    """
  This function is run at the beginning of every web request
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request
  The variable g is globally accessible
  """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback
        traceback.print_exc()
        g.conn = None


@app.teardown_request
def teardown_request(exception):
    """
  At the end of the web request, this makes sure to close the database connection.
  If you don't the database could run out of memory!
  """
    try:
        g.conn.close()
    except Exception as e:
        pass


@app.route('/')
def start():
    return render_template('index.html')


@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/login.html', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_email = request.form.get('email')
        entered_password = request.form.get('password')

        check = g.conn.execute(f"""
        SELECT COUNT(email), nickname as cnt 
        FROM Users 
        WHERE email = '{entered_email}' AND password = '{entered_password}'
        GROUP BY nickname
        """).fetchone()

        if check[0] != 1:
            return redirect(url_for('login'))
        name = check[1]

        info = g.conn.execute(f"""
            SELECT uid, nickname, email
            FROM Users
            WHERE email='{entered_email}'
            """).fetchone()
        user = User(info[0], info[1], info[2])
        user.id = entered_email
        flask_login.login_user(user)
        user.is_authenticated()
        return redirect(url_for('home'))

    return render_template('login.html')


@app.route('/register.html', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        entered_name = request.form.get('name')
        entered_email = request.form.get('email')
        entered_password = request.form.get('password')

        matching_email = g.conn.execute(f"""
        SELECT email 
        FROM Users 
        WHERE email = '{entered_email}'
        LIMIT 1"""
                                        ).fetchone()
        if matching_email is not None:
            return redirect(url_for('index'))

        uid = g.conn.execute("""SELECT MAX(uid) as max FROM Users LIMIT 1""").fetchone()[0] + 1
        engine.execute(f"""
        INSERT INTO Users(uid, nickname, email, password) 
        VALUES ({uid},'{entered_name}','{entered_email}','{entered_password}')"""
                       )
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/contacts.html', methods=['GET', ])
@flask_login.login_required
def contacts():
    uid = get_uid()
    contlist_id = g.conn.execute(f"""
    SELECT contlist_id
    FROM manage2_contlists
    WHERE manage2_contlists.uid = {uid}
    """).fetchone()

    if contlist_id is None:
        contlist_id = g.conn.execute("""SELECT MAX(contlist_id) FROM manage2_contlists""").fetchone()[0] + 1
        engine.execute(f"""
        INSERT INTO manage2_contlists VALUES ({uid}, {contlist_id})
        """)
    else:
        contlist_id = contlist_id[0]

    cont_ids = g.conn.execute(f"""
    SELECT cont_id
    FROM contain_contacts
    WHERE uid = {uid} AND contlist_id={contlist_id}
    """).fetchall()
    contacts = []
    for cid in cont_ids:
        contacts.append(g.conn.execute(f"""
        SELECT nickname, email
        FROM Users
        WHERE uid = {cid[0]}
        """).fetchone())

    return render_template('contacts.html', contacts=contacts)


@app.route('/chatlist.html', methods=['GET', ])
@flask_login.login_required
def chatlist():
    return render_template(chatlist)


@app.route('/home.html', methods=['GET', ])
@flask_login.login_required
def home():
    return render_template('home.html', name=flask_login.current_user.nickname)


@app.route('/addcontact.html', methods=['GET', 'POST'])
@flask_login.login_required
def addcontact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        email_exists = g.conn.execute(f"""
        SELECT COUNT(email), uid
        FROM Users
        WHERE email = '{email}'
        GROUP BY uid
        """).fetchone()
        if email_exists is None:
            return redirect(url_for('addcontactfail'))
        cont_uid = email_exists[1]

        engine.execute(f"""
        INSERT INTO contain_contacts(uid, contlist_id, cont_id) VALUES ({get_uid()}, {get_contlist_id()}, {cont_uid})
        ON CONFLICT DO NOTHING
        """)
        return redirect(url_for('addcontactsuccess'))
    return render_template('addcontact.html')


@app.route('/addcontactsuccess.html', methods=['GET', ])
@flask_login.login_required
def addcontactsuccess():
    return render_template('addcontactsuccess.html')


@app.route('/addcontactfail.html', methods=['GET', ])
@flask_login.login_required
def addcontactfail():
    return render_template('addcontactfail.html')


@app.route('/deletecontact.html', methods=['GET', 'POST'])
@flask_login.login_required
def deletecontact():
    if request.method == 'POST':
        return render_template('deletecontact.html')


def get_uid():
    return g.conn.execute(f"""
    SELECT uid
    FROM Users
    WHERE email='{flask_login.current_user.id}'
    """).fetchone()[0]


def get_contlist_id():
    return g.conn.execute(f"""
    SELECT contlist_id
    FROM manage2_contlists
    WHERE uid='{get_uid()}'
    """).fetchone()[0]


if __name__ == "__main__":
    app.run()
