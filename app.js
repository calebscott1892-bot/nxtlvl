document.addEventListener('DOMContentLoaded', () => {

    // --- 0. Hero Entrance Animation ---
    const heroContent = document.querySelector('.hero-content');
    if (heroContent) {
        // Small delay so the page settles, then trigger the sequence
        requestAnimationFrame(() => {
            setTimeout(() => heroContent.classList.add('hero-animate'), 200);
        });
    }

    // --- 1. Mobile Navigation Toggle ---
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-content nav');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            const isOpen = navMenu.classList.toggle('open');
            navToggle.setAttribute('aria-expanded', isOpen);
        });
    }

    // --- 2. Session Type Toggle ---
    const sessionTypeSelect = document.getElementById('session_type');
    const groupSizeWrapper = document.getElementById('group-size-field');
    const groupSizeSelect = document.getElementById('group_size');

    if (sessionTypeSelect && groupSizeWrapper) {
        sessionTypeSelect.addEventListener('change', (e) => {
            if (e.target.value === 'group') {
                groupSizeWrapper.style.display = 'block';
                if (groupSizeSelect) groupSizeSelect.required = true;
            } else {
                groupSizeWrapper.style.display = 'none';
                if (groupSizeSelect) {
                    groupSizeSelect.value = '';
                    groupSizeSelect.required = false;
                }
            }
        });
    }

    // --- 2b. Set minimum date to today ---
    const dateInput = document.getElementById('preferred_date');
    if (dateInput) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        dateInput.setAttribute('min', `${yyyy}-${mm}-${dd}`);
    }

    // --- 3. FullCalendar Initialization ---
    const calendarEl = document.getElementById('booking-calendar');
    let calendar;
    let currentAvailabilityMonth = '';

    if (calendarEl) {
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: ''
            },
            validRange: {
                start: new Date()
            },
            dateClick: (info) => {
                const d = new Date(info.dateStr + 'T00:00:00');
                if (d.getDay() === 0 || d.getDay() === 6) return; // ignore weekends

                const dateInput = document.getElementById('preferred_date');
                if (dateInput) {
                    dateInput.value = info.dateStr;
                    dateInput.dispatchEvent(new Event('change'));
                }

                // Highlight selected day in calendar
                calendarEl.querySelectorAll('.fc-daygrid-day').forEach(cell => cell.classList.remove('fc-day-selected'));
                const dayCell = calendarEl.querySelector(`[data-date="${info.dateStr}"]`);
                if (dayCell) dayCell.classList.add('fc-day-selected');

                // Scroll booking form into view
                const bookingForm = document.getElementById('booking-form');
                if (bookingForm) bookingForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
            },
            datesSet: (info) => {
                const currentDate = info.view.currentStart;
                const monthStr = currentDate.toISOString().substring(0, 7);
                currentAvailabilityMonth = monthStr;
                refreshAvailability();
            }
        });
        calendar.render();
    }

    function getCurrentCalendarMonth() {
        if (!calendar) return '';
        return calendar.getDate().toISOString().substring(0, 7);
    }

    async function refreshAvailability() {
        const month = currentAvailabilityMonth || getCurrentCalendarMonth();
        if (!month) return;
        await fetchAvailability(month);
        if (dateInput?.value) {
            await fetchDayAvailability(dateInput.value);
        }
    }

    async function fetchAvailability(month) {
        if (!calendar) return;
        try {
            const response = await fetch(`/bookings/availability?month=${month}`);
            if (!response.ok) throw new Error('Failed to fetch availability');

            const data = await response.json();

            calendar.removeAllEvents();

            data.forEach(day => {
                if (day.slots.length > 0) {
                    calendar.addEvent({
                        title: `${day.slots.length} slot${day.slots.length > 1 ? 's' : ''}`,
                        start: day.date,
                        backgroundColor: day.slots.length <= 2 ? '#d97706' : '#22c55e',
                        borderColor: day.slots.length <= 2 ? '#d97706' : '#22c55e',
                        textColor: '#ffffff',
                        allDay: true
                    });
                }
            });
        } catch (error) {
            console.error('Calendar Error:', error);
        }
    }

    if (calendar) {
        setInterval(() => {
            if (!document.hidden) refreshAvailability();
        }, 30000);

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) refreshAvailability();
        });
    }

    // --- 3b. Smart Time Slot Filtering ---
    const TIME_LABELS = {
        '08:00': '8:00 AM', '09:00': '9:00 AM', '10:00': '10:00 AM',
        '11:00': '11:00 AM', '12:00': '12:00 PM', '13:00': '1:00 PM'
    };

    const timeSelect = document.getElementById('preferred_time');

    function updateTimeSlots(availableSlots) {
        if (!timeSelect) return;
        const current = timeSelect.value;
        timeSelect.innerHTML = '<option value="" disabled selected>Select a time slot</option>';

        if (!availableSlots || availableSlots.length === 0) {
            const opt = document.createElement('option');
            opt.disabled = true;
            opt.textContent = 'No slots available for this date';
            timeSelect.appendChild(opt);
            return;
        }

        Object.keys(TIME_LABELS).sort().forEach(val => {
            const opt = document.createElement('option');
            opt.value = val;
            opt.textContent = TIME_LABELS[val];
            if (!availableSlots.includes(val)) {
                opt.disabled = true;
                opt.textContent += ' — Booked';
            }
            timeSelect.appendChild(opt);
        });

        // Re-select previous value if still available
        if (current && availableSlots.includes(current)) {
            timeSelect.value = current;
        }
    }

    if (dateInput) {
        dateInput.addEventListener('change', async () => {
            const date = dateInput.value;
            if (!date) return;
            await fetchDayAvailability(date);
        });
    }

    async function fetchDayAvailability(date) {
        try {
            const resp = await fetch(`/bookings/availability/${date}`);
            if (!resp.ok) throw new Error('Failed');
            const data = await resp.json();
            updateTimeSlots(data.slots);
        } catch {
            updateTimeSlots(null);
        }
    }

    // --- 4. Form Submission ---
    const bookingForm = document.getElementById('booking-form');
    const formStatus = document.getElementById('form-status');
    const submitBtn = document.getElementById('submit-btn');
    const btnSpinner = submitBtn?.querySelector('.btn-spinner');

    function setLoading(on) {
        if (!submitBtn) return;
        submitBtn.disabled = on;
        if (on) {
            submitBtn.classList.add('loading');
            if (btnSpinner) btnSpinner.hidden = false;
        } else {
            submitBtn.classList.remove('loading');
            if (btnSpinner) btnSpinner.hidden = true;
        }
    }

    if (bookingForm) {
        bookingForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (formStatus) {
                formStatus.textContent = '';
                formStatus.style.color = '';
            }
            setLoading(true);

            const nameVal = document.getElementById('name')?.value;
            const sessionVal = document.getElementById('session_type')?.value;
            const dateVal = document.getElementById('preferred_date')?.value;
            const timeVal = document.getElementById('preferred_time')?.value;

            const formData = {
                name: nameVal,
                email: document.getElementById('email')?.value,
                phone: document.getElementById('phone')?.value,
                session_type: sessionVal,
                group_size: sessionVal === 'group'
                    ? parseInt(document.getElementById('group_size')?.value || '3', 10)
                    : 1,
                preferred_date: dateVal,
                preferred_time: timeVal,
                notes: document.getElementById('notes')?.value || ''
            };

            try {
                const response = await fetch('/bookings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                if (response.status === 201) {
                    // Show success confirmation panel
                    showBookingConfirmation({
                        name: nameVal,
                        session_type: sessionVal,
                        date: dateVal,
                        time: timeVal
                    });

                    bookingForm.reset();
                    if (groupSizeWrapper) groupSizeWrapper.style.display = 'none';
                    if (timeSelect) updateTimeSlots(null);
                    if (calendar) {
                        refreshAvailability();
                    }
                } else if (response.status === 429) {
                    throw new Error('Too many requests — please wait a minute and try again.');
                } else {
                    const errData = await response.json();
                    const detail = errData.detail;
                    const msg = Array.isArray(detail)
                        ? detail.map(e => e.msg || e).join('; ')
                        : (detail || 'Submission failed');
                    throw new Error(msg);
                }
            } catch (error) {
                if (formStatus) {
                    formStatus.style.color = '#ef4444';
                    formStatus.textContent = `Error: ${error.message}`;
                }
            } finally {
                setLoading(false);
            }
        });
    }

    // --- 4b. Booking Confirmation Panel ---
    function showBookingConfirmation({ name, session_type, date, time }) {
        const confirmationEl = document.getElementById('booking-confirmation');
        if (!confirmationEl) return;

        const timeFmt = TIME_LABELS[time] || time;
        const dateFmt = new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
        const typeLabel = session_type === 'solo' ? '1-on-1 Session' : 'Small Group Session';

        confirmationEl.querySelector('.conf-name').textContent = name;
        confirmationEl.querySelector('.conf-type').textContent = typeLabel;
        confirmationEl.querySelector('.conf-date').textContent = dateFmt;
        confirmationEl.querySelector('.conf-time').textContent = timeFmt;

        bookingForm.style.display = 'none';
        confirmationEl.hidden = false;
        confirmationEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const bookAnotherBtn = document.getElementById('book-another-btn');
    if (bookAnotherBtn && bookingForm) {
        bookAnotherBtn.addEventListener('click', () => {
            const confirmationEl = document.getElementById('booking-confirmation');
            if (confirmationEl) confirmationEl.hidden = true;
            bookingForm.style.display = '';
        });
    }

    // --- 5. Smooth Scroll ---
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);

            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth' });
                if (navMenu) navMenu.classList.remove('open');
            }
        });
    });

    // --- 6. Scroll Reveal (IntersectionObserver) ---
    const revealEls = document.querySelectorAll('[data-reveal]');
    if (revealEls.length) {
        // Opt-in: hide elements only after JS loads (progressive enhancement)
        document.documentElement.classList.add('reveal-ready');

        if ('IntersectionObserver' in window) {
            const revealObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('revealed');
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.05, rootMargin: '0px 0px -20px 0px' });

            revealEls.forEach(el => revealObserver.observe(el));
        }

        // Safety net: reveal everything after 2.5s no matter what
        setTimeout(() => {
            revealEls.forEach(el => el.classList.add('revealed'));
        }, 2500);
    }

    // --- 7. Draggable Career Carousel ---
    const carousel = document.getElementById('career-carousel');
    if (carousel) {
        const track = carousel.querySelector('.career-track');
        let isDragging = false;
        let startX = 0;
        let currentTranslate = 0;
        let prevTranslate = 0;
        let dragDistance = 0;

        // Calculate drag bounds
        function getMaxTranslate() {
            const trackWidth = track.scrollWidth;
            const containerWidth = carousel.offsetWidth;
            return Math.min(0, -(trackWidth - containerWidth));
        }

        function clamp(val, min, max) {
            return Math.max(min, Math.min(max, val));
        }

        function setPosition() {
            track.style.transform = `translateX(${currentTranslate}px)`;
        }

        // Mouse events
        carousel.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragDistance = 0;
            startX = e.clientX;
            track.style.transition = 'none';
            carousel.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            dragDistance = Math.abs(dx);
            currentTranslate = clamp(prevTranslate + dx, getMaxTranslate(), 0);
            setPosition();
        });

        window.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            prevTranslate = currentTranslate;
            track.style.transition = 'transform 0.3s ease-out';
            carousel.style.cursor = 'grab';
        });

        // Touch events
        carousel.addEventListener('touchstart', (e) => {
            isDragging = true;
            dragDistance = 0;
            startX = e.touches[0].clientX;
            track.style.transition = 'none';
        }, { passive: true });

        carousel.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            const dx = e.touches[0].clientX - startX;
            dragDistance = Math.abs(dx);
            currentTranslate = clamp(prevTranslate + dx, getMaxTranslate(), 0);
            setPosition();
        }, { passive: true });

        carousel.addEventListener('touchend', () => {
            isDragging = false;
            prevTranslate = currentTranslate;
            track.style.transition = 'transform 0.3s ease-out';
        });

        // Prevent link clicks during drag
        carousel.addEventListener('click', (e) => {
            if (dragDistance > 5) {
                e.preventDefault();
            }
        });
    }

});
