// Time Management functionality

let allEvents = [];
let editingEventId = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadEvents();
    setupEventListeners();
});

function setupEventListeners() {
    const modal = document.getElementById('eventModal');
    const addBtn = document.getElementById('addEventBtn');
    const closeBtn = modal.querySelector('.close');
    const cancelBtn = document.getElementById('cancelBtn');
    const form = document.getElementById('eventForm');

    addBtn.addEventListener('click', () => openAddModal());
    closeBtn.addEventListener('click', () => closeModal());
    cancelBtn.addEventListener('click', () => closeModal());
    form.addEventListener('submit', handleSubmit);

    // Close modal on outside click
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
}

async function loadEvents() {
    try {
        const response = await fetch('/api/events');
        allEvents = await response.json();
        renderEvents();
    } catch (error) {
        console.error('Error loading events:', error);
    }
}

function renderEvents() {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart);
    todayEnd.setDate(todayEnd.getDate() + 1);

    // Separate events
    const todayEvents = allEvents.filter(event => {
        const eventDate = new Date(event.start_time);
        return eventDate >= todayStart && eventDate < todayEnd;
    });

    const upcomingEvents = allEvents.filter(event => {
        const eventDate = new Date(event.start_time);
        return eventDate >= todayEnd;
    });

    const pastEvents = allEvents.filter(event => {
        const eventDate = new Date(event.start_time);
        return eventDate < todayStart;
    }).reverse();

    // Update counts
    document.getElementById('todayCount').textContent = todayEvents.length;
    document.getElementById('upcomingCount').textContent = upcomingEvents.length;
    document.getElementById('pastCount').textContent = pastEvents.length;

    // Render each section
    renderEventsList('todayEvents', todayEvents, 'No events scheduled for today');
    renderEventsList('upcomingEvents', upcomingEvents, 'No upcoming events');
    renderEventsList('pastEvents', pastEvents, 'No past events');
}

function renderEventsList(containerId, events, emptyMessage) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    if (events.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                    <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <p>${emptyMessage}</p>
            </div>
        `;
        return;
    }

    events.forEach(event => {
        const card = createEventCard(event);
        container.appendChild(card);
    });
}

function createEventCard(event) {
    const card = document.createElement('div');
    card.className = `event-card ${event.event_type}`;

    const startTime = new Date(event.start_time);
    const timeStr = startTime.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
    const dateStr = startTime.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });

    let endTimeStr = '';
    if (event.end_time) {
        const endTime = new Date(event.end_time);
        endTimeStr = ' - ' + endTime.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }

    const eventTypeLabels = {
        'meeting': 'Meeting',
        'reminder': 'Reminder',
        'personal': 'Personal'
    };

    card.innerHTML = `
        <div class="event-header">
            <h4 class="event-title">${event.title}</h4>
            <span class="event-type-badge ${event.event_type}">${eventTypeLabels[event.event_type]}</span>
        </div>
        ${event.description ? `<p class="event-description">${event.description}</p>` : ''}
        <div class="event-meta">
            <div class="event-meta-item time">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                    <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>${timeStr}${endTimeStr}</span>
            </div>
            <div class="event-meta-item">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/>
                    <path d="M16 2V6M8 2V6M3 10H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>${dateStr}</span>
            </div>
            ${event.location ? `
                <div class="event-meta-item">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 21C12 21 5 15 5 10C5 6.13401 8.13401 3 12 3C15.866 3 19 6.13401 19 10C19 15 12 21 12 21Z" stroke="currentColor" stroke-width="2"/>
                        <circle cx="12" cy="10" r="3" stroke="currentColor" stroke-width="2"/>
                    </svg>
                    <span>${event.location}</span>
                </div>
            ` : ''}
        </div>
        <div class="event-actions">
            <button class="event-btn" onclick="editEvent(${event.id})">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 1.5L14.5 4.5L5 14H2V11L11.5 1.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Edit
            </button>
            <button class="event-btn delete-btn" onclick="deleteEvent(${event.id})">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M2 4H14M12.6667 4V13.3333C12.6667 14 12 14.6667 11.3333 14.6667H4.66667C4 14.6667 3.33333 14 3.33333 13.3333V4M5.33333 4V2.66667C5.33333 2 6 1.33333 6.66667 1.33333H9.33333C10 1.33333 10.6667 2 10.6667 2.66667V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Delete
            </button>
        </div>
    `;

    return card;
}

function openAddModal() {
    editingEventId = null;
    document.getElementById('modalTitle').textContent = 'Add New Event';
    document.getElementById('submitBtn').textContent = 'Add Event';
    document.getElementById('eventForm').reset();
    document.getElementById('eventId').value = '';

    // Set default start time to current time rounded to next hour
    const now = new Date();
    now.setHours(now.getHours() + 1, 0, 0, 0);
    document.getElementById('eventStartTime').value = formatDateTimeLocal(now);

    document.getElementById('eventModal').classList.add('active');
}

function editEvent(eventId) {
    editingEventId = eventId;
    const event = allEvents.find(e => e.id === eventId);
    if (!event) return;

    document.getElementById('modalTitle').textContent = 'Edit Event';
    document.getElementById('submitBtn').textContent = 'Save Changes';
    document.getElementById('eventId').value = eventId;
    document.getElementById('eventTitle').value = event.title;
    document.getElementById('eventDescription').value = event.description || '';
    document.getElementById('eventType').value = event.event_type;
    document.getElementById('eventLocation').value = event.location || '';

    // Format datetime for input
    document.getElementById('eventStartTime').value = formatDateTimeLocal(new Date(event.start_time));
    if (event.end_time) {
        document.getElementById('eventEndTime').value = formatDateTimeLocal(new Date(event.end_time));
    }

    document.getElementById('eventModal').classList.add('active');
}

async function deleteEvent(eventId) {
    if (!confirm('Are you sure you want to delete this event?')) return;

    try {
        const response = await fetch(`/api/events/${eventId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadEvents();
        } else {
            alert('Failed to delete event');
        }
    } catch (error) {
        console.error('Error deleting event:', error);
        alert('Error deleting event');
    }
}

function closeModal() {
    document.getElementById('eventModal').classList.remove('active');
    editingEventId = null;
}

async function handleSubmit(e) {
    e.preventDefault();

    const formData = {
        title: document.getElementById('eventTitle').value,
        description: document.getElementById('eventDescription').value,
        event_type: document.getElementById('eventType').value,
        location: document.getElementById('eventLocation').value,
        start_time: new Date(document.getElementById('eventStartTime').value).toISOString(),
        end_time: document.getElementById('eventEndTime').value ?
            new Date(document.getElementById('eventEndTime').value).toISOString() : null
    };

    try {
        let response;
        if (editingEventId) {
            response = await fetch(`/api/events/${editingEventId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
        } else {
            response = await fetch('/api/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
        }

        if (response.ok) {
            closeModal();
            await loadEvents();
        } else {
            alert('Failed to save event');
        }
    } catch (error) {
        console.error('Error saving event:', error);
        alert('Error saving event');
    }
}

function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}
