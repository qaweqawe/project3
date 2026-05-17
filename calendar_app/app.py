from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta, timezone
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY
import calendar
import os
import socket
import uuid
import json
import re

MOSCOW_TZ = timezone(timedelta(hours=3))

def moscow_now():
    return datetime.now(MOSCOW_TZ)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calendar.db'
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        try:
            current_user.last_seen = moscow_now()
            db.session.commit()
        except:
            db.session.rollback()

def is_mobile():
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['android', 'iphone', 'ipod', 'blackberry', 'windows phone', 'opera mini', 'iemobile']
    for keyword in mobile_keywords:
        if keyword in user_agent:
            return True
    return False

def get_version():
    version = request.args.get('version', 'auto')
    if version == 'desktop':
        return 'desktop'
    elif version == 'mobile':
        return 'mobile'
    else:
        return 'mobile' if is_mobile() else 'desktop'

friends = db.Table('friends',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('status', db.String(20), default='pending'),
    db.Column('created_at', db.DateTime, default=moscow_now)
)

group_members = db.Table('group_members',
    db.Column('group_id', db.Integer, db.ForeignKey('chat_groups.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('is_admin', db.Boolean, default=False),
    db.Column('joined_at', db.DateTime, default=moscow_now)
)

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

    sent_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.from_user_id', backref='from_user', lazy='dynamic', cascade='all, delete-orphan')
    received_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.to_user_id', backref='to_user', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='user', lazy=True, cascade='all, delete-orphan')
    day_colors = db.relationship('DayColor', backref='user', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('Event', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')

    friends = db.relationship('User', secondary=friends, primaryjoin=(friends.c.user_id == id), secondaryjoin=(friends.c.friend_id == id), backref=db.backref('friend_of', lazy='dynamic'), lazy='dynamic')
    groups = db.relationship('ChatGroup', secondary=group_members, backref='members')

    def set_password(self, p): self.password_hash = bcrypt.generate_password_hash(p).decode('utf-8')
    def check_password(self, p): return bcrypt.check_password_hash(self.password_hash, p)
    def get_avatar_url(self):
        if self.avatar and self.avatar != 'default.png' and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], self.avatar)):
            return url_for('static', filename=f'uploads/{self.avatar}')
        return url_for('static', filename='uploads/default.png')
    def get_friends(self):
        sent = FriendRequest.query.filter_by(from_user_id=self.id, status='accepted').all()
        received = FriendRequest.query.filter_by(to_user_id=self.id, status='accepted').all()
        return list(set([r.to_user for r in sent] + [r.from_user for r in received]))
    def is_friend(self, uid):
        return FriendRequest.query.filter(((FriendRequest.from_user_id==self.id)&(FriendRequest.to_user_id==uid)) | ((FriendRequest.from_user_id==uid)&(FriendRequest.to_user_id==self.id)), FriendRequest.status=='accepted').first() is not None
    def get_pending_requests(self): return FriendRequest.query.filter_by(to_user_id=self.id, status='pending').all()
    def is_online(self):
        if not self.last_seen: return False
        return (moscow_now() - self.last_seen.replace(tzinfo=MOSCOW_TZ)).total_seconds() < 30

class FriendRequest(db.Model):
    __tablename__ = 'friend_requests'
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=moscow_now)

class ChatGroup(db.Model):
    __tablename__ = 'chat_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(200), default='group_default.png')
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=moscow_now)
    creator = db.relationship('User', backref='created_groups')
    messages = db.relationship('GroupMessage', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    def get_avatar_url(self):
        return url_for('static', filename=f'uploads/{self.avatar}') if self.avatar != 'group_default.png' else url_for('static', filename='uploads/group_default.png')

class GroupMessage(db.Model):
    __tablename__ = 'group_messages'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_groups.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    reply_to = db.Column(db.Integer)
    edited = db.Column(db.Boolean, default=False)
    reactions = db.Column(db.Text, default='{}')
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=moscow_now)
    sender = db.relationship('User', backref='group_messages_sent')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    reply_to = db.Column(db.Integer)
    edited = db.Column(db.Boolean, default=False)
    reactions = db.Column(db.Text, default='{}')
    pinned = db.Column(db.Boolean, default=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=moscow_now)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50)); title = db.Column(db.String(200))
    message = db.Column(db.Text); link = db.Column(db.String(500))
    read = db.Column(db.Boolean, default=False); created_at = db.Column(db.DateTime, default=moscow_now)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False); text = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(20), default='#667eea'); created_at = db.Column(db.DateTime, default=moscow_now)

