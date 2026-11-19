import React from 'react';

export default function Navbar({
  currentScreen,
  setCurrentScreen,
  demoMode,
  onToggleDemoMode,
  theme,
  onToggleTheme,
}) {
  const isLight = theme === 'light';

  return (
    <header style={{
      borderBottom: '1px solid var(--border-line)',
      background: 'var(--bg-backdrop)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '12px 0',
      transition: 'background-color 0.25s ease, border-color 0.25s ease'
    }}>
      <div className="container navbar-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Brand Identity with Scholarly Seal */}
        <div 
          onClick={() => setCurrentScreen('home')}
          style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', userSelect: 'none' }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setCurrentScreen('home')}
        >
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '9px',
            background: 'linear-gradient(135deg, var(--accent-orange), var(--accent-orange-hover))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(240, 106, 44, 0.35)',
            flexShrink: 0
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <path d="m9 12 2 2 4-4"/>
            </svg>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '19px',
                fontWeight: '700',
                letterSpacing: '-0.02em',
                color: 'var(--text-primary)',
                lineHeight: 1.1
              }}>
                Credence
              </span>
              <span style={{
                fontSize: '10px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'var(--accent-orange-subtle)',
                color: 'var(--accent-orange)',
                padding: '2px 7px',
                borderRadius: '4px',
                border: '1px solid var(--accent-orange-border)'
              }}>
                Engine v2.0
              </span>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', display: 'block', marginTop: '1px' }}>
              Every scientific verdict carries proof
            </span>
          </div>
        </div>

        {/* Primary Screen Navigation */}
        <nav style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          background: 'var(--bg-surface-elevated)',
          padding: '4px',
          borderRadius: '9px',
          border: '1px solid var(--border-line)'
        }}>
          {[
            { id: 'home', label: 'Verify & Ingest' },
            { id: 'report', label: 'Report Dossier' },
            { id: 'benchmark', label: 'Evaluation Benchmark' },
          ].map(tab => {
            const active = currentScreen === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentScreen(tab.id)}
                style={{
                  background: active ? 'var(--bg-surface)' : 'transparent',
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  border: active ? '1px solid var(--border-line)' : '1px solid transparent',
                  boxShadow: active ? 'var(--shadow-sm)' : 'none',
                  padding: '7px 15px',
                  borderRadius: '7px',
                  fontSize: '12.5px',
                  fontWeight: active ? '600' : '500',
                  cursor: 'pointer',
                  transition: 'all 0.18s ease'
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Controls: Theme Switch & Demo Mode Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Light / Dark Mode Toggle */}
          <button
            onClick={() => onToggleTheme?.()}
            title={isLight ? "Switch to Dark Mode" : "Switch to Light Mode"}
            aria-label="Toggle theme"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-line)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            {isLight ? (
              /* Moon Icon for Light Mode (switch to dark) */
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
              </svg>
            ) : (
              /* Sun Icon for Dark Mode (switch to light) */
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4"/>
                <path d="M12 2v2"/><path d="M12 20v2"/>
                <path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>
                <path d="M2 12h2"/><path d="M20 12h2"/>
                <path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>
              </svg>
            )}
          </button>

          {/* Demo Mode Toggle Button */}
          <button
            onClick={() => onToggleDemoMode?.()}
            title={demoMode ? "Demo Mode ON: Uses cached sample data without live external APIs" : "Live Mode ON: Calls real academic databases"}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
              fontSize: '11.5px',
              fontWeight: '600',
              cursor: 'pointer',
              padding: '6px 12px',
              borderRadius: '8px',
              transition: 'all 0.2s ease',
              background: demoMode ? 'var(--supported-bg)' : 'var(--bg-surface-elevated)',
              color: demoMode ? 'var(--supported-color)' : 'var(--text-secondary)',
              border: demoMode ? '1px solid var(--supported-border)' : '1px solid var(--border-line)',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: demoMode ? 'var(--supported-color)' : 'var(--text-tertiary)',
              boxShadow: demoMode ? '0 0 8px var(--supported-color)' : 'none'
            }} />
            <span>{demoMode ? 'Demo Mode (Offline)' : 'Live Gateway'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
