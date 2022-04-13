import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, abort, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
import flask_login
from flask_session import Session

app = Flask(__name__, instance_relative_config=True)
#Session(app)
app.secret_key = 'secret'
#app.config['SECRET_TYPE'] = 'secret'
#socketio = SocketIO(app, manage_session=False)

DB_USER = 'jl6017'
DB_PASS = 'jl6017'
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
        import traceback;
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


@app.route('/index.html')
def index():
    return render_template('index.html')


@app.route('/backtoindex.html', methods=['GET', ])
def backtoindex():
    return render_template('backtoindex.html', message=request.args.get('message'))


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

        if check is None:
            message = "Login failed. Invalid credentials."
            return redirect(url_for('login', message=message))
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
            message = "Registration failed. Email already exists."
            return redirect(url_for('backtoindex', message=message))

        uid = g.conn.execute("""SELECT MAX(uid) as max FROM Users LIMIT 1""").fetchone()[0] + 1
        engine.execute(f"""
        INSERT INTO Users(uid, nickname, email, password) 
        VALUES ({uid},'{entered_name}','{entered_email}','{entered_password}')"""
                       )

        message = "Registration successful."
        return redirect(url_for('backtoindex', message=message))

    return render_template('register.html')


@app.route('/contacts.html', methods=['GET', ])
@flask_login.login_required
def contacts():
    uid = get_uid()
    contlist_id = get_contlist_id()

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
            message = 'Email does not exist, or other error occurred.'
            return redirect(url_for('backtohome', message=message))
        cont_uid = email_exists[1]

        engine.execute(f"""
        INSERT INTO contain_contacts(uid, contlist_id, cont_id) VALUES ({get_uid()}, {get_contlist_id()}, {cont_uid})
        ON CONFLICT DO NOTHING
        """)
        message = 'Added contact.'
        return redirect(url_for('backtohome', message=message))
    return render_template('addcontact.html')


@app.route('/backtohome.html', methods=['GET', ])
@flask_login.login_required
def backtohome():
    return render_template('backtohome.html', message=request.args.get('message'))


@app.route('/deletecontact.html', methods=['GET', 'POST'])
@flask_login.login_required
def deletecontact():
    uid = get_uid()
    contlist_id = get_contlist_id()

    if request.method == 'POST':
        email = request.form.get('contact')

        cont_id = g.conn.execute(f"""
        SELECT uid
        FROM Users
        WHERE email = '{email}'
        """).fetchone()

        if cont_id is None:
            return redirect(url_for('backtohome', message="Can't delete a contact that doesn't exist!"))

        engine.execute(f"""
        DELETE FROM contain_contacts
        WHERE uid = {uid} AND contlist_id = {contlist_id} AND cont_id = {cont_id[0]}
        """)

        return redirect(url_for('backtohome', message="Contact deleted."))

    cont_ids = g.conn.execute(f"""
    SELECT cont_id
    FROM contain_contacts
    WHERE uid={uid} AND contlist_id={contlist_id}
    """).fetchall()

    contacts = []
    for cont_id in cont_ids:
        contacts.append(g.conn.execute(f"""
        SELECT nickname, email
        FROM Users
        WHERE uid = {cont_id[0]}
        """).fetchone())

    return render_template('deletecontact.html', contacts=contacts)


@app.route('/namechange.html', methods=['GET', 'POST'])
@flask_login.login_required
def namechange():
    if request.method == 'POST':
        name = request.form.get('name')
        uid = get_uid()

        engine.execute(f"""
        UPDATE Users
        SET nickname = '{name}'
        WHERE uid = {uid}
        """)

        return redirect(url_for('backtohome', message="Name change successful."))
    return render_template('namechange.html')

@app.route('/chatlist.html',methods = ['GET', 'POST'])
@flask_login.login_required
def chatlist():
    chats = get_chats()

    # if request.method == 'POST':
    #     cid = request.form.get('cid')


    return render_template('chatlist.html', chatlist=chats)

@app.route('/addchatroom.html',methods=['GET','POST'])
@flask_login.login_required
def addchatroom():
    if request.method == 'POST':
        uid = get_uid()
        chatlist_id = get_chatlist_id()
        chatname = request.form.get('name')
        cid = g.conn.execute("""SELECT MAX(cid) FROM chatrooms""").fetchone()[0]+1

        engine.execute(f"""
        INSERT INTO chatrooms(cid, name) VALUES ({cid}, '{chatname}')
        """)

        engine.execute(f"""
        INSERT INTO create_room(cid, uid) VALUES ({cid}, {uid})
        ON CONFLICT DO NOTHING
        """)

        engine.execute(f"""
        INSERT INTO contain1(uid, chatlist_id, cid) VALUES ({uid}, {chatlist_id}, {cid})
        ON CONFLICT DO NOTHING
        """)

        return redirect(url_for('backtohome', message="Successfully created chat room."))

    return render_template('addchatroom.html')

@app.route('/deletechatroom.html', methods=['GET', 'POST'])
@flask_login.login_required
def deletechatroom():
    if request.method == 'POST':
        cid = request.form.get('cid')
        uid = get_uid()
        owner_uid = g.conn.execute(f"""
        SELECT uid
        FROM create_room
        WHERE cid={cid}
        """).fetchone()[0]

        if uid == owner_uid:
            engine.execute(f"""
            DELETE FROM contain1
            WHERE cid={cid}
            """)

            engine.execute(f"""
            DELETE FROM create_room
            WHERE cid={cid}
            """)

            engine.execute(f"""
            DELETE FROM join_room
            WHERE cid={cid}
            """)
            engine.execute(f"""
            DELETE FROM chatrooms
            WHERE cid={cid}
            """)

            return redirect(url_for('backtohome',message="Successfully left and deleted chatroom."))
        else:
            engine.execute(f"""
            DELETE FROM contain1
            WHERE cid={cid} AND uid={uid}
            """)
            engine.execute(f"""
            DELETE FROM join_room
            WHERE cid={cid} AND uid={uid}
            """)
            return redirect(url_for('backtohome', message='Successfully left chatroom'))
    chats = get_chats()
    return render_template('deletechatroom.html', chatlist=chats)


def get_uid():
    return g.conn.execute(f"""
    SELECT uid
    FROM Users
    WHERE email='{flask_login.current_user.id}'
    """).fetchone()[0]


def get_contlist_id():
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

    return contlist_id

def get_chatlist_id():
    uid = get_uid()
    chatlist_id =  g.conn.execute(f"""
    SELECT chatlist_id
    FROM manage1_chatlists
    WHERE uid={get_uid()}
    """).fetchone()

    if chatlist_id is None:
        chatlist_id = g.conn.execute("""SELECT MAX (chatlist_id) FROM manage1_chatlists""").fetchone()[0]+1
        engine.execute(f"""
        INSERT INTO manage1_chatlists VALUES({uid}, {chatlist_id})
        """)
    else:
        return chatlist_id[0]

    return chatlist_id

def get_chats():
    uid = get_uid()
    chatlist_id = get_chatlist_id()
    chat_ids = g.conn.execute(f"""
        SELECT cid
        FROM contain1
        WHERE uid={uid} AND chatlist_id = {chatlist_id}
        """).fetchall()

    chats = []
    for cid in chat_ids:
        chats.append(g.conn.execute(f"""
            SELECT cid, name
            FROM chatrooms
            WHERE cid = {cid[0]}
            """).fetchone())

    return chats


if __name__ == "__main__":
    app.run()