class DayColor(db.Model):
    __tablename__ = 'day_colors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False); color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=moscow_now)

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#48bb78')
    category = db.Column(db.String(50), default='personal')
    is_shared = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_type = db.Column(db.String(20))
    recurring_end = db.Column(db.String(10))
    has_time = db.Column(db.Boolean, default=False)
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))
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

EVENT_CATEGORIES = {
    'work': {'name': 'Работа', 'icon': '💼', 'color': '#667eea'},
    'personal': {'name': 'Личное', 'icon': '👤', 'color': '#48bb78'},
    'health': {'name': 'Здоровье', 'icon': '🏥', 'color': '#f56565'},
    'birthday': {'name': 'День рождения', 'icon': '🎂', 'color': '#ed8936'},
    'meeting': {'name': 'Встреча', 'icon': '🤝', 'color': '#9f7aea'},
    'other': {'name': 'Другое', 'icon': '📌', 'color': '#a0aec0'}
}

RUSSIAN_HOLIDAYS = {
    '01-01': 'Новый год', '01-02': 'Новогодние каникулы', '01-03': 'Новогодние каникулы',
    '01-04': 'Новогодние каникулы', '01-05': 'Новогодние каникулы', '01-06': 'Новогодние каникулы',
    '01-07': 'Рождество', '01-08': 'Новогодние каникулы',
    '02-23': 'День защитника', '03-08': '8 марта',
    '05-01': '1 мая', '05-09': 'День Победы',
    '06-12': 'День России', '11-04': 'День единства'
}

def get_personal_holidays(user):
    holidays = {}
    if user and user.birth_date:
        parts = user.birth_date.split('-')
        if len(parts) == 3: holidays[f"{parts[1]}-{parts[2]}"] = '🎂 День рождения'
    return holidays

def create_notification(uid, t, title, msg, link=None):
    try:
        n = Notification(user_id=uid, type=t, title=title, message=msg, link=link)
        db.session.add(n)
        db.session.commit()
        print(f"Уведомление: {title} -> user {uid}")
        return True
    except Exception as e:
        print(f"Ошибка уведомления: {e}")
        db.session.rollback()
        return False

def get_recurring_dates(event, year, month):
    if not event.is_recurring or not event.recurring_type: return []
    last_day = calendar.monthrange(year, month)[1]
    start_date = datetime.strptime(event.date, '%Y-%m-%d')
    end_date = datetime(year, month, last_day)
    if event.recurring_end:
        try: end_date = min(end_date, datetime.strptime(event.recurring_end, '%Y-%m-%d'))
        except: pass
    if start_date > end_date: return []
    freq_map = {'weekly': WEEKLY, 'monthly': MONTHLY, 'yearly': YEARLY}
    freq = freq_map.get(event.recurring_type, WEEKLY)
    try:
        dates = list(rrule(freq, dtstart=start_date, until=end_date))
        return [d.strftime('%Y-%m-%d') for d in dates if d.strftime('%Y-%m-%d') != event.date and d.month == month]
    except: return []

@app.route('/')
def index():
    if not current_user.is_authenticated: return redirect(url_for('login'))
    now = moscow_now()
    version = get_version()
    if version == 'mobile':
        return render_template('index_mobile.html', current_year=now.year, current_month=now.month, current_day=now.day, user=current_user, event_categories=EVENT_CATEGORIES)
    return render_template('index.html', current_year=now.year, current_month=now.month, current_day=now.day, user=current_user, event_categories=EVENT_CATEGORIES)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.json
        u = data.get('username','').strip(); e = data.get('email','').strip(); p = data.get('password','')
        if not u or not e or not p: return jsonify({'success':False,'error':'Заполните все поля'}),400
        if User.query.filter_by(username=u).first(): return jsonify({'success':False,'error':'Пользователь существует'}),400
        if User.query.filter_by(email=e).first(): return jsonify({'success':False,'error':'Email занят'}),400
        user = User(username=u, email=e, gender=data.get('gender','other'), birth_date=data.get('birth_date'))
        user.set_password(p); db.session.add(user); db.session.commit()
        login_user(user)
        return jsonify({'success':True,'theme':user.theme})
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.json
        u = data.get('username','').strip(); p = data.get('password','')
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user, remember=data.get('remember',False))
            user.last_seen = moscow_now(); db.session.commit()
            return jsonify({'success':True,'theme':user.theme})
        return jsonify({'success':False,'error':'Неверный логин или пароль'}),401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                fn = f"{uuid.uuid4()}.jpg"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                if current_user.avatar != 'default.png':
                    try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], current_user.avatar))
                    except: pass
                current_user.avatar = fn; db.session.commit()
                return jsonify({'success':True,'avatar':current_user.get_avatar_url()})
        data = request.json
        if data:
            if data.get('username'):
                nu = data['username'].strip()
                if nu != current_user.username:
                    if User.query.filter_by(username=nu).first(): return jsonify({'success':False,'error':'Ник занят'}),400
                    current_user.username = nu
            if 'gender' in data: current_user.gender = data['gender']
            if 'birth_date' in data: current_user.birth_date = data['birth_date']
            db.session.commit(); return jsonify({'success':True})
    version = get_version()
    if version == 'mobile':
        return render_template('profile_mobile.html', user=current_user)
    return render_template('profile.html', user=current_user)

