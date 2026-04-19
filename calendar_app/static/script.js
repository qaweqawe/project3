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
let todayDate = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-${String(new Date().getDate()).padStart(2, '0')}`;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализация...');

    if (typeof CURRENT_YEAR !== 'undefined') currentYear = CURRENT_YEAR;
    if (typeof CURRENT_MONTH !== 'undefined') currentMonth = CURRENT_MONTH;
    if (typeof TODAY_DATE !== 'undefined') todayDate = TODAY_DATE;
    if (typeof USER_THEME !== 'undefined') currentTheme = USER_THEME;

    initYearSelect();
    loadCalendar();
    initDraggable();
    loadTheme();
});

function loadTheme() {
    const savedTheme = localStorage.getItem('theme');
    const defaultTheme = (typeof USER_THEME !== 'undefined' && USER_THEME) ? USER_THEME : 'light';
    currentTheme = savedTheme || defaultTheme;

    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon();
}

function toggleTheme() {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    updateThemeIcon();

    fetch('/update_theme', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({theme: currentTheme})
    }).catch(err => console.error('Ошибка сохранения темы:', err));

    loadCalendar();
}

function updateThemeIcon() {
    const btn = document.querySelector('.theme-toggle');
    if (btn) {
        btn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
    }
}

function initYearSelect() {
    const yearSelect = document.getElementById('year-select');
    const monthSelect = document.getElementById('month-select');

    if (!yearSelect || !monthSelect) {
        console.error('Не найдены селекты года или месяца');
        return;
    }

    yearSelect.innerHTML = '';
    for (let year = 2010; year <= 2044; year++) {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        if (year === currentYear) option.selected = true;
        yearSelect.appendChild(option);
    }

    monthSelect.value = currentMonth;
    console.log('Селекты инициализированы:', currentYear, currentMonth);
}

function goToToday() {
    const today = new Date();
    currentYear = today.getFullYear();
    currentMonth = today.getMonth() + 1;
    todayDate = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    document.getElementById('year-select').value = currentYear;
    document.getElementById('month-select').value = currentMonth;

    loadCalendar();
}

async function loadCalendar() {
    const yearSelect = document.getElementById('year-select');
    const monthSelect = document.getElementById('month-select');

    if (!yearSelect || !monthSelect) {
        console.error('Не найдены селекты');
        return;
    }

    currentYear = parseInt(yearSelect.value);
    currentMonth = parseInt(monthSelect.value);

    console.log('Загрузка календаря:', currentYear, currentMonth);

    const monthTitle = document.getElementById('current-month');
    const tbody = document.getElementById('calendar-body');

    monthTitle.textContent = 'Загрузка...';
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px;">Загрузка...</td></tr>';

    try {
        const url = `/get_calendar/${currentYear}/${currentMonth}`;
        console.log('Fetch URL:', url);

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Данные получены:', data);

        if (data.error) {
            throw new Error(data.error);
        }

        monthTitle.textContent = `${data.month_name} ${data.year}`;
        if (data.today) {
            todayDate = data.today;
        }

        renderCalendar(data.calendar);
    } catch (error) {
        console.error('Ошибка загрузки календаря:', error);
        monthTitle.textContent = 'Ошибка загрузки';
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 40px; color: var(--holiday);">
            Ошибка загрузки календаря<br>
            <small>${error.message}</small><br>
            <button onclick="loadCalendar()" class="btn btn-primary" style="margin-top: 10px;">Повторить</button>
        </td></tr>`;
    }
}

