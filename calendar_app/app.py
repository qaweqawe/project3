from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta, timezone
import calendar
import os
import socket
import uuid

# Московский часовой пояс (UTC+3) - используем timezone
MOSCOW_TZ = timezone(timedelta(hours=3))


def moscow_now():
    """Возвращает текущее время в московском часовом поясе"""
    return datetime.now(MOSCOW_TZ)


def make_aware(dt):
    """Делает datetime объект aware (с часовым поясом)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=MOSCOW_TZ)
    return dt


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calendar.db'
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к календарю.'


# ============ МОДЕЛИ ============

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(20), default='light')
    gender = db.Column(db.String(10), default='other')
    birth_date = db.Column(db.String(10))
    avatar = db.Column(db.String(200), default='default.png')
    created_at = db.Column(db.DateTime, default=moscow_now)
    last_seen = db.Column(db.DateTime, default=moscow_now)

    sent_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.from_user_id', backref='from_user',
                                    lazy='dynamic', cascade='all, delete-orphan')
    received_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.to_user_id', backref='to_user',
                                        lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='user', lazy=True, cascade='all, delete-orphan')
    day_colors = db.relationship('DayColor', backref='user', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('Event', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver',
                                        lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def get_avatar_url(self):
        if self.avatar and self.avatar != 'default.png' and os.path.exists(
                os.path.join(app.config['UPLOAD_FOLDER'], self.avatar)):
            return url_for('static', filename=f'uploads/{self.avatar}')
        return url_for('static', filename='uploads/default.png')

    def get_friends(self):
        sent = FriendRequest.query.filter_by(from_user_id=self.id, status='accepted').all()
        received = FriendRequest.query.filter_by(to_user_id=self.id, status='accepted').all()
        friends = []
        for req in sent: friends.append(req.to_user)
        for req in received: friends.append(req.from_user)
        return friends

    def is_friend(self, user_id):
        sent = FriendRequest.query.filter_by(from_user_id=self.id, to_user_id=user_id, status='accepted').first()
        received = FriendRequest.query.filter_by(from_user_id=user_id, to_user_id=self.id, status='accepted').first()
        return sent is not None or received is not None

    def get_pending_requests(self):
        return FriendRequest.query.filter_by(to_user_id=self.id, status='pending').all()

    def update_last_seen(self):
        self.last_seen = moscow_now()
        db.session.commit()

    def is_online(self):
        if not self.last_seen:
            return False
        last_seen_aware = make_aware(self.last_seen)
        now = moscow_now()
        return (now - last_seen_aware).total_seconds() < 300


class FriendRequest(db.Model):
    __tablename__ = 'friend_requests'
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=moscow_now)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=moscow_now)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    link = db.Column(db.String(500))
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=moscow_now)


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    text = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(20), default='#667eea')
    created_at = db.Column(db.DateTime, default=moscow_now)


class DayColor(db.Model):
    __tablename__ = 'day_colors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=moscow_now)


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#48bb78')
    is_shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=moscow_now)


class SharedEvent(db.Model):
    __tablename__ = 'shared_events'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=moscow_now)
    event = db.relationship('Event', backref='shared_with')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ============ ПРАЗДНИКИ ============

RUSSIAN_HOLIDAYS = {
    '01-01': 'Новый год', '01-02': 'Новогодние каникулы', '01-03': 'Новогодние каникулы',
    '01-04': 'Новогодние каникулы', '01-05': 'Новогодние каникулы', '01-06': 'Новогодние каникулы',
    '01-07': 'Рождество', '01-08': 'Новогодние каникулы',
    '02-23': 'День защитника Отечества', '03-08': 'Международный женский день',
    '05-01': 'Праздник Весны и Труда', '05-09': 'День Победы',
    '06-12': 'День России', '11-04': 'День народного единства'
}


def get_personal_holidays(user):
    holidays = {}
    if user and user.birth_date:
        parts = user.birth_date.split('-')
        if len(parts) == 3:
            holidays[f"{parts[1]}-{parts[2]}"] = '🎂 День рождения'
    return holidays


def create_notification(user_id, type, title, message, link=None):
    try:
        n = Notification(user_id=user_id, type=type, title=title, message=message, link=link)
        db.session.add(n)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка уведомления: {e}")
        db.session.rollback()


# ============ МАРШРУТЫ ============

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    now = moscow_now()
    current_user.update_last_seen()
    return render_template('index.html',
                           current_year=now.year,
                           current_month=now.month,
                           current_day=now.day,
                           user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'Все поля обязательны'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Пользователь уже существует'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email уже используется'}), 400
        user = User(username=username, email=email, gender=data.get('gender', 'other'),
                    birth_date=data.get('birth_date'))
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return jsonify({'success': True, 'theme': user.theme})
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=data.get('remember', False))
            user.update_last_seen()
            return jsonify({'success': True, 'theme': user.theme})
        return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'}), 401
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                filename = f"{uuid.uuid4()}.jpg"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                if current_user.avatar and current_user.avatar != 'default.png':
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.avatar)
                    if os.path.exists(old_path): os.remove(old_path)
                current_user.avatar = filename
                db.session.commit()
                return jsonify({'success': True, 'avatar': current_user.get_avatar_url()})
        data = request.json
        if data:
            if 'gender' in data: current_user.gender = data['gender']
            if 'birth_date' in data: current_user.birth_date = data['birth_date']
            db.session.commit()
            return jsonify({'success': True})
    return render_template('profile.html', user=current_user)


@app.route('/update_theme', methods=['POST'])
@login_required
def update_theme():
    current_user.theme = request.json.get('theme', 'light')
    db.session.commit()
    return jsonify({'success': True})


@app.route('/friends')
@login_required
def friends_page():
    return render_template('friends.html', user=current_user)


# ============ API ДРУЗЕЙ ============

@app.route('/api/friends/search')
@login_required
def api_friends_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2: return jsonify([])
    users = User.query.filter(User.username.contains(q), User.id != current_user.id).limit(10).all()
    friends_ids = [f.id for f in current_user.get_friends()]
    result = []
    for u in users:
        pending_sent = FriendRequest.query.filter_by(from_user_id=current_user.id, to_user_id=u.id,
                                                     status='pending').first()
        pending_received = FriendRequest.query.filter_by(from_user_id=u.id, to_user_id=current_user.id,
                                                         status='pending').first()
        result.append({
            'id': u.id, 'username': u.username, 'avatar': u.get_avatar_url(),
            'is_friend': u.id in friends_ids,
            'pending_sent': pending_sent is not None,
            'pending_received': pending_received is not None
        })
    return jsonify(result)


@app.route('/api/friends/send_request', methods=['POST'])
@login_required
def api_send_friend_request():
    friend_id = request.json.get('friend_id')
    if not friend_id or friend_id == current_user.id:
        return jsonify({'success': False, 'error': 'Неверный запрос'}), 400
    friend = db.session.get(User, friend_id)
    if not friend: return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
    if current_user.is_friend(friend_id):
        return jsonify({'success': False, 'error': 'Вы уже друзья'}), 400
    existing = FriendRequest.query.filter_by(from_user_id=current_user.id, to_user_id=friend_id,
                                             status='pending').first()
    if existing: return jsonify({'success': False, 'error': 'Заявка уже отправлена'}), 400
    reverse = FriendRequest.query.filter_by(from_user_id=friend_id, to_user_id=current_user.id,
                                            status='pending').first()
    if reverse:
        reverse.status = 'accepted'
        db.session.commit()
        create_notification(friend_id, 'friend_accepted', 'Заявка принята',
                            f'{current_user.username} принял вашу заявку')
        return jsonify({'success': True, 'message': 'Заявка автоматически принята'})
    req = FriendRequest(from_user_id=current_user.id, to_user_id=friend_id)
    db.session.add(req)
    db.session.commit()
    create_notification(friend_id, 'friend_request', 'Новая заявка в друзья',
                        f'{current_user.username} хочет добавить вас в друзья')
    return jsonify({'success': True})


@app.route('/api/friends/respond', methods=['POST'])
@login_required
def api_respond_friend_request():
    data = request.json
    req = FriendRequest.query.filter_by(from_user_id=data.get('from_user_id'), to_user_id=current_user.id,
                                        status='pending').first()
    if not req: return jsonify({'success': False, 'error': 'Заявка не найдена'}), 404
    if data.get('action') == 'accept':
        req.status = 'accepted'
        create_notification(req.from_user_id, 'friend_accepted', 'Заявка принята',
                            f'{current_user.username} принял вашу заявку')
    else:
        req.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/friends/remove', methods=['POST'])
@login_required
def api_remove_friend():
    friend_id = request.json.get('friend_id')
    FriendRequest.query.filter(
        ((FriendRequest.from_user_id == current_user.id) & (FriendRequest.to_user_id == friend_id)) |
        ((FriendRequest.from_user_id == friend_id) & (FriendRequest.to_user_id == current_user.id))
    ).delete()
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/friends/list')
@login_required
def api_friends_list():
    friends = current_user.get_friends()
    return jsonify([{
        'id': f.id,
        'username': f.username,
        'avatar': f.get_avatar_url(),
        'online': f.is_online()
    } for f in friends])


@app.route('/api/friends/requests')
@login_required
def api_friend_requests():
    requests = current_user.get_pending_requests()
    return jsonify([{'id': r.id, 'user': {'id': r.from_user.id, 'username': r.from_user.username,
                                          'avatar': r.from_user.get_avatar_url()},
                     'created_at': r.created_at.isoformat()} for r in requests])


# ============ API ЧАТА ============

@app.route('/api/messages/<int:friend_id>')
@login_required
def api_get_messages(friend_id):
    if not current_user.is_friend(friend_id):
        return jsonify({'error': 'Не друг'}), 403

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == friend_id)) |
        ((Message.sender_id == friend_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).limit(100).all()

    Message.query.filter_by(sender_id=friend_id, receiver_id=current_user.id, read=False).update({'read': True})
    db.session.commit()

    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'text': m.text,
        'read': m.read,
        'created_at': m.created_at.isoformat()
    } for m in messages])


@app.route('/api/messages/send', methods=['POST'])
@login_required
def api_send_message():
    data = request.json
    friend_id = data.get('friend_id')
    text = data.get('text', '').strip()

    if not text or not friend_id:
        return jsonify({'success': False, 'error': 'Пустое сообщение'}), 400

    if not current_user.is_friend(friend_id):
        return jsonify({'success': False, 'error': 'Не друг'}), 403

    msg = Message(sender_id=current_user.id, receiver_id=friend_id, text=text)
    db.session.add(msg)
    db.session.commit()

    create_notification(
        friend_id, 'new_message', 'Новое сообщение',
        f'{current_user.username}: {text[:50]}...',
        f'/friends?chat={current_user.id}'
    )

    return jsonify({'success': True, 'message': {
        'id': msg.id,
        'sender_id': msg.sender_id,
        'text': msg.text,
        'created_at': msg.created_at.isoformat()
    }})


@app.route('/api/messages/unread')
@login_required
def api_unread_messages():
    unread = db.session.query(Message.sender_id, db.func.count(Message.id).label('count')) \
        .filter_by(receiver_id=current_user.id, read=False) \
        .group_by(Message.sender_id).all()

    return jsonify({str(u[0]): u[1] for u in unread})


# ============ КАЛЕНДАРЬ ============

@app.route('/get_calendar/<int:year>/<int:month>')
@login_required
def get_calendar(year, month):
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь',
                   'Ноябрь', 'Декабрь']
    cal = calendar.monthcalendar(year, month)
    personal = get_personal_holidays(current_user)
    month_days = []
    for week in cal:
        week_days = []
        for day in week:
            if day == 0:
                week_days.append({'day': '', 'is_holiday': False})
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                month_day = f"{month:02d}-{day:02d}"
                is_holiday = month_day in RUSSIAN_HOLIDAYS or month_day in personal
                holiday_name = personal.get(month_day) or RUSSIAN_HOLIDAYS.get(month_day, '')
                day_color = DayColor.query.filter_by(user_id=current_user.id, date=date_str).first()
                comment = Comment.query.filter_by(user_id=current_user.id, date=date_str).first()
                own_events = Event.query.filter_by(user_id=current_user.id, date=date_str).all()
                shared_events = Event.query.join(SharedEvent).filter(SharedEvent.user_id == current_user.id,
                                                                     Event.date == date_str).all()
                all_events = own_events + shared_events
                week_days.append({
                    'day': day, 'date': date_str, 'is_holiday': is_holiday, 'holiday_name': holiday_name,
                    'color': day_color.color if day_color else '',
                    'has_comment': comment is not None and comment.text.strip() != '',
                    'comment_color': comment.color if comment else '#667eea',
                    'events': [{'id': e.id, 'title': e.title, 'color': e.color, 'is_shared': e.is_shared} for e in
                               all_events[:5]]
                })
        month_days.append(week_days)
    today = moscow_now()
    return jsonify({'year': year, 'month': month, 'month_name': month_names[month - 1], 'calendar': month_days,
                    'today': f"{today.year}-{today.month:02d}-{today.day:02d}"})


@app.route('/get_day_info/<date>')
@login_required
def get_day_info(date):
    month_day = date[5:]
    holiday = get_personal_holidays(current_user).get(month_day) or RUSSIAN_HOLIDAYS.get(month_day, '')
    comment = Comment.query.filter_by(user_id=current_user.id, date=date).first()
    own_events = Event.query.filter_by(user_id=current_user.id, date=date).all()
    shared_events = Event.query.join(SharedEvent).filter(SharedEvent.user_id == current_user.id,
                                                         Event.date == date).all()
    all_events = own_events + shared_events
    return jsonify({
        'date': date, 'holiday': holiday,
        'comment': {'id': comment.id, 'text': comment.text, 'color': comment.color} if comment else None,
        'events': [
            {'id': e.id, 'title': e.title, 'description': e.description, 'color': e.color, 'is_shared': e.is_shared} for
            e in all_events]
    })


@app.route('/get_comment/<date>')
@login_required
def get_comment(date):
    comment = Comment.query.filter_by(user_id=current_user.id, date=date).first()
    return jsonify(
        {'id': comment.id, 'text': comment.text, 'color': comment.color} if comment else {'id': None, 'text': '',
                                                                                          'color': '#667eea'})


@app.route('/save_comment', methods=['POST'])
@login_required
def save_comment():
    data = request.json
    comment = Comment.query.filter_by(user_id=current_user.id, date=data['date']).first()
    if comment:
        comment.text = data['text'];
        comment.color = data.get('color', '#667eea')
    else:
        db.session.add(
            Comment(user_id=current_user.id, date=data['date'], text=data['text'], color=data.get('color', '#667eea')))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/delete_comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id, user_id=current_user.id).first()
    if comment: db.session.delete(comment); db.session.commit()
    return jsonify({'success': True})


@app.route('/save_event', methods=['POST'])
@login_required
def save_event():
    data = request.json
    is_shared = data.get('is_shared', False)
    shared_with = data.get('shared_with', [])

    if data.get('id'):
        event = Event.query.filter_by(id=data['id'], user_id=current_user.id).first()
        if event:
            event.title = data['title'];
            event.description = data.get('description', '')
            event.color = data.get('color', '#48bb78');
            event.is_shared = is_shared
    else:
        event = Event(user_id=current_user.id, date=data['date'], title=data['title'],
                      description=data.get('description', ''), color=data.get('color', '#48bb78'), is_shared=is_shared)
        db.session.add(event)
        db.session.flush()

    if is_shared:
        SharedEvent.query.filter_by(event_id=event.id).delete()
        for friend_id in shared_with:
            if current_user.is_friend(friend_id):
                db.session.add(SharedEvent(event_id=event.id, user_id=friend_id))
                friend = db.session.get(User, friend_id)
                create_notification(
                    friend_id, 'shared_event', 'Совместное событие',
                    f'{current_user.username} создал совместное событие "{event.title}" на {event.date}',
                    f'/?date={event.date}'
                )

    db.session.commit()
    return jsonify({'success': True})


@app.route('/get_events/<date>')
@login_required
def get_events(date):
    own_events = Event.query.filter_by(user_id=current_user.id, date=date).all()
    shared_events = Event.query.join(SharedEvent).filter(SharedEvent.user_id == current_user.id,
                                                         Event.date == date).all()
    return jsonify(
        [{'id': e.id, 'title': e.title, 'description': e.description, 'color': e.color, 'is_shared': e.is_shared} for e
         in own_events + shared_events])


@app.route('/get_event/<int:event_id>')
@login_required
def get_event(event_id):
    event = Event.query.filter_by(id=event_id).first()
    if event and (event.user_id == current_user.id or SharedEvent.query.filter_by(event_id=event_id,
                                                                                  user_id=current_user.id).first()):
        return jsonify({'id': event.id, 'title': event.title, 'description': event.description, 'color': event.color,
                        'date': event.date, 'is_shared': event.is_shared})
    return jsonify({'error': 'Не найдено'}), 404


@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    event = Event.query.filter_by(id=event_id).first()
    if event and (event.user_id == current_user.id or SharedEvent.query.filter_by(event_id=event_id,
                                                                                  user_id=current_user.id).first()):
        if event.user_id == current_user.id:
            SharedEvent.query.filter_by(event_id=event_id).delete()
            db.session.delete(event)
        else:
            SharedEvent.query.filter_by(event_id=event_id, user_id=current_user.id).delete()
        db.session.commit()
    return jsonify({'success': True})


@app.route('/set_day_color', methods=['POST'])
@login_required
def set_day_color():
    data = request.json
    for date in data['dates']:
        day_color = DayColor.query.filter_by(user_id=current_user.id, date=date).first()
        if day_color:
            if data['color']:
                day_color.color = data['color']
            else:
                db.session.delete(day_color)
        elif data['color']:
            db.session.add(DayColor(user_id=current_user.id, date=date, color=data['color']))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/notifications')
@login_required
def api_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()).limit(50).all()
    unread = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    return jsonify({'notifications': [
        {'id': n.id, 'type': n.type, 'title': n.title, 'message': n.message, 'link': n.link, 'read': n.read,
         'created_at': n.created_at.isoformat()} for n in notifications], 'unread_count': unread})


@app.route('/api/notifications/read_all', methods=['POST'])
@login_required
def api_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/<int:notification_id>/delete', methods=['DELETE'])
@login_required
def api_delete_notification(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification and notification.user_id == current_user.id:
        db.session.delete(notification)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Не найдено'}), 404


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def create_default_avatar():
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'default.png')
    if not os.path.exists(path):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (300, 300), '#667eea')
            d = ImageDraw.Draw(img)
            d.ellipse((100, 80, 200, 180), fill='white')
            d.ellipse((75, 200, 225, 280), fill='white')
            img.save(path)
        except:
            pass


if __name__ == '__main__':
    if os.path.exists('calendar.db'): os.remove('calendar.db')
    with app.app_context():
        db.create_all()
        create_default_avatar()
        print("✅ База создана")
    ip = get_local_ip()
    print(f"\n📍 http://127.0.0.1:5000")
    print(f"🌐 http://{ip}:5000\n")
    app.run(debug=True, host='0.0.0.0', port=5000)