@app.route('/update_theme', methods=['POST'])
@login_required
def update_theme():
    current_user.theme = request.json.get('theme','light'); db.session.commit()
    return jsonify({'success':True})

@app.route('/friends')
@login_required
def friends_page():
    return render_template('friends.html', user=current_user, event_categories=EVENT_CATEGORIES)

@app.route('/get_calendar/<int:year>/<int:month>')
@login_required
def get_calendar(year, month):
    mn = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
    cal = calendar.monthcalendar(year, month); personal = get_personal_holidays(current_user)
    recurring_events = Event.query.filter_by(user_id=current_user.id, is_recurring=True).all()
    recurring_map = {}
    for ev in recurring_events:
        dates = get_recurring_dates(ev, year, month)
        for d in dates:
            if d not in recurring_map: recurring_map[d] = []
            recurring_map[d].append(ev)
    md = []
    for week in cal:
        wd = []
        for day in week:
            if day == 0: wd.append({'day':'','is_holiday':False})
            else:
                ds = f"{year}-{month:02d}-{day:02d}"; mds = f"{month:02d}-{day:02d}"
                ih = mds in RUSSIAN_HOLIDAYS or mds in personal
                hn = personal.get(mds) or RUSSIAN_HOLIDAYS.get(mds,'')
                dc = DayColor.query.filter_by(user_id=current_user.id, date=ds).first()
                cm = Comment.query.filter_by(user_id=current_user.id, date=ds).first()
                ev = Event.query.filter_by(user_id=current_user.id, date=ds).all()
                if ds in recurring_map: ev = ev + recurring_map[ds]
                wd.append({'day':day,'date':ds,'is_holiday':ih,'holiday_name':hn,'color':dc.color if dc else '','has_comment':cm is not None and cm.text.strip()!='','comment_color':cm.color if cm else '#667eea','events':[{'id':e.id,'title':e.title,'color':e.color,'icon':EVENT_CATEGORIES.get(e.category,EVENT_CATEGORIES['other'])['icon'],'is_recurring':e.is_recurring,'has_time':e.has_time,'start_time':e.start_time,'end_time':e.end_time} for e in ev[:5]]})
        md.append(wd)
    today = moscow_now()
    return jsonify({'year':year,'month':month,'month_name':mn[month-1],'calendar':md,'today':f"{today.year}-{today.month:02d}-{today.day:02d}"})

@app.route('/get_week_view/<int:year>/<int:month>/<int:day>')
@login_required
def get_week_view(year, month, day):
    date = datetime(year, month, day); start = date - timedelta(days=date.weekday())
    days = []
    for i in range(7):
        d = start + timedelta(days=i); ds = d.strftime('%Y-%m-%d')
        ev = Event.query.filter_by(user_id=current_user.id, date=ds).all()
        days.append({'date':ds,'day_name':d.strftime('%A'),'day':d.day,'events':[{'id':e.id,'title':e.title,'color':e.color,'icon':EVENT_CATEGORIES.get(e.category,EVENT_CATEGORIES['other'])['icon'],'has_time':e.has_time,'start_time':e.start_time,'end_time':e.end_time,'description':e.description} for e in ev]})
    return jsonify({'days':days})

