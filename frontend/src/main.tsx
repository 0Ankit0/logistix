import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { DEFAULT_THEME_ID, THEME_PRESETS, applyThemeToDocument, findThemeById } from '@/lib/themes';
import { App } from '@/App';
import '@/app/globals.css';

function applyInitialTheme() {
  try {
    const storedTheme = localStorage.getItem('theme-storage');
    let activeThemeId = DEFAULT_THEME_ID;
    let customThemes = [];

    if (storedTheme) {
      const parsed = JSON.parse(storedTheme);
      if (parsed?.state?.activeThemeId) {
        activeThemeId = parsed.state.activeThemeId;
      }
      if (Array.isArray(parsed?.state?.customThemes)) {
        customThemes = parsed.state.customThemes;
      }
    }

    applyThemeToDocument(findThemeById(activeThemeId, customThemes));
  } catch {
    applyThemeToDocument(THEME_PRESETS[0]);
  }
}

applyInitialTheme();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
