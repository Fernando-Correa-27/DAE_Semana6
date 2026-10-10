(() => {
    const root = document.documentElement;
    const toggle = document.querySelector('[data-theme-toggle]');
    if (!toggle) return;

    const label = toggle.querySelector('.theme-label');
    const systemPreference = window.matchMedia('(prefers-color-scheme: dark)');

    const hasSavedPreference = () => {
        try {
            const theme = localStorage.getItem('dae-theme');
            return theme === 'light' || theme === 'dark';
        } catch (_) {
            return false;
        }
    };

    const updateControl = () => {
        const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        const nextLabel = nextTheme === 'light' ? 'claro' : 'oscuro';
        toggle.setAttribute('aria-label', `Cambiar al tema ${nextLabel}`);
        toggle.setAttribute('title', `Cambiar al tema ${nextLabel}`);
        if (label) label.textContent = `Tema ${nextLabel}`;
    };

    const setTheme = (theme, save = false) => {
        root.dataset.theme = theme;
        if (save) {
            try {
                localStorage.setItem('dae-theme', theme);
            } catch (_) {
                // El tema sigue funcionando durante la página aunque el almacenamiento no esté disponible.
            }
        }
        updateControl();
    };

    updateControl();
    toggle.addEventListener('click', () => {
        setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
    });

    const followSystemPreference = (event) => {
        if (!hasSavedPreference()) setTheme(event.matches ? 'dark' : 'light');
    };
    if (systemPreference.addEventListener) {
        systemPreference.addEventListener('change', followSystemPreference);
    } else if (systemPreference.addListener) {
        systemPreference.addListener(followSystemPreference);
    }

    window.addEventListener('storage', (event) => {
        if (event.key !== 'dae-theme') return;
        if (event.newValue === 'light' || event.newValue === 'dark') {
            setTheme(event.newValue);
        } else if (!event.newValue) {
            setTheme(systemPreference.matches ? 'dark' : 'light');
        }
    });
})();
