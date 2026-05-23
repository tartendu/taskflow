// Reports functionality

document.addEventListener('DOMContentLoaded', () => {
    loadReports();
});

async function loadReports() {
    try {
        const response = await fetch('/api/reports/user-stats');
        const stats = await response.json();
        renderStats(stats);
    } catch (error) {
        console.error('Error loading reports:', error);
    }
}

function renderStats(stats) {
    // Update stat cards
    document.getElementById('totalTasks').textContent = stats.total_assigned;
    document.getElementById('completedTasks').textContent = stats.completed;
    document.getElementById('inProgressTasks').textContent = stats.in_progress;
    document.getElementById('overdueTasks').textContent = stats.overdue;

    // Update completion rate circle
    const completionRate = stats.completion_rate;
    document.getElementById('completionRate').textContent = completionRate + '%';
    updateProgressCircle(completionRate);

    // Update task distribution bars
    const maxTasks = Math.max(stats.todo, stats.in_progress, stats.on_hold, stats.completed) || 1;

    updateBar('todoBar', 'todoValue', stats.todo, maxTasks);
    updateBar('progressBar', 'progressValue', stats.in_progress, maxTasks);
    updateBar('holdBar', 'holdValue', stats.on_hold, maxTasks);
    updateBar('doneBar', 'doneValue', stats.completed, maxTasks);

    // Update priority distribution
    const totalPriority = stats.high_priority + stats.medium_priority + stats.low_priority || 1;

    document.getElementById('highPriority').textContent = stats.high_priority;
    document.getElementById('mediumPriority').textContent = stats.medium_priority;
    document.getElementById('lowPriority').textContent = stats.low_priority;

    updatePriorityBar('highBar', stats.high_priority, totalPriority);
    updatePriorityBar('mediumBar', stats.medium_priority, totalPriority);
    updatePriorityBar('lowBar', stats.low_priority, totalPriority);

    // Update project stats
    document.getElementById('ownedProjects').textContent = stats.owned_projects;
    document.getElementById('memberProjects').textContent = stats.member_projects;
}

function updateProgressCircle(percentage) {
    const circle = document.getElementById('completionCircle');
    const circumference = 534.07; // 2 * PI * 85
    const offset = circumference - (percentage / 100) * circumference;

    // Animate the circle
    setTimeout(() => {
        circle.style.strokeDashoffset = offset;
    }, 100);
}

function updateBar(barId, valueId, value, max) {
    const bar = document.getElementById(barId);
    const valueElement = document.getElementById(valueId);

    const percentage = (value / max) * 100;

    // Animate the bar
    setTimeout(() => {
        bar.style.width = percentage + '%';
    }, 100);

    valueElement.textContent = value;
}

function updatePriorityBar(barId, value, total) {
    const bar = document.getElementById(barId);
    const percentage = (value / total) * 100;

    // Animate the bar
    setTimeout(() => {
        bar.style.width = percentage + '%';
    }, 100);
}