@app.route('/save_event', methods=['POST'])
@login_required
def save_event():
    data = request.json
    if data.get('id'):
        ev = Event.query.filter_by(id=data['id'], user_id=current_user.id).first()
        if ev:
            ev.title = data['title']; ev.description = data.get('description',''); ev.color = data.get('color','#48bb78')
            ev.category = data.get('category','personal'); ev.is_recurring = data.get('is_recurring',False)
            ev.recurring_type = data.get('recurring_type'); ev.recurring_end = data.get('recurring_end')
            ev.is_shared = data.get('is_shared',False); ev.has_time = data.get('has_time',False)
            ev.start_time = data.get('start_time'); ev.end_time = data.get('end_time')
    else:
        ev = Event(user_id=current_user.id, date=data['date'], title=data['title'], description=data.get('description',''),color=data.get('color','#48bb78'), category=data.get('category','personal'),is_recurring=data.get('is_recurring',False), recurring_type=data.get('recurring_type'),recurring_end=data.get('recurring_end'), is_shared=data.get('is_shared',False),has_time=data.get('has_time',False), start_time=data.get('start_time'), end_time=data.get('end_time'))
        db.session.add(ev); db.session.flush()
    if data.get('is_shared'):
        SharedEvent.query.filter_by(event_id=ev.id).delete()
        for fid in data.get('shared_with',[]):
            if current_user.is_friend(int(fid)):
                db.session.add(SharedEvent(event_id=ev.id, user_id=int(fid)))
                create_notification(int(fid), 'shared_event', '📅 Совместное событие', f'{current_user.username} приглашает вас на "{ev.title}"', f'/?date={ev.date}')
    db.session.commit(); return jsonify({'success':True,'event_id':ev.id})

@app.route('/get_events/<date>')
@login_required
def get_events(date):
    return jsonify([{'id':e.id,'title':e.title,'color':e.color,'category':e.category,'is_recurring':e.is_recurring,'has_time':e.has_time,'start_time':e.start_time,'end_time':e.end_time,'icon':EVENT_CATEGORIES.get(e.category,EVENT_CATEGORIES['other'])['icon']} for e in Event.query.filter_by(user_id=current_user.id, date=date).all()])

@app.route('/get_event/<int:eid>')
@login_required
def get_event(eid):
    e = Event.query.filter_by(id=eid, user_id=current_user.id).first()
    if e: return jsonify({'id':e.id,'title':e.title,'description':e.description,'color':e.color,'date':e.date,'category':e.category,'is_recurring':e.is_recurring,'recurring_type':e.recurring_type,'recurring_end':e.recurring_end,'is_shared':e.is_shared,'has_time':e.has_time,'start_time':e.start_time,'end_time':e.end_time})
    return jsonify({'error':'Не найдено'}),404

@app.route('/delete_event/<int:eid>', methods=['DELETE'])
@login_required
def delete_event(eid):
    e = Event.query.filter_by(id=eid, user_id=current_user.id).first()
    if e: SharedEvent.query.filter_by(event_id=eid).delete(); db.session.delete(e); db.session.commit()
    return jsonify({'success':True})

@app.route('/get_day_info/<date>')
@login_required
def get_day_info(date):
    md = date[5:]; h = get_personal_holidays(current_user).get(md) or RUSSIAN_HOLIDAYS.get(md,'')
    c = Comment.query.filter_by(user_id=current_user.id, date=date).first()
    ev = Event.query.filter_by(user_id=current_user.id, date=date).all()
    return jsonify({'date':date,'holiday':h,'comment':{'id':c.id,'text':c.text,'color':c.color} if c else None,'events':[{'id':e.id,'title':e.title,'description':e.description,'color':e.color,'icon':EVENT_CATEGORIES.get(e.category,EVENT_CATEGORIES['other'])['icon'],'is_recurring':e.is_recurring,'has_time':e.has_time,'start_time':e.start_time,'end_time':e.end_time} for e in ev]})

@app.route('/get_comment/<date>')
@login_required
def get_comment(date):
    c = Comment.query.filter_by(user_id=current_user.id, date=date).first()
    return jsonify({'id':c.id,'text':c.text,'color':c.color} if c else {'id':None,'text':'','color':'#667eea'})

@app.route('/save_comment', methods=['POST'])
@login_required
def save_comment():
    d = request.json; c = Comment.query.filter_by(user_id=current_user.id, date=d['date']).first()
    if c: c.text=d['text']; c.color=d.get('color','#667eea')
    else: db.session.add(Comment(user_id=current_user.id, date=d['date'], text=d['text'], color=d.get('color','#667eea')))
    db.session.commit(); return jsonify({'success':True})

@app.route('/delete_comment/<int:cid>', methods=['DELETE'])
@login_required
def delete_comment(cid):
    c = Comment.query.filter_by(id=cid, user_id=current_user.id).first()
    if c: db.session.delete(c); db.session.commit()
    return jsonify({'success':True})

