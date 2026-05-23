// Calendar functionality

let currentDate = new Date();
let allTasks = [];

// Initialize calendar
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('prevMonth').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar();
    });

    document.getElementById('nextMonth').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar();
    });

    document.getElementById('todayBtn').addEventListener('click', () => {
        currentDate = new Date();
        renderCalendar();
    });
}

async function loadTasks() {
    try {
        const response = await fetch('/api/calendar/tasks');
        allTasks = await response.json();
        renderCalendar();
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    // Update header
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    document.getElementById('currentMonth').textContent = `${monthNames[month]} ${year}`;

    // Get first day of month and number of days
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    const calendarDays = document.getElementById('calendarDays');
    calendarDays.innerHTML = '';

    // Add previous month days
    for (let i = firstDay - 1; i >= 0; i--) {
        const day = daysInPrevMonth - i;
        const dayElement = createDayElement(day, month - 1, year, true);
        calendarDays.appendChild(dayElement);
    }

    // Add current month days
    for (let day = 1; day <= daysInMonth; day++) {
        const dayElement = createDayElement(day, month, year, false);
        calendarDays.appendChild(dayElement);
    }

    // Add next month days to fill the grid
    const totalCells = calendarDays.children.length;
    const remainingCells = Math.ceil(totalCells / 7) * 7 - totalCells;
    for (let day = 1; day <= remainingCells; day++) {
        const dayElement = createDayElement(day, month + 1, year, true);
        calendarDays.appendChild(dayElement);
    }
}

function createDayElement(day, month, year, isOtherMonth) {
    const dayElement = document.createElement('div');
    dayElement.className = 'calendar-day';

    if (isOtherMonth) {
        dayElement.classList.add('other-month');
    }

    // Check if today
    const today = new Date();
    if (day === today.getDate() && month === today.getMonth() && year === today.getFullYear() && !isOtherMonth) {
        dayElement.classList.add('today');
    }

    // Create date string
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

    // Get tasks for this day
    const dayTasks = allTasks.filter(task => {
        if (!task.due_date) return false;
        const taskDate = task.due_date.split('T')[0];
        return taskDate === dateStr;
    });

    // Day number
    const dayNumber = document.createElement('div');
    dayNumber.className = 'day-number';
    dayNumber.textContent = day;
    dayElement.appendChild(dayNumber);

    // Tasks container
    const tasksContainer = document.createElement('div');
    tasksContainer.className = 'day-tasks';

    // Show max 3 tasks
    const displayTasks = dayTasks.slice(0, 3);
    displayTasks.forEach(task => {
        const taskElement = createTaskElement(task);
        tasksContainer.appendChild(taskElement);
    });

    dayElement.appendChild(tasksContainer);

    // Task count if more than 3
    if (dayTasks.length > 3) {
        const countElement = document.createElement('div');
        countElement.className = 'task-count';
        countElement.textContent = `+${dayTasks.length - 3}`;
        dayElement.appendChild(countElement);
    }

    // Click to show all tasks for this day
    dayElement.addEventListener('click', () => {
        showDayTasks(dateStr, dayTasks);
    });

    return dayElement;
}

function createTaskElement(task) {
    const taskElement = document.createElement('div');
    taskElement.className = 'calendar-task';

    // Determine class based on status and overdue
    if (task.status === 'done') {
        taskElement.classList.add('completed');
    } else if (task.is_overdue) {
        taskElement.classList.add('overdue');
    } else {
        taskElement.classList.add('upcoming');
    }

    taskElement.textContent = task.title;
    taskElement.title = task.title;

    // Prevent event bubbling to day element
    taskElement.addEventListener('click', (e) => {
        e.stopPropagation();
        window.location.href = `/project/${task.project_id}/dashboard#task-${task.id}`;
    });

    return taskElement;
}

function showDayTasks(dateStr, tasks) {
    const modal = document.getElementById('taskDetailModal');
    const selectedDate = document.getElementById('selectedDate');
    const tasksList = document.getElementById('tasksList');

    // Format date
    const date = new Date(dateStr + 'T00:00:00');
    const formatted = date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    selectedDate.textContent = formatted;

    // Clear and populate tasks list
    tasksList.innerHTML = '';

    if (tasks.length === 0) {
        tasksList.innerHTML = '<p style="text-align: center; color: #95a5a6;">No tasks for this day</p>';
    } else {
        tasks.forEach(task => {
            const taskCard = createModalTaskCard(task);
            tasksList.appendChild(taskCard);
        });
    }

    modal.classList.add('active');
}

function createModalTaskCard(task) {
    const card = document.createElement('div');
    card.className = 'modal-task-card';

    const priorityLabels = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High'
    };

    const statusLabels = {
        'todo': 'To Do',
        'in_progress': 'In Progress',
        'on_hold': 'On Hold',
        'done': 'Done'
    };

    card.innerHTML = `
        <div class="modal-task-header">
            <h4 class="modal-task-title">${task.title}</h4>
            <span class="modal-task-priority priority-${task.priority}">${priorityLabels[task.priority]}</span>
        </div>
        ${task.description ? `<p class="modal-task-description">${task.description}</p>` : ''}
        <div class="modal-task-meta">
            <span class="modal-task-tag project-tag">📁 ${task.project_name}</span>
            <span class="modal-task-tag status-${task.status}">${statusLabels[task.status]}</span>
            ${task.is_overdue ? '<span class="modal-task-tag" style="background: #e74c3c20; color: #e74c3c;">⚠️ Overdue</span>' : ''}
        </div>
    `;

    card.addEventListener('click', () => {
        window.location.href = `/project/${task.project_id}/dashboard#task-${task.id}`;
    });

    return card;
}

function closeTaskModal() {
    const modal = document.getElementById('taskDetailModal');
    modal.classList.remove('active');
}

// Close modal on outside click
window.addEventListener('click', (e) => {
    const modal = document.getElementById('taskDetailModal');
    if (e.target === modal) {
        closeTaskModal();
    }
});
