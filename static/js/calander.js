$(document).ready(function() {
    const calendar = $("#calendar");
    let currentDate = new Date();
    let bookedDates = [];

 
    function fetchBookedDates() {
        fetch('http://127.0.0.1:5001/api/get_user_booked_dates', {
            method: 'GET',
            credentials: 'include' 
        })
        .then(response => response.json())
        .then(dates => {
            bookedDates = dates.map(dateString => {
                let d = new Date(dateString);
                return { 
                    day: d.getDate(), 
                    month: d.getMonth(), 
                    year: d.getFullYear() 
                };
            });
            generateCalendar(currentDate);
        })
        .catch(error => console.error("Error fetching dates:", error));
    }

    function generateCalendar(date) {
        calendar.empty();
        let year = date.getFullYear();
        let month = date.getMonth();

        $("#monthYear").text(
            new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(date)
        );

        let firstDay = new Date(year, month, 1).getDay();
        let daysInMonth = new Date(year, month + 1, 0).getDate();
        let daysInPrevMonth = new Date(year, month, 0).getDate();
        let weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

        weekdays.forEach(day => {
            calendar.append(`<div class="weekday">${day}</div>`);
        });

        for (let i = firstDay; i > 0; i--) {
            calendar.append(`<div class="day prev-month">${daysInPrevMonth - i + 1}</div>`);
        }

        for (let i = 1; i <= daysInMonth; i++) {
            let isBooked = bookedDates.some(d => d.day === i && d.month === month && d.year === year);
            let markClass = isBooked ? "highlighted-date" : "";
            calendar.append(`<div class="day ${markClass}">${i}</div>`);
        }

        let nextMonthDays = 7 - ((firstDay + daysInMonth) % 7);
        if (nextMonthDays < 7) {
            for (let i = 1; i <= nextMonthDays; i++) {
                calendar.append(`<div class="day next-month">${i}</div>`);
            }
        }
    }

    fetchBookedDates();

    $("#prevMonth").click(() => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        generateCalendar(currentDate);
    });

    $("#nextMonth").click(() => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        generateCalendar(currentDate);
    });
});