@app.route('/set_day_color', methods=['POST'])
@login_required
def set_day_color():
    d = request.json
    for date in d['dates']:
        dc = DayColor.query.filter_by(user_id=current_user.id, date=date).first()
        if dc:
            if d['color']: dc.color = d['color']
            else: db.session.delete(dc)
        elif d['color']: db.session.add(DayColor(user_id=current_user.id, date=date, color=d['color']))
    db.session.commit(); return jsonify({'success':True})

@app.route('/api/friends/search')
@login_required
def api_friends_search():
    q = request.args.get('q','').strip()
    if len(q)<2: return jsonify([])
    users = User.query.filter(User.username.contains(q), User.id!=current_user.id).limit(10).all()
    fids = [f.id for f in current_user.get_friends()]
    return jsonify([{'id':u.id,'username':u.username,'avatar':u.get_avatar_url(),'is_friend':u.id in fids} for u in users])

@app.route('/api/friends/send_request', methods=['POST'])
@login_required
def api_send_friend_request():
    fid = request.json.get('friend_id')
    if not fid or fid==current_user.id: return jsonify({'success':False}),400
    f = db.session.get(User, fid)
    if not f: return jsonify({'success':False}),404
    if current_user.is_friend(fid): return jsonify({'success':False}),400
    reverse = FriendRequest.query.filter_by(from_user_id=fid, to_user_id=current_user.id, status='pending').first()
    if reverse:
        reverse.status='accepted'; db.session.commit()
        create_notification(fid, 'friend_accepted', 'Заявка принята', f'{current_user.username} принял вашу заявку в друзья', '/friends')
        return jsonify({'success':True})
    db.session.add(FriendRequest(from_user_id=current_user.id, to_user_id=fid)); db.session.commit()
    create_notification(fid, 'friend_request', 'Новая заявка в друзья', f'{current_user.username} хочет добавить вас в друзья', '/friends')
    return jsonify({'success':True})

@app.route('/api/friends/respond', methods=['POST'])
@login_required
def api_respond_friend_request():
    d = request.json
    r = FriendRequest.query.filter_by(from_user_id=d.get('from_user_id'), to_user_id=current_user.id, status='pending').first()
    if not r: return jsonify({'success':False}),404
    r.status = 'accepted' if d.get('action')=='accept' else 'rejected'; db.session.commit()
    if r.status == 'accepted':
        create_notification(r.from_user_id, 'friend_accepted', 'Заявка принята', f'{current_user.username} принял вашу заявку в друзья', '/friends')
    return jsonify({'success':True})

@app.route('/api/friends/remove', methods=['POST'])
@login_required
def api_remove_friend():
    fid = request.json.get('friend_id')
    FriendRequest.query.filter(((FriendRequest.from_user_id==current_user.id)&(FriendRequest.to_user_id==fid)) | ((FriendRequest.from_user_id==fid)&(FriendRequest.to_user_id==current_user.id))).delete()
    db.session.commit(); return jsonify({'success':True})

@app.route('/api/friends/list')
@login_required
def api_friends_list():
    friends = current_user.get_friends()
    return jsonify([{'id':f.id,'username':f.username,'avatar':f.get_avatar_url(),'online':f.is_online(),'last_seen':f.last_seen.isoformat() if f.last_seen else None,'gender':f.gender} for f in friends])

@app.route('/api/friends/requests')
@login_required
def api_friend_requests():
    return jsonify([{'id':x.id,'user':{'id':x.from_user.id,'username':x.from_user.username,'avatar':x.from_user.get_avatar_url()}} for x in current_user.get_pending_requests()])

@app.route('/api/messages/<int:fid>')
@login_required
def api_get_messages(fid):
    if not current_user.is_friend(fid): return jsonify({'error':'Не друг'}),403
    ms = Message.query.filter(((Message.sender_id==current_user.id)&(Message.receiver_id==fid)) | ((Message.sender_id==fid)&(Message.receiver_id==current_user.id))).order_by(Message.created_at.asc()).limit(100).all()
    Message.query.filter_by(sender_id=fid, receiver_id=current_user.id, read=False).update({'read':True}); db.session.commit()
    result = []
    for m in ms:
        reply_data = None
        if m.reply_to:
            rm = db.session.get(Message, m.reply_to)
            if rm: reply_data = {'id':rm.id,'text':rm.text,'sender':rm.sender.username}
        result.append({'id':m.id,'sender_id':m.sender_id,'sender_name':m.sender.username,'sender_avatar':m.sender.get_avatar_url(),'text':m.text,'image_url':m.image_url,'reply_to':reply_data,'edited':m.edited,'reactions':json.loads(m.reactions) if m.reactions else {},'pinned':m.pinned,'read':m.read,'created_at':m.created_at.isoformat()})
    return jsonify(result)

