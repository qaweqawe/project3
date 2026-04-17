let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let selectedDate = null;
let selectedEventColor = '#667eea';

document.addEventListener('DOMContentLoaded', function() {
    initYearSelect();
    loadCalendar();
    initDraggable();
});

function initYearSelect() {
    const select = document.getElementById('year-select');
    for (let year = 2010; year <= 2044; year++) {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        if (year === currentYear) option.selected = true;
        select.appendChild(option);
    }
    document.getElementById('month-select').value = currentMonth;
}

async function loadCalendar() {
    currentYear = parseInt(document.getElementById('year-select').value);
    currentMonth = parseInt(document.getElementById('month-select').value);
    
    try {
        const response = await fetch(`/get_calendar/${currentYear}/${currentMonth}`);
        const data = await response.json();
        
        document.getElementById('current-month').textContent = `${data.month_name} ${data.year}`;
        renderCalendar(data.calendar);
    } catch (error) {
        console.error('Ошибка загрузки календаря:', error);
    }
}

function renderCalendar(calendarData) {
    const tbody = document.getElementById('calendar-body');
    tbody.innerHTML = '';
    
    calendarData.forEach(week => {
        const row = document.createElement('tr');
        
        week.forEach(day => {
            const cell = document.createElement('td');
            
            if (day.day === '') {
                cell.className = 'empty-day';
            } else {
                const dayDiv = document.createElement('div');
                dayDiv.className = 'day-cell';
                dayDiv.setAttribute('data-date', day.date);
                
                if (day.color !== 'white') {
                    dayDiv.style.backgroundColor = hexToRgba(day.color, 0.15);
                }
                
                const dayNumber = document.createElement('div');
                dayNumber.className = 'day-number' + (day.is_holiday ? ' holiday' : '');
                dayNumber.textContent = day.day;
                dayDiv.appendChild(dayNumber);
                
                if (day.is_holiday) {
                    const holidayDiv = document.createElement('div');
                    holidayDiv.className = 'holiday-name';
                    holidayDiv.textContent = day.holiday_name;
                    dayDiv.appendChild(holidayDiv);
                }
                
                if (day.memorable_name) {
                    const memorableDiv = document.createElement('div');
                    memorableDiv.className = 'memorable-name';
                    memorableDiv.textContent = day.memorable_name;
                    dayDiv.appendChild(memorableDiv);
                }
                
                if (day.has_comment) {
                    const commentIndicator = document.createElement('div');
                    commentIndicator.className = 'comment-indicator';
                    commentIndicator.textContent = '📝';
                    commentIndicator.style.fontSize = '12px';
                    dayDiv.appendChild(commentIndicator);
                }
                
                dayDiv.onclick = () => openCommentModal(day.date);
                cell.appendChild(dayDiv);
            }
            
            row.appendChild(cell);
        });
        
        tbody.appendChild(row);
    });
}

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function openCommentModal(date) {
    selectedDate = date;
    
    try {
        const response = await fetch(`/get_comment/${date}`);
        const data = await response.json();
        
        document.getElementById('comment-text').value = data.text;
        document.getElementById('modal-title').textContent = formatDate(date);
        
        // Загружаем события
        await loadEvents(date);
        
        const modal = document.getElementById('comment-modal');
        modal.style.display = 'block';
        
        const modalContent = modal.querySelector('.modal-content');
        modalContent.style.left = (window.innerWidth - 500) / 2 + 'px';
        modalContent.style.top = (window.innerHeight - 400) / 2 + 'px';
    } catch (error) {
        console.error('Ошибка открытия модального окна:', error);
    }
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const months = ['Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня',
                    'Июля', 'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря'];
    return `${day} ${months[parseInt(month) - 1]} ${year}`;
}

function closeModal() {
    document.getElementById('comment-modal').style.display = 'none';
}

async function saveComment() {
    const text = document.getElementById('comment-text').value;
    
    try {
        const response = await fetch('/save_comment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({date: selectedDate, text: text})
        });
        
        const data = await response.json();
        if (data.success) {
            closeModal();
            loadCalendar();
        }
    } catch (error) {
        console.error('Ошибка сохранения:', error);
    }
}

