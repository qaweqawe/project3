let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let selectedDate = null;
let selectedEventColor = '#48bb78';
let selectedCommentColor = '#667eea';
let colorMode = false;
let selectedDays = new Set();
let currentTheme = 'light';
let currentCommentId = null;
let editingEventId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализация...');
    initYearSelect();
    loadCalendar();
    initDraggable();
    loadTheme();
});

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    currentTheme = savedTheme;
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon();
}

function toggleTheme() {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    updateThemeIcon();
    loadCalendar(); // Перезагружаем календарь для обновления прозрачности
}

function updateThemeIcon() {
    const btn = document.querySelector('.theme-toggle');
    btn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
}

function initYearSelect() {
    const select = document.getElementById('year-select');
    select.innerHTML = '';
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

    console.log('Загрузка календаря:', currentYear, currentMonth);

    try {
        const response = await fetch(`/get_calendar/${currentYear}/${currentMonth}`);
        const data = await response.json();

        console.log('Данные получены:', data);

        document.getElementById('current-month').textContent = `${data.month_name} ${data.year}`;
        renderCalendar(data.calendar);
    } catch (error) {
        console.error('Ошибка загрузки календаря:', error);
        alert('Ошибка загрузки календаря. Проверьте консоль.');
    }
}

function renderCalendar(calendarData) {
    console.log('Рендеринг календаря, данных:', calendarData);
    const tbody = document.getElementById('calendar-body');
    tbody.innerHTML = '';
    selectedDays.clear();

    if (!calendarData || calendarData.length === 0) {
        console.error('Нет данных для отображения');
        return;
    }

    calendarData.forEach((week, weekIndex) => {
        console.log(`Неделя ${weekIndex}:`, week);
        const row = document.createElement('tr');

        week.forEach((day, dayIndex) => {
            const cell = document.createElement('td');

            if (day.day === '') {
                cell.className = 'empty-day';
                // Добавляем пустой div для сохранения высоты
                const emptyDiv = document.createElement('div');
                emptyDiv.style.height = '100%';
                emptyDiv.style.minHeight = '80px';
                cell.appendChild(emptyDiv);
            } else {
                const dayDiv = document.createElement('div');
                dayDiv.className = 'day-cell';
                dayDiv.setAttribute('data-date', day.date);

                // Устанавливаем цвет фона если есть
                if (day.color) {
                    dayDiv.style.backgroundColor = hexToRgba(day.color,
                        currentTheme === 'dark' ? 0.3 : 0.15);
                }

                // Заголовок с числом и карандашом
                const header = document.createElement('div');
                header.className = 'day-header';

                const dayNumber = document.createElement('span');
                dayNumber.className = 'day-number' + (day.is_holiday ? ' holiday' : '');
                dayNumber.textContent = day.day;
                header.appendChild(dayNumber);

                const editPencil = document.createElement('span');
                editPencil.className = 'edit-pencil';
                editPencil.textContent = '✏️';
                editPencil.onclick = (e) => {
                    e.stopPropagation();
                    openEditModalDirect(day.date);
                };
                header.appendChild(editPencil);

                dayDiv.appendChild(header);

                // Праздник
                if (day.is_holiday && day.holiday_name) {
                    const holidayDiv = document.createElement('div');
                    holidayDiv.className = 'holiday-name';
                    holidayDiv.textContent = day.holiday_name;
                    dayDiv.appendChild(holidayDiv);
                }

                // События
                if (day.events && day.events.length > 0) {
                    const eventsContainer = document.createElement('div');
                    eventsContainer.className = 'events-container';

                    const maxEvents = day.events.length > 3 ? 2 : day.events.length;

                    for (let i = 0; i < maxEvents; i++) {
                        const event = day.events[i];
                        const eventTitle = document.createElement('div');
                        eventTitle.className = 'event-title';
                        eventTitle.style.backgroundColor = event.color;
                        eventTitle.textContent = event.title;
                        eventTitle.title = event.title;
                        eventsContainer.appendChild(eventTitle);
                    }

                    if (day.events.length > 3) {
                        const moreEvents = document.createElement('div');
                        moreEvents.className = 'event-title';
                        moreEvents.style.backgroundColor = '#a0aec0';
                        moreEvents.textContent = `+${day.events.length - 2} ещё`;
                        eventsContainer.appendChild(moreEvents);
                    }

                    dayDiv.appendChild(eventsContainer);
                }

                // Индикатор заметки
                if (day.has_comment) {
                    const footer = document.createElement('div');
                    footer.className = 'day-footer';
                    const commentInd = document.createElement('span');
                    commentInd.className = 'comment-indicator';
                    commentInd.style.backgroundColor = day.comment_color || '#667eea';
                    footer.appendChild(commentInd);
                    dayDiv.appendChild(footer);
                }

                dayDiv.onclick = (e) => {
                    if (!e.target.classList.contains('edit-pencil')) {
                        handleDayClick(e, day.date);
                    }
                };

                cell.appendChild(dayDiv);
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });

    console.log('Календарь отрисован');
}

function handleDayClick(event, date) {
    if (colorMode) {
        const dayCell = event.currentTarget;
        dayCell.classList.toggle('selected');

        if (selectedDays.has(date)) {
            selectedDays.delete(date);
        } else {
            selectedDays.add(date);
        }
    } else {
        openInfoModal(date);
    }
}

async function openInfoModal(date) {
    selectedDate = date;

    try {
        const response = await fetch(`/get_day_info/${date}`);
        const data = await response.json();

        document.getElementById('info-title').textContent = formatDate(date);

        const holidayInfo = document.getElementById('holiday-info');
        const eventsInfo = document.getElementById('events-info');
        const commentInfo = document.getElementById('comment-info');

        if (data.holiday) {
            holidayInfo.innerHTML = `
                <h4>🎉 Праздник</h4>
                <div class="holiday-block">${data.holiday}</div>
            `;
            holidayInfo.style.display = 'block';
        } else {
            holidayInfo.innerHTML = '';
            holidayInfo.style.display = 'none';
        }

        if (data.events && data.events.length > 0) {
            let eventsHtml = '<h4>📌 События</h4>';
            data.events.forEach(event => {
                eventsHtml += `
                    <div class="event-info-item" style="border-left-color: ${event.color}">
                        <div class="event-info-header">
                            <div class="event-info-title">${event.title}</div>
                            <div class="event-actions">
                                <button class="event-edit-btn" onclick="editEvent(${event.id})" title="Редактировать">✏️</button>
                                <button class="event-delete-btn" onclick="deleteEventFromInfo(${event.id})" title="Удалить">🗑️</button>
                            </div>
                        </div>
                        ${event.description ? `<div class="event-info-description">${event.description}</div>` : ''}
                    </div>
                `;
            });
            eventsInfo.innerHTML = eventsHtml;
        } else {
            eventsInfo.innerHTML = '<h4>📌 События</h4><p style="color: var(--text-secondary);">Нет событий</p>';
        }

        if (data.comment) {
            commentInfo.innerHTML = `
                <h4>📝 Заметка</h4>
                <div class="comment-block" style="border-left-color: ${data.comment.color}">${data.comment.text}</div>
            `;
            currentCommentId = data.comment.id;
        } else {
            commentInfo.innerHTML = '<h4>📝 Заметка</h4><p style="color: var(--text-secondary);">Нет заметок</p>';
            currentCommentId = null;
        }

        const modal = document.getElementById('info-modal');
        modal.style.display = 'block';

        const modalContent = modal.querySelector('.modal-content');
        modalContent.style.left = (window.innerWidth - 450) / 2 + 'px';
        modalContent.style.top = (window.innerHeight - 400) / 2 + 'px';
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

function openEditModal() {
    closeInfoModal();
    openEditModalDirect(selectedDate);
}

async function openEditModalDirect(date) {
    selectedDate = date;

    try {
        const response = await fetch(`/get_comment/${date}`);
        const data = await response.json();

        document.getElementById('comment-text').value = data.text || '';
        document.getElementById('comment-color').value = data.color || '#667eea';
        selectedCommentColor = data.color || '#667eea';
        currentCommentId = data.id;

        document.querySelectorAll('#note-tab .color-option').forEach(opt => {
            opt.classList.remove('selected');
            if (opt.style.backgroundColor === selectedCommentColor) {
                opt.classList.add('selected');
            }
        });

        const deleteBtn = document.getElementById('delete-comment-btn');
        if (data.id) {
            deleteBtn.style.display = 'block';
        } else {
            deleteBtn.style.display = 'none';
        }

        document.getElementById('edit-title').textContent = formatDate(date);

        await loadEventsList(date);

        const modal = document.getElementById('edit-modal');
        modal.style.display = 'block';

        const modalContent = modal.querySelector('.modal-content');
        modalContent.style.left = (window.innerWidth - 450) / 2 + 'px';
        modalContent.style.top = (window.innerHeight - 400) / 2 + 'px';
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const months = ['Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня',
                    'Июля', 'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря'];
    return `${day} ${months[parseInt(month) - 1]} ${year}`;
}

function closeInfoModal() {
    document.getElementById('info-modal').style.display = 'none';
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
    selectedDate = null;
    editingEventId = null;
    document.getElementById('editing-event-id').value = '';
    document.getElementById('save-event-btn').textContent = '➕ Добавить событие';
    document.getElementById('cancel-edit-btn').style.display = 'none';
}

function hexToRgba(hex, alpha) {
    if (!hex) return 'transparent';
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function toggleColorMode() {
    colorMode = !colorMode;
    const btn = document.getElementById('colorModeBtn');
    const applyBtn = document.getElementById('applyColorBtn');

    if (colorMode) {
        btn.textContent = '✅ Выбор';
        applyBtn.style.display = 'inline-block';
        selectedDays.clear();
        document.querySelectorAll('.day-cell').forEach(cell => {
            cell.classList.remove('selected');
        });
    } else {
        btn.textContent = '🎨 Выбрать дни';
        applyBtn.style.display = 'none';
        selectedDays.clear();
        document.querySelectorAll('.day-cell').forEach(cell => {
            cell.classList.remove('selected');
        });
    }
}

async function applyColorToSelected() {
    if (selectedDays.size === 0) {
        alert('Выберите дни для окрашивания!');
        return;
    }

    const color = document.getElementById('day-color').value;

    try {
        const response = await fetch('/set_day_color', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                dates: Array.from(selectedDays),
                color: color
            })
        });

        const data = await response.json();
        if (data.success) {
            toggleColorMode();
            loadCalendar();
        } else {
            alert('Ошибка: ' + data.error);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при применении цвета');
    }
}

async function clearSelectedColors() {
    if (selectedDays.size === 0) {
        alert('Выберите дни для очистки!');
        return;
    }

    if (!confirm('Очистить цвета для выбранных дней?')) return;

    try {
        const response = await fetch('/set_day_color', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                dates: Array.from(selectedDays),
                color: ''
            })
        });

        const data = await response.json();
        if (data.success) {
            if (colorMode) toggleColorMode();
            loadCalendar();
        }
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

async function saveComment() {
    const text = document.getElementById('comment-text').value;
    const color = document.getElementById('comment-color').value;

    try {
        const response = await fetch('/save_comment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                date: selectedDate,
                text: text,
                color: color,
                id: currentCommentId
            })
        });

        const data = await response.json();
        if (data.success) {
            closeEditModal();
            loadCalendar();
        } else {
            alert('Ошибка сохранения: ' + data.error);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при сохранении');
    }
}

async function deleteComment() {
    if (!currentCommentId) return;
    if (!confirm('Удалить заметку?')) return;

    try {
        const response = await fetch(`/delete_comment/${currentCommentId}`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.success) {
            closeEditModal();
            loadCalendar();
        } else {
            alert('Ошибка удаления: ' + data.error);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении');
    }
}

async function saveEvent() {
    const title = document.getElementById('event-title').value;
    const description = document.getElementById('event-description').value;
    const color = document.getElementById('event-color').value;
    const eventId = document.getElementById('editing-event-id').value;

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
                color: color,
                id: eventId || null
            })
        });

        const data = await response.json();
        if (data.success) {
            document.getElementById('event-title').value = '';
            document.getElementById('event-description').value = '';
            document.getElementById('editing-event-id').value = '';
            document.getElementById('save-event-btn').textContent = '➕ Добавить событие';
            document.getElementById('cancel-edit-btn').style.display = 'none';
            editingEventId = null;

            await loadEventsList(selectedDate);
            loadCalendar();
        } else {
            alert('Ошибка: ' + data.error);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при сохранении события');
    }
}