@app.route('/api/messages/send', methods=['POST'])
@login_required
def api_send_message():
    d = request.json; fid = d.get('friend_id'); txt = d.get('text','').strip()
    image_url = d.get('image_url'); reply_to = d.get('reply_to'); edit_id = d.get('edit_id')
    if not txt and not image_url: return jsonify({'success':False,'error':'Пустое сообщение'}),400
    if not current_user.is_friend(fid): return jsonify({'success':False,'error':'Не друг'}),403
    if edit_id:
        msg = db.session.get(Message, edit_id)
        if msg and msg.sender_id == current_user.id: msg.text = txt; msg.image_url = image_url; msg.edited = True; db.session.commit(); return jsonify({'success':True,'message':{'id':msg.id,'edited':True}})
    m = Message(sender_id=current_user.id, receiver_id=fid, text=txt, image_url=image_url, reply_to=reply_to)
    db.session.add(m); db.session.commit()
    create_notification(fid, 'new_message', '💬 Новое сообщение', f'{current_user.username}: {(txt or "Изображение")[:50]}...', '/friends')
    reply_data = None
    if reply_to:
        rm = db.session.get(Message, reply_to)
        if rm: reply_data = {'id':rm.id,'text':rm.text,'sender':rm.sender.username}
    return jsonify({'success':True,'message':{'id':m.id,'sender_id':m.sender_id,'sender_name':current_user.username,'sender_avatar':current_user.get_avatar_url(),'text':m.text,'image_url':m.image_url,'reply_to':reply_data,'edited':False,'reactions':{},'pinned':False,'created_at':m.created_at.isoformat()}})

@app.route('/api/messages/<int:mid>', methods=['DELETE'])
@login_required
def delete_message(mid):
    m = db.session.get(Message, mid)
    if m and m.sender_id == current_user.id: db.session.delete(m); db.session.commit(); return jsonify({'success':True})
    return jsonify({'error':'Не найдено'}),404

@app.route('/api/messages/<int:mid>/pin', methods=['POST'])
@login_required
def pin_message(mid):
    m = db.session.get(Message, mid) or db.session.get(GroupMessage, mid)
    if m:
        if isinstance(m, Message): Message.query.filter(((Message.sender_id==current_user.id)&(Message.receiver_id==m.receiver_id)) | ((Message.sender_id==m.receiver_id)&(Message.receiver_id==current_user.id))).update({'pinned':False})
        else: GroupMessage.query.filter_by(group_id=m.group_id).update({'pinned':False})
        m.pinned = not m.pinned; db.session.commit()
        return jsonify({'success':True})
    return jsonify({'error':'Не найдено'}),404

@app.route('/api/messages/<int:mid>/reaction', methods=['POST'])
@login_required
def add_reaction(mid):
    data = request.json; emoji = data.get('emoji')
    m = db.session.get(Message, mid) or db.session.get(GroupMessage, mid)
    if m and emoji:
        reactions = json.loads(m.reactions) if m.reactions else {}
        if emoji not in reactions: reactions[emoji] = []
        if current_user.id in reactions[emoji]: reactions[emoji].remove(current_user.id)
        else: reactions[emoji].append(current_user.id)
        if not reactions[emoji]: del reactions[emoji]
        m.reactions = json.dumps(reactions) if reactions else '{}'; db.session.commit()
        return jsonify({'success':True,'reactions':reactions})
    return jsonify({'error':'Не найдено'}),404

@app.route('/api/messages/pinned/<int:fid>')
@login_required
def get_pinned_messages(fid):
    gid = request.args.get('group_id', type=int)
    if gid: m = GroupMessage.query.filter_by(group_id=gid, pinned=True).first()
    else: m = Message.query.filter(((Message.sender_id==current_user.id)&(Message.receiver_id==fid)) | ((Message.sender_id==fid)&(Message.receiver_id==current_user.id))).filter_by(pinned=True).first()
    if m:
        rd = None
        if m.reply_to:
            rm = db.session.get(Message, m.reply_to) or db.session.get(GroupMessage, m.reply_to)
            if rm: rd = {'id':rm.id,'text':rm.text,'sender':rm.sender.username}
        return jsonify([{'id':m.id,'text':m.text,'image_url':m.image_url,'sender_name':m.sender.username,'reply_to':rd}])
    return jsonify([])