async function saveEvent() {
    const title = document.getElementById('event-title').value;
    const description = document.getElementById('event-description').value;
    
    if (!title) {
        alert('Введите название события');
        return;
    }
    
    try {
        const response = await fetch('/save_event', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                date: selectedDate,
                title: title,
                description: description,
                color: selectedEventColor
            })
        });
        
        const data = await response.json();
        if (data.success) {
            document.getElementById('event-title').value = '';
            document.getElementById('event-description').value = '';
            await loadEvents(selectedDate);
            loadCalendar();
        }
    } catch (error) {
        console.error('Ошибка сохранения события:', error);
    }
}

async function loadEvents(date) {
    try {
        const response = await fetch(`/get_events/${date}`);
        const events = await response.json();
        
        const eventsList = document.getElementById('events-list');
        eventsList.innerHTML = '<h4>События:</h4>';
        
        events.forEach(event => {
            const eventDiv = document.createElement('div');
            eventDiv.className = 'event-item';
            eventDiv.style.borderLeft = `4px solid ${event.color}`;
            eventDiv.innerHTML = `
                <strong>${event.title}</strong>
                <p>${event.description || ''}</p>
                <button onclick="deleteEvent(${event.id})" class="btn-small">Удалить</button>
            `;
            eventsList.appendChild(eventDiv);
        });
    } catch (error) {
        console.error('Ошибка загрузки событий:', error);
    }
}

async function deleteEvent(eventId) {
    if (!confirm('Удалить событие?')) return;
    
    try {
        await fetch(`/delete_event/${eventId}`, {method: 'DELETE'});
        await loadEvents(selectedDate);
        loadCalendar();
    } catch (error) {
        console.error('Ошибка удаления:', error);
    }
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(`${tab}-tab`).classList.add('active');
}

function selectEventColor(color) {
    selectedEventColor = color;
    document.getElementById('event-color').value = color;
    
    document.querySelectorAll('.color-option').forEach(opt => {
        opt.classList.remove('selected');
        if (opt.style.backgroundColor === color) {
            opt.classList.add('selected');
        }
    });
}

async function applyColorToDays() {
    const color = document.getElementById('day-color').value;
    const dayCells = document.querySelectorAll('.day-cell');
    let applied = 0;
    
    for (const cell of dayCells) {
        const date = cell.getAttribute('data-date');
        if (date) {
            await fetch('/set_day_color', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({date: date, color: color})
            });
            applied++;
        }
    }
    
    if (applied > 0) {
        loadCalendar();
        alert(`Цвет применен к ${applied} дням`);
    }
}

async function clearColors() {
    if (!confirm('Очистить все цвета?')) return;
    
    const dayCells = document.querySelectorAll('.day-cell');
    
    for (const cell of dayCells) {
        const date = cell.getAttribute('data-date');
        if (date) {
            await fetch('/set_day_color', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({date: date, color: 'white'})
            });
        }
    }
    
    loadCalendar();
}

function initDraggable() {
    const modal = document.getElementById('comment-modal');
    const modalContent = modal.querySelector('.modal-content');
    const modalHeader = modal.querySelector('.modal-header');
    
    let isDragging = false;
    let currentX, currentY, initialX, initialY;
    
    modalHeader.onmousedown = (e) => {
        isDragging = true;
        initialX = e.clientX;
        initialY = e.clientY;
        
        const rect = modalContent.getBoundingClientRect();
        currentX = rect.left;
        currentY = rect.top;
    };
    
    document.onmousemove = (e) => {
        if (!isDragging) return;
        
        e.preventDefault();
        const dx = e.clientX - initialX;
        const dy = e.clientY - initialY;
        
        modalContent.style.left = (currentX + dx) + 'px';
        modalContent.style.top = (currentY + dy) + 'px';
    };
    
    document.onmouseup = () => {
        isDragging = false;
    };
}

window.onclick = function(event) {
    const modal = document.getElementById('comment-modal');
    if (event.target === modal) {
        closeModal();
    }
}