async function editEvent(eventId) {
    try {
        const response = await fetch(`/get_event/${eventId}`);
        const event = await response.json();

        closeInfoModal();
        await openEditModalDirect(event.date);

        setTimeout(() => {
            switchTab('event');
            document.getElementById('event-title').value = event.title;
            document.getElementById('event-description').value = event.description || '';
            document.getElementById('event-color').value = event.color;
            document.getElementById('editing-event-id').value = event.id;
            selectedEventColor = event.color;

            document.querySelectorAll('#event-tab .color-option').forEach(opt => {
                opt.classList.remove('selected');
                if (opt.style.backgroundColor === event.color) {
                    opt.classList.add('selected');
                }
            });

            document.getElementById('save-event-btn').textContent = '💾 Обновить событие';
            document.getElementById('cancel-edit-btn').style.display = 'block';
            editingEventId = event.id;
        }, 100);

    } catch (error) {
        console.error('Ошибка загрузки события:', error);
    }
}

function cancelEditEvent() {
    document.getElementById('event-title').value = '';
    document.getElementById('event-description').value = '';
    document.getElementById('editing-event-id').value = '';
    document.getElementById('save-event-btn').textContent = '➕ Добавить событие';
    document.getElementById('cancel-edit-btn').style.display = 'none';
    editingEventId = null;
}

