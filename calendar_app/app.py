from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timezone
import calendar
from sqlalchemy import select
import os
import socket
import traceback

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calendar.db'
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к календарю.'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(20), default='light')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    comments = db.relationship('Comment', backref='user', lazy=True, cascade='all, delete-orphan')
    day_colors = db.relationship('DayColor', backref='user', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('Event', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(20), default='#667eea')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


class DayColor(db.Model):
    __tablename__ = 'day_colors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False, index=True)
    color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#48bb78')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


RUSSIAN_HOLIDAYS = {
    '01-01': 'Новый год',
    '01-02': 'Новогодние каникулы',
    '01-03': 'Новогодние каникулы',
    '01-04': 'Новогодние каникулы',
    '01-05': 'Новогодние каникулы',
    '01-06': 'Новогодние каникулы',
    '01-07': 'Рождество',
    '01-08': 'Новогодние каникулы',
    '02-23': 'День защитника',
    '03-08': '8 марта',
    '05-01': '1 мая',
    '05-09': 'День Победы',
    '06-12': 'День России',
    '11-04': 'День единства'
}


def get_month_calendar(user_id, year, month):
    try:
        cal = calendar.monthcalendar(year, month)
        month_days = []

        for week in cal:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append({'day': '', 'is_holiday': False})
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    month_day_str = f"{month:02d}-{day:02d}"

                    is_holiday = month_day_str in RUSSIAN_HOLIDAYS
                    holiday_name = RUSSIAN_HOLIDAYS.get(month_day_str, '')

                    day_color = db.session.execute(
                        select(DayColor).filter_by(user_id=user_id, date=date_str)
                    ).scalar_one_or_none()
                    color = day_color.color if day_color else ''

                    comment = db.session.execute(
                        select(Comment).filter_by(user_id=user_id, date=date_str)
                    ).scalar_one_or_none()
                    has_comment = comment is not None and comment.text.strip() != ''
                    comment_color = comment.color if comment else '#667eea'

                    events = db.session.execute(
                        select(Event).filter_by(user_id=user_id, date=date_str).order_by(Event.created_at.desc())
                    ).scalars().all()

                    week_days.append({
                        'day': day,
                        'date': date_str,
                        'is_holiday': is_holiday,
                        'holiday_name': holiday_name,
                        'color': color,
                        'has_comment': has_comment,
                        'comment_color': comment_color,
                        'events': [{'id': e.id, 'title': e.title, 'color': e.color} for e in events]
                    })
            month_days.append(week_days)

        return month_days
    except Exception as e:
        print(f"Ошибка в get_month_calendar: {e}")
        traceback.print_exc()
        raise e

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Пользователь уже существует'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email уже используется'}), 400

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return jsonify({'success': True, 'theme': user.theme})

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        remember = data.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            return jsonify({'success': True, 'theme': user.theme})

        return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'}), 401

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/update_theme', methods=['POST'])
@login_required
def update_theme():
    data = request.json
    theme = data.get('theme', 'light')
    current_user.theme = theme
    db.session.commit()
    return jsonify({'success': True})


# Главная страница (требует авторизации)
@app.route('/')
@login_required
def index():
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_day = datetime.now().day
    return render_template('index.html',
                           current_year=current_year,
                           current_month=current_month,
                           current_day=current_day,
                           user=current_user)