@app.route('/api/messages/unread')
@login_required
def api_unread_messages():
    u = db.session.query(Message.sender_id, db.func.count(Message.id)).filter_by(receiver_id=current_user.id, read=False).group_by(Message.sender_id).all()
    return jsonify({str(x[0]):x[1] for x in u})

@app.route('/api/groups/create', methods=['POST'])
@login_required
def api_create_group():
    d = request.json; name = d.get('name','').strip()
    if not name: return jsonify({'success':False}),400
    g = ChatGroup(name=name, creator_id=current_user.id); db.session.add(g); db.session.flush()
    db.session.execute(group_members.insert().values(group_id=g.id, user_id=current_user.id, is_admin=True))
    for mid in d.get('members',[]):
        if current_user.is_friend(int(mid)):
            db.session.execute(group_members.insert().values(group_id=g.id, user_id=int(mid)))
            create_notification(int(mid), 'group_invite', '👥 Группа', f'{current_user.username} добавил вас в группу "{name}"', '/friends')
    db.session.commit(); return jsonify({'success':True,'group_id':g.id})


@app.route('/api/groups/<int:gid>/avatar', methods=['POST'])
@login_required
def api_update_group_avatar(gid):
    g = db.session.get(ChatGroup, gid)
    if not g: return jsonify({'success': False, 'error': 'Группа не найдена'}), 404
    if current_user not in g.members: return jsonify({'success': False, 'error': 'Вы не участник группы'}), 403

    if 'avatar' not in request.files: return jsonify({'success': False, 'error': 'Нет файла'}), 400
    file = request.files['avatar']
    if file.filename == '': return jsonify({'success': False, 'error': 'Файл не выбран'}), 400

    fn = f"group_{uuid.uuid4()}.jpg"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
    g.avatar = fn
    db.session.commit()
    return jsonify({'success': True, 'avatar': g.get_avatar_url()})

@app.route('/api/groups/list')
@login_required
def api_groups_list():
    groups = current_user.groups; result = []
    for g in groups:
        members_data = []
        for m in g.members:
            ms = db.session.execute(group_members.select().where(group_members.c.group_id==g.id, group_members.c.user_id==m.id)).first()
            members_data.append({'id':m.id,'username':m.username,'avatar':m.get_avatar_url(),'is_admin':ms.is_admin if ms else False})
        result.append({'id':g.id,'name':g.name,'avatar':g.get_avatar_url(),'creator_id':g.creator_id,'members_count':len(g.members),'members':members_data})
    return jsonify(result)

@app.route('/api/groups/<int:gid>/messages')
@login_required
def api_get_group_messages(gid):
    g = db.session.get(ChatGroup, gid)
    if not g or current_user not in g.members: return jsonify({'error':'Нет доступа'}),403
    ms = GroupMessage.query.filter_by(group_id=gid).order_by(GroupMessage.created_at.asc()).limit(100).all()
    result = []
    for m in ms:
        reply_data = None
        if m.reply_to:
            rm = db.session.get(GroupMessage, m.reply_to)
            if rm: reply_data = {'id':rm.id,'text':rm.text,'sender':rm.sender.username}
        result.append({'id':m.id,'sender_id':m.sender_id,'sender_name':m.sender.username,'sender_avatar':m.sender.get_avatar_url(),'text':m.text,'image_url':m.image_url,'reply_to':reply_data,'edited':m.edited,'reactions':json.loads(m.reactions) if m.reactions else {},'pinned':m.pinned,'created_at':m.created_at.isoformat()})
    return jsonify(result)

@app.route('/api/groups/<int:gid>/send', methods=['POST'])
@login_required
def api_send_group_message(gid):
    g = db.session.get(ChatGroup, gid)
    if not g or current_user not in g.members: return jsonify({'success':False}),403
    d = request.json; txt = d.get('text','').strip(); image_url = d.get('image_url')
    reply_to = d.get('reply_to'); edit_id = d.get('edit_id')
    if not txt and not image_url: return jsonify({'success':False,'error':'Пустое сообщение'}),400
    if edit_id:
        msg = db.session.get(GroupMessage, edit_id)
        if msg and msg.sender_id == current_user.id: msg.text = txt; msg.image_url = image_url; msg.edited = True; db.session.commit(); return jsonify({'success':True,'message':{'id':msg.id,'edited':True}})
    m = GroupMessage(group_id=gid, sender_id=current_user.id, text=txt, image_url=image_url, reply_to=reply_to)
    db.session.add(m); db.session.commit()
    for mb in g.members:
        if mb.id != current_user.id:
            create_notification(mb.id, 'group_message', f'💬 {g.name}', f'{current_user.username}: {(txt or "Изображение")[:50]}...', '/friends')
    reply_data = None
    if reply_to:
        rm = db.session.get(GroupMessage, reply_to)
        if rm: reply_data = {'id':rm.id,'text':rm.text,'sender':rm.sender.username}
    return jsonify({'success':True,'message':{'id':m.id,'sender_id':m.sender_id,'sender_name':current_user.username,'sender_avatar':current_user.get_avatar_url(),'text':m.text,'image_url':m.image_url,'reply_to':reply_data,'edited':False,'reactions':{},'pinned':False,'created_at':m.created_at.isoformat()}})