async function deleteEvent(eventId) {
    if (!confirm('Удалить событие?')) return;

    try {
        await fetch(`/delete_event/${eventId}`, {method: 'DELETE'});
        await loadEventsList(selectedDate);
        loadCalendar();
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

async function deleteEventFromInfo(eventId) {
    if (!confirm('Удалить событие?')) return;

    try {
        await fetch(`/delete_event/${eventId}`, {method: 'DELETE'});
        closeInfoModal();
        loadCalendar();
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

async function loadEventsList(date) {
    try {
        const response = await fetch(`/get_events/${date}`);
        const events = await response.json();

        const eventsList = document.getElementById('events-list');

        if (events.length > 0) {
            let html = '<h4 style="margin-bottom: 10px;">Существующие события:</h4>';
            events.forEach(event => {
                html += `
                    <div class="event-item" style="border-left-color: ${event.color}">
                        <div class="event-item-header">
                            <div class="event-item-title">${event.title}</div>
                            <div class="event-item-actions">
                                <button class="btn-icon" onclick="editEvent(${event.id})" title="Редактировать">✏️</button>
                                <button class="btn-icon" onclick="deleteEvent(${event.id})" title="Удалить">🗑️</button>
                            </div>
                        </div>
                        ${event.description ? `<div class="event-item-description">${event.description}</div>` : ''}
                    </div>
                `;
            });
            eventsList.innerHTML = html;
        } else {
            eventsList.innerHTML = '<p style="color: var(--text-secondary);">Нет событий</p>';
        }
    } catch (error) {
        console.error('Ошибка загрузки событий:', error);
    }
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.textContent.includes(tab === 'note' ? 'Заметка' : 'Событие')) {
            btn.classList.add('active');
        }
    });

    document.getElementById(`${tab}-tab`).classList.add('active');
}

function selectEventColor(color) {
    selectedEventColor = color;
    document.getElementById('event-color').value = color;

    document.querySelectorAll('#event-tab .color-option').forEach(opt => {
        opt.classList.remove('selected');
        if (opt.style.backgroundColor === color) {
            opt.classList.add('selected');
        }
    });
}

function selectCommentColor(color) {
    selectedCommentColor = color;
    document.getElementById('comment-color').value = color;

    document.querySelectorAll('#note-tab .color-option').forEach(opt => {
        opt.classList.remove('selected');
        if (opt.style.backgroundColor === color) {
            opt.classList.add('selected');
        }
    });
}

function initDraggable() {
    ['info-modal', 'edit-modal'].forEach(modalId => {
        const modal = document.getElementById(modalId);
        const modalContent = modal.querySelector('.modal-content');
        const modalHeader = modal.querySelector('.modal-header');

        let isDragging = false;
        let currentX, currentY, initialX, initialY;

        modalHeader.onmousedown = (e) => {
            if (e.target.classList.contains('edit-pencil') ||
                e.target.classList.contains('modal-close') ||
                e.target.classList.contains('edit-btn')) return;

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
    });
}

window.onclick = function(event) {
    const infoModal = document.getElementById('info-modal');
    const editModal = document.getElementById('edit-modal');

    if (event.target === infoModal) {
        closeInfoModal();
    }
    if (event.target === editModal) {
        closeEditModal();
    }
}

// Для отладки
console.log('Script.js загружен');