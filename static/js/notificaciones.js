(() => {
    const badge = document.querySelector('[data-notification-count]');
    if (!badge) {
        return;
    }

    const endpoint = badge.dataset.countUrl;
    const updateCount = async () => {
        try {
            const response = await fetch(endpoint, {
                credentials: 'same-origin',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
            });
            if (!response.ok) {
                throw new Error(`Notification count request failed: ${response.status}`);
            }
            const result = await response.json();
            const count = Number(result.count);
            if (!Number.isInteger(count) || count < 0) {
                throw new Error('Notification count response was invalid.');
            }
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.hidden = count === 0;
        } catch (error) {
            console.error('Unable to update notification count:', error);
        }
    };

    updateCount();
    window.setInterval(updateCount, 60_000);
})();