@app.route('/api/groups/<int:gid>/add_members', methods=['POST'])
@login_required
def api_add_group_members(gid):
    g = db.session.get(ChatGroup, gid)
    if not g: return jsonify({'success':False,'error':'Группа не найдена'}),404
    if current_user not in g.members: return jsonify({'success':False,'error':'Вы не участник группы'}),403
    data = request.json; member_ids = data.get('members',[]); added = 0
    for mid in member_ids:
        mid_int = int(mid)
        if current_user.is_friend(mid_int):
            existing = db.session.execute(group_members.select().where(group_members.c.group_id==gid, group_members.c.user_id==mid_int)).first()
            if not existing:
                db.session.execute(group_members.insert().values(group_id=gid, user_id=mid_int, is_admin=False))
                create_notification(mid_int, 'group_invite', '👥 Группа', f'{current_user.username} добавил вас в группу "{g.name}"', '/friends')
                added += 1
    db.session.commit(); return jsonify({'success':True,'added':added})

@app.route('/api/groups/<int:gid>/leave', methods=['POST'])
@login_required
def api_leave_group(gid):
    db.session.execute(group_members.delete().where(group_members.c.group_id==gid, group_members.c.user_id==current_user.id))
    if not db.session.execute(group_members.select().where(group_members.c.group_id==gid)).all():
        g = db.session.get(ChatGroup, gid)
        if g: db.session.delete(g)
    db.session.commit(); return jsonify({'success':True})

@app.route('/api/notifications')
@login_required
def api_notifications():
    try:
        ns = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
        unread = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        return jsonify({'notifications':[{'id':n.id,'type':n.type,'title':n.title,'message':n.message,'link':n.link,'read':n.read,'created_at':n.created_at.isoformat()} for n in ns],'unread_count':unread})
    except: return jsonify({'notifications':[],'unread_count':0})

@app.route('/api/notifications/read_all', methods=['POST'])
@login_required
def api_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read':True}); db.session.commit()
    return jsonify({'success':True})

@app.route('/api/notifications/clear_all', methods=['POST'])
@login_required
def api_clear_all_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete(); db.session.commit()
    return jsonify({'success':True})

@app.route('/api/notifications/<int:nid>/delete', methods=['DELETE'])
@login_required
def api_delete_notification(nid):
    n = db.session.get(Notification, nid)
    if n and n.user_id == current_user.id: db.session.delete(n); db.session.commit(); return jsonify({'success':True})
    return jsonify({'error':'Не найдено'}),404

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files: return jsonify({'error':'Нет файла'}),400
    f = request.files['file']
    if f.filename=='': return jsonify({'error':'Файл не выбран'}),400
    ext = f.filename.rsplit('.',1)[-1].lower(); fn = f"{uuid.uuid4()}.{ext}"
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
    return jsonify({'url':url_for('static', filename=f'uploads/{fn}')})

def get_local_ip():
    try: s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

def create_default_avatar():
    for name,color in [('default.png','#667eea'),('group_default.png','#48bb78')]:
        path=os.path.join(app.config['UPLOAD_FOLDER'],name)
        if not os.path.exists(path):
            try:
                from PIL import Image,ImageDraw
                img=Image.new('RGB',(300,300),color); d=ImageDraw.Draw(img)
                if name=='default.png': d.ellipse((100,80,200,180),fill='white'); d.ellipse((75,200,225,280),fill='white')
                else: d.ellipse((80,80,140,140),fill='white'); d.ellipse((160,80,220,140),fill='white'); d.ellipse((120,160,180,220),fill='white')
                img.save(path)
            except: pass

if __name__=='__main__':
    with app.app_context():
        db.create_all()
        create_default_avatar()
        create_favicon()
        print("База создана")
    ip=get_local_ip()
    print(f"\nhttp://{ip}:5000\n")
    app.run(debug=True,host='0.0.0.0',port=5000)
