from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'Moscowtrafikwet33!'  # Обязательно измените на уникальный ключ
socketio = SocketIO(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Конфигурация базы данных
DATABASE = 'users.db'

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    @staticmethod
    def get(user_id):
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password'])
        return None

    @staticmethod
    def find_by_username(username):
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password'])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Добавляем тестового пользователя если его нет
    if not conn.execute('SELECT 1 FROM users WHERE username = "admin"').fetchone():
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin123')))
    conn.commit()
    conn.close()

@app.before_request
def before_request():
    if not request.is_secure and request.url.startswith('http://'):
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)
@app.context_processor
def inject_user():
    return dict(current_user=current_user)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Заполните все поля')
            return redirect(url_for('login'))

        user = User.find_by_username(username)
        
        if user is None:
            flash('Пользователь не найден')
            return redirect(url_for('login'))
            
        if not check_password_hash(user.password, password):
            flash('Неверный пароль')
            return redirect(url_for('login'))

        login_user(user)
        flash(f'Добро пожаловать, {username}!')
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Заполните все поля')
            return redirect(url_for('register'))

        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, generate_password_hash(password)))
            conn.commit()
            conn.close()
            flash('Регистрация успешна! Теперь войдите')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Имя пользователя уже занято')

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    traffic_data = [
        {"road": "Ленинский проспект", "level": "high", "speed": 20},
        {"road": "Кутузовский проспект", "level": "medium", "speed": 40},
        {"road": "Третье транспортное кольцо", "level": "high", "speed": 15},
        {"road": "Садовое кольцо", "level": "medium", "speed": 35},
        {"road": "Проспект Мира", "level": "low", "speed": 50}
    ]

    weather_data = {
        "temp": 15,
        "condition": "Облачно",
        "humidity": 75,
        "wind": 5
    }

    return render_template('dashboard.html',
                           traffic_data=traffic_data,
                           weather_data=weather_data)

@app.route('/transport')
@login_required
def transport():
    return render_template('transport.html',
                           username=current_user.username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы')
    return redirect(url_for('index'))

@app.route('/debug')
def debug():
    return f"""
    <pre>
    Session: {dict(session)}
    Logged in: {current_user.is_authenticated}
    Current user: {current_user.username if current_user.is_authenticated else 'None'}
    Users in DB: {get_db_connection().execute('SELECT username FROM users').fetchall()}
    </pre>
    """

@socketio.on('message')
def handle_message(data):
    if not current_user.is_authenticated:
        return False

    emit('message', {
        'username': current_user.username,
        'message': data['message'],
        'time': datetime.now().strftime('%H:%M')
    }, broadcast=True)
if __name__ == '__main__':
    init_db()
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        ssl_context=('cert.pem', 'key.pem'),
        debug=True,
        allow_unsafe_werkzeug=True
    )