function renderCalendar(calendarData) {
    console.log('Рендеринг календаря...');
    const tbody = document.getElementById('calendar-body');
    tbody.innerHTML = '';
    selectedDays.clear();

    if (!calendarData || calendarData.length === 0) {
        console.error('Нет данных для отображения');
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px;">Нет данных</td></tr>';
        return;
    }

    calendarData.forEach((week) => {
        const row = document.createElement('tr');

        week.forEach((day) => {
            const cell = document.createElement('td');

            if (day.day === '') {
                cell.className = 'empty-day';
                cell.innerHTML = '<div style="height: 100%; min-height: 80px;"></div>';
            } else {
                const dayDiv = document.createElement('div');
                dayDiv.className = 'day-cell';
                dayDiv.setAttribute('data-date', day.date);

                if (day.date === todayDate) {
                    dayDiv.classList.add('today');
                }

                if (day.color) {
                    dayDiv.style.backgroundColor = hexToRgba(day.color,
                        currentTheme === 'dark' ? 0.3 : 0.15);
                }

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

                if (day.is_holiday && day.holiday_name) {
                    const holidayDiv = document.createElement('div');
                    holidayDiv.className = 'holiday-name';
                    holidayDiv.textContent = day.holiday_name;
                    dayDiv.appendChild(holidayDiv);
                }

                if (day.events && day.events.length > 0) {
                    const eventsContainer = document.createElement('div');
                    eventsContainer.className = 'events-container';

                    const maxEvents = Math.min(day.events.length, 3);

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
                        moreEvents.textContent = `+${day.events.length - 3} ещё`;
                        eventsContainer.appendChild(moreEvents);
                    }

                    dayDiv.appendChild(eventsContainer);
                }

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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

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
        alert('Ошибка загрузки информации о дне');
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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

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

        // Сбрасываем форму события
        document.getElementById('event-title').value = '';
        document.getElementById('event-description').value = '';
        document.getElementById('editing-event-id').value = '';
        document.getElementById('save-event-btn').textContent = '➕ Добавить событие';
        document.getElementById('cancel-edit-btn').style.display = 'none';
        editingEventId = null;

        await loadEventsList(date);

        const modal = document.getElementById('edit-modal');
        modal.style.display = 'block';

        const modalContent = modal.querySelector('.modal-content');
        modalContent.style.left = (window.innerWidth - 450) / 2 + 'px';
        modalContent.style.top = (window.innerHeight - 400) / 2 + 'px';
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка загрузки данных для редактирования');
    }
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const months = ['Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня',
                    'Июля', 'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря'];
    return `${day} ${months[parseInt(month) - 1]} ${year}`;
}

function closeInfoModal() {
    const modal = document.getElementById('info-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function closeEditModal() {
    const modal = document.getElementById('edit-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    selectedDate = null;
    editingEventId = null;
    document.getElementById('editing-event-id').value = '';
    const saveBtn = document.getElementById('save-event-btn');
    if (saveBtn) {
        saveBtn.textContent = '➕ Добавить событие';
    }
    const cancelBtn = document.getElementById('cancel-edit-btn');
    if (cancelBtn) {
        cancelBtn.style.display = 'none';
    }
}

function hexToRgba(hex, alpha) {
    if (!hex) return 'transparent';
    try {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    } catch (e) {
        return 'transparent';
    }
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
    if (!colorMode) {
        if (!confirm('Очистить ВСЕ цвета дней в текущем месяце?')) return;

        const allDays = document.querySelectorAll('.day-cell');
        const dates = [];
        allDays.forEach(cell => {
            const date = cell.getAttribute('data-date');
            if (date) dates.push(date);
        });

        if (dates.length === 0) return;

        try {
            const response = await fetch('/set_day_color', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    dates: dates,
                    color: ''
                })
            });

            const data = await response.json();
            if (data.success) {
                loadCalendar();
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
        return;
    }

    if (selectedDays.size === 0) {
        alert('Выберите дни для очистки или выключите режим выбора!');
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
            toggleColorMode();
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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const event = await response.json();

        closeInfoModal();
        await openEditModalDirect(event.date);

        setTimeout(() => {
            // Переключаемся на вкладку событий
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
        alert('Ошибка загрузки события');
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
        const response = await fetch(`/delete_event/${eventId}`, {method: 'DELETE'});

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        await loadEventsList(selectedDate);
        loadCalendar();
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении события');
    }
}

async function deleteEventFromInfo(eventId) {
    if (!confirm('Удалить событие?')) return;

    try {
        const response = await fetch(`/delete_event/${eventId}`, {method: 'DELETE'});

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        closeInfoModal();
        loadCalendar();
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении события');
    }
}

async function loadEventsList(date) {
    try {
        const response = await fetch(`/get_events/${date}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

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
        eventsList.innerHTML = '<p style="color: var(--error);">Ошибка загрузки событий</p>';
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
        if (!modal) return;

        const modalContent = modal.querySelector('.modal-content');
        const modalHeader = modal.querySelector('.modal-header');

        if (!modalContent || !modalHeader) return;

        let isDragging = false;
        let currentX, currentY, initialX, initialY;

        modalHeader.onmousedown = (e) => {
            if (e.target.classList.contains('edit-pencil') ||
                e.target.classList.contains('modal-close') ||
                e.target.classList.contains('edit-btn') ||
                e.target.classList.contains('btn-icon')) return;

            isDragging = true;
            initialX = e.clientX;
            initialY = e.clientY;

            const rect = modalContent.getBoundingClientRect();
            currentX = rect.left;
            currentY = rect.top;

            modalContent.style.cursor = 'grabbing';
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
            if (isDragging) {
                isDragging = false;
                modalContent.style.cursor = '';
            }
        };
    });
}

// Закрытие модальных окон по клику вне их
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

// Закрытие по Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeInfoModal();
        closeEditModal();
    }
});

console.log('Script.js загружен успешно');