from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import calendar
from sqlalchemy import select, inspect
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calendar.db'
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(20), default='#667eea')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


class DayColor(db.Model):
    __tablename__ = 'day_colors'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True, index=True)
    color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#48bb78')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


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


def init_db():
    with app.app_context():
        inspector = inspect(db.engine)

        if not inspector.has_table('comments'):
            db.create_all()
            print("База данных создана заново")
        else:
            columns = [col['name'] for col in inspector.get_columns('comments')]
            if 'color' not in columns:
                print("Добавляем колонку color в таблицу comments")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE comments ADD COLUMN color VARCHAR(20) DEFAULT "#667eea"'))
                    conn.commit()

            columns = [col['name'] for col in inspector.get_columns('events')]
            if 'updated_at' not in columns:
                print("Добавляем колонку updated_at в таблицу events")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE events ADD COLUMN updated_at DATETIME'))
                    conn.commit()


def get_month_calendar(year, month):
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

                # Получаем цвет дня
                day_color = db.session.execute(
                    select(DayColor).filter_by(date=date_str)
                ).scalar_one_or_none()
                color = day_color.color if day_color else ''

                # Получаем комментарий с цветом
                comment = db.session.execute(
                    select(Comment).filter_by(date=date_str)
                ).scalar_one_or_none()
                has_comment = comment is not None and comment.text.strip() != ''
                comment_color = comment.color if comment else '#667eea'

                # Получаем события
                events = db.session.execute(
                    select(Event).filter_by(date=date_str).order_by(Event.created_at.desc())
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


@app.route('/')
def index():
    current_year = datetime.now().year
    current_month = datetime.now().month
    return render_template('index.html',
                           current_year=current_year,
                           current_month=current_month)


@app.route('/get_calendar/<int:year>/<int:month>')
def get_calendar(year, month):
    month_names = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]

    try:
        calendar_data = get_month_calendar(year, month)

        return jsonify({
            'year': year,
            'month': month,
            'month_name': month_names[month - 1],
            'calendar': calendar_data
        })
    except Exception as e:
        print(f"Ошибка в get_calendar: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_day_info/<date>')
def get_day_info(date):
    month_day = date[5:]

    holiday = RUSSIAN_HOLIDAYS.get(month_day, '')

    comment = db.session.execute(
        select(Comment).filter_by(date=date)
    ).scalar_one_or_none()

    events = db.session.execute(
        select(Event).filter_by(date=date).order_by(Event.created_at.desc())
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
def get_comment(date):
    comment = db.session.execute(
        select(Comment).filter_by(date=date)
    ).scalar_one_or_none()

    return jsonify({
        'id': comment.id if comment else None,
        'text': comment.text if comment else '',
        'color': comment.color if comment else '#667eea'
    })


@app.route('/save_comment', methods=['POST'])
def save_comment():
    try:
        data = request.json
        date = data['date']
        text = data['text']
        color = data.get('color', '#667eea')
        comment_id = data.get('id')

        if comment_id:
            comment = db.session.get(Comment, comment_id)
            if comment:
                comment.text = text
                comment.color = color
                comment.updated_at = datetime.now(timezone.utc)
        else:
            comment = Comment(date=date, text=text, color=color)
            db.session.add(comment)

        db.session.commit()
        return jsonify({'success': True, 'id': comment.id if comment else comment_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_comment/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    try:
        comment = db.session.get(Comment, comment_id)
        if comment:
            db.session.delete(comment)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Заметка не найдена'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set_day_color', methods=['POST'])
def set_day_color():
    try:
        data = request.json
        dates = data['dates']
        color = data['color']

        for date in dates:
            day_color = db.session.execute(
                select(DayColor).filter_by(date=date)
            ).scalar_one_or_none()

            if day_color:
                if color:
                    day_color.color = color
                else:
                    db.session.delete(day_color)
            elif color:
                day_color = DayColor(date=date, color=color)
                db.session.add(day_color)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save_event', methods=['POST'])
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
            if event:
                event.title = title
                event.description = description
                event.color = color
                event.updated_at = datetime.now(timezone.utc)
        else:
            event = Event(
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
def get_events(date):
    events = db.session.execute(
        select(Event).filter_by(date=date).order_by(Event.created_at.desc())
    ).scalars().all()

    return jsonify([{
        'id': e.id,
        'title': e.title,
        'description': e.description,
        'color': e.color
    } for e in events])


@app.route('/get_event/<int:event_id>')
def get_event(event_id):
    event = db.session.get(Event, event_id)
    if event:
        return jsonify({
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'color': event.color,
            'date': event.date
        })
    return jsonify({'error': 'Событие не найдено'}), 404


@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if event:
            db.session.delete(event)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Событие не найдено'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    db_path = 'calendar.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Старая база данных удалена")

    with app.app_context():
        db.create_all()
        print("Новая база данных создана")

    app.run(debug=True, port=5000)