@app.route('/get_calendar/<int:year>/<int:month>')
@login_required
def get_calendar(year, month):
    try:
        month_names = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]

        print(f"Запрос календаря: год={year}, месяц={month}, пользователь={current_user.id}")

        calendar_data = get_month_calendar(current_user.id, year, month)
        today = datetime.now()
        today_str = f"{today.year}-{today.month:02d}-{today.day:02d}"

        response_data = {
            'year': year,
            'month': month,
            'month_name': month_names[month - 1],
            'calendar': calendar_data,
            'today': today_str
        }

        print(f"Отправка данных: {len(calendar_data)} недель")
        return jsonify(response_data)
    except Exception as e:
        print(f"Ошибка в get_calendar: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/get_day_info/<date>')
@login_required
def get_day_info(date):
    month_day = date[5:]
    holiday = RUSSIAN_HOLIDAYS.get(month_day, '')

    comment = db.session.execute(
        select(Comment).filter_by(user_id=current_user.id, date=date)
    ).scalar_one_or_none()

    events = db.session.execute(
        select(Event).filter_by(user_id=current_user.id, date=date).order_by(Event.created_at.desc())
    ).scalars().all()

    return jsonify({
        'date': date,
        'holiday': holiday,
        'comment': {
            'id': comment.id if comment else None,
            'text': comment.text if comment else '',
            'color': comment.color if comment else '#667eea'
        } if comment else None,
        'events': [{
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'color': e.color
        } for e in events]
    })


@app.route('/get_comment/<date>')
@login_required
def get_comment(date):
    comment = db.session.execute(
        select(Comment).filter_by(user_id=current_user.id, date=date)
    ).scalar_one_or_none()

    return jsonify({
        'id': comment.id if comment else None,
        'text': comment.text if comment else '',
        'color': comment.color if comment else '#667eea'
    })


@app.route('/save_comment', methods=['POST'])
@login_required
def save_comment():
    try:
        data = request.json
        date = data['date']
        text = data['text']
        color = data.get('color', '#667eea')
        comment_id = data.get('id')

        if comment_id:
            comment = db.session.get(Comment, comment_id)
            if comment and comment.user_id == current_user.id:
                comment.text = text
                comment.color = color
                comment.updated_at = datetime.now(timezone.utc)
        else:
            comment = Comment(user_id=current_user.id, date=date, text=text, color=color)
            db.session.add(comment)

        db.session.commit()
        return jsonify({'success': True, 'id': comment.id if comment else comment_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    try:
        comment = db.session.get(Comment, comment_id)
        if comment and comment.user_id == current_user.id:
            db.session.delete(comment)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Заметка не найдена'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set_day_color', methods=['POST'])
@login_required
def set_day_color():
    try:
        data = request.json
        dates = data['dates']
        color = data['color']

        for date in dates:
            day_color = db.session.execute(
                select(DayColor).filter_by(user_id=current_user.id, date=date)
            ).scalar_one_or_none()

            if day_color:
                if color:
                    day_color.color = color
                else:
                    db.session.delete(day_color)
            elif color:
                day_color = DayColor(user_id=current_user.id, date=date, color=color)
                db.session.add(day_color)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save_event', methods=['POST'])
@login_required
def save_event():
    try:
        data = request.json
        date = data['date']
        title = data['title']
        description = data.get('description', '')
        color = data.get('color', '#48bb78')
        event_id = data.get('id')

        if event_id:
            event = db.session.get(Event, event_id)
            if event and event.user_id == current_user.id:
                event.title = title
                event.description = description
                event.color = color
                event.updated_at = datetime.now(timezone.utc)
        else:
            event = Event(
                user_id=current_user.id,
                date=date,
                title=title,
                description=description,
                color=color
            )
            db.session.add(event)

        db.session.commit()
        return jsonify({'success': True, 'event_id': event.id if event else event_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get_events/<date>')
@login_required
def get_events(date):
    events = db.session.execute(
        select(Event).filter_by(user_id=current_user.id, date=date).order_by(Event.created_at.desc())
    ).scalars().all()

    return jsonify([{
        'id': e.id,
        'title': e.title,
        'description': e.description,
        'color': e.color
    } for e in events])


@app.route('/get_event/<int:event_id>')
@login_required
def get_event(event_id):
    event = db.session.get(Event, event_id)
    if event and event.user_id == current_user.id:
        return jsonify({
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'color': event.color,
            'date': event.date
        })
    return jsonify({'error': 'Событие не найдено'}), 404


@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if event and event.user_id == current_user.id:
            db.session.delete(event)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Событие не найдено'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ База данных инициализирована")

        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Таблицы в базе: {tables}")

    local_ip = get_local_ip()

    print("\n" + "=" * 70)
    print("🚀 СЕРВЕР КАЛЕНДАРЯ ЗАПУЩЕН!")
    print("=" * 70)
    print(f"\n📍 Локальный доступ: http://127.0.0.1:5000")
    print(f"🌐 Локальная сеть: http://{local_ip}:5000")
    print("\n💡 Для остановки сервера нажмите Ctrl+C")
    print("=" * 70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
