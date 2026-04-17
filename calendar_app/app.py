from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import calendar
from sqlalchemy import select, update, delete

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calendar.db'
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Модель для хранения комментариев
class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


# Модель для хранения цветов дней
class DayColor(db.Model):
    __tablename__ = 'day_colors'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True, index=True)
    color = db.Column(db.String(20), default='white')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# Модель для событий
class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#667eea')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# Государственные праздники РФ
RUSSIAN_HOLIDAYS = {
    # Январь
    '01-01': 'Новый год',
    '01-02': 'Новогодние каникулы',
    '01-03': 'Новогодние каникулы',
    '01-04': 'Новогодние каникулы',
    '01-05': 'Новогодние каникулы',
    '01-06': 'Новогодние каникулы',
    '01-07': 'Рождество Христово',
    '01-08': 'Новогодние каникулы',
    # Февраль
    '02-23': 'День защитника Отечества',
    # Март
    '03-08': 'Международный женский день',
    # Май
    '05-01': 'Праздник Весны и Труда',
    '05-09': 'День Победы',
    # Июнь
    '06-12': 'День России',
    # Ноябрь
    '11-04': 'День народного единства'
}

# Памятные даты
MEMORABLE_DATES = {
    '01-25': 'Татьянин день',
    '02-14': 'День всех влюбленных',
    '02-21': 'День родного языка',
    '03-27': 'День театра',
    '04-12': 'День космонавтики',
    '05-18': 'День музеев',
    '06-01': 'День защиты детей',
    '06-06': 'Пушкинский день',
    '07-08': 'День семьи',
    '08-22': 'День флага РФ',
    '09-01': 'День знаний',
    '10-05': 'День учителя',
    '11-27': 'День матери',
    '12-12': 'День Конституции',
}


def get_month_calendar(year, month):
    """Генерирует календарь на указанный месяц"""
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

                # Проверяем праздники
                is_holiday = month_day_str in RUSSIAN_HOLIDAYS
                holiday_name = RUSSIAN_HOLIDAYS.get(month_day_str, '')

                # Проверяем памятные даты
                memorable_name = MEMORABLE_DATES.get(month_day_str, '')

                # Получаем цвет дня (используем SQLAlchemy 2.0 стиль)
                day_color = db.session.execute(
                    select(DayColor).filter_by(date=date_str)
                ).scalar_one_or_none()
                color = day_color.color if day_color else 'white'

                # Получаем комментарий
                comment = db.session.execute(
                    select(Comment).filter_by(date=date_str)
                ).scalar_one_or_none()
                has_comment = comment is not None and comment.text.strip() != ''

                # Получаем события на день
                events = db.session.execute(
                    select(Event).filter_by(date=date_str).order_by(Event.created_at.desc())
                ).scalars().all()

                week_days.append({
                    'day': day,
                    'date': date_str,
                    'is_holiday': is_holiday,
                    'holiday_name': holiday_name,
                    'memorable_name': memorable_name,
                    'color': color,
                    'has_comment': has_comment,
                    'events': [{'id': e.id, 'title': e.title, 'color': e.color} for e in events[:3]]
                })
        month_days.append(week_days)

    return month_days


@app.route('/')
def index():
    """Главная страница"""
    current_year = datetime.now().year
    current_month = datetime.now().month
    return render_template('index.html',
                           current_year=current_year,
                           current_month=current_month)


@app.route('/get_calendar/<int:year>/<int:month>')
def get_calendar(year, month):
    """API endpoint для получения данных календаря"""
    month_names = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]

    calendar_data = get_month_calendar(year, month)

    return jsonify({
        'year': year,
        'month': month,
        'month_name': month_names[month - 1],
        'calendar': calendar_data
    })


@app.route('/get_comment/<date>')
def get_comment(date):
    """Получение комментария для конкретной даты"""
    comment = db.session.execute(
        select(Comment).filter_by(date=date)
    ).scalar_one_or_none()

    return jsonify({
        'text': comment.text if comment else '',
        'color': comment.color if comment else 'white'
    })


@app.route('/save_comment', methods=['POST'])
def save_comment():
    """Сохранение комментария"""
    data = request.json
    date = data['date']
    text = data['text']

    comment = db.session.execute(
        select(Comment).filter_by(date=date)
    ).scalar_one_or_none()

    if comment:
        comment.text = text
        comment.updated_at = datetime.now(timezone.utc)
    else:
        comment = Comment(date=date, text=text, color='white')
        db.session.add(comment)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Комментарий сохранен'})


@app.route('/set_day_color', methods=['POST'])
def set_day_color():
    """Установка цвета для дня"""
    data = request.json
    date = data['date']
    color = data['color']

    day_color = db.session.execute(
        select(DayColor).filter_by(date=date)
    ).scalar_one_or_none()

    if day_color:
        day_color.color = color
    else:
        day_color = DayColor(date=date, color=color)
        db.session.add(day_color)

    db.session.commit()
    return jsonify({'success': True})


@app.route('/save_event', methods=['POST'])
def save_event():
    """Сохранение события"""
    data = request.json
    date = data['date']
    title = data['title']
    description = data.get('description', '')
    color = data.get('color', '#667eea')

    event = Event(
        date=date,
        title=title,
        description=description,
        color=color
    )
    db.session.add(event)
    db.session.commit()

    return jsonify({'success': True, 'event_id': event.id})


@app.route('/get_events/<date>')
def get_events(date):
    """Получение событий на конкретную дату"""
    events = db.session.execute(
        select(Event).filter_by(date=date).order_by(Event.created_at.desc())
    ).scalars().all()

    return jsonify([{
        'id': e.id,
        'title': e.title,
        'description': e.description,
        'color': e.color
    } for e in events])


@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Удаление события"""
    event = db.session.get(Event, event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Событие не найдено'}), 404


@app.route('/get_holidays/<int:year>')
def get_holidays(year):
    """Получение списка праздников на год"""
    holidays = []

    # Добавляем государственные праздники
    for month_day, name in RUSSIAN_HOLIDAYS.items():
        month, day = month_day.split('-')
        date_str = f"{year}-{month}-{day}"
        holidays.append({
            'date': date_str,
            'name': name,
            'type': 'holiday'
        })

    # Добавляем памятные даты
    for month_day, name in MEMORABLE_DATES.items():
        month, day = month_day.split('-')
        date_str = f"{year}-{month}-{day}"
        holidays.append({
            'date': date_str,
            'name': name,
            'type': 'memorable'
        })

    return jsonify(holidays)


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Ресурс не найден'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)