import React, { useState } from 'react';

export default function Navbar({
  currentScreen,
  setCurrentScreen,
  demoMode,
  onToggleDemoMode,
  theme,
  onToggleTheme,
}) {
  const isLight = theme === 'light';
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const mainTabs = [
    { id: 'home', label: 'Verify & Ingest' },
    { id: 'report', label: 'Active Dossier' },
    { id: 'reports', label: 'Archive' },
    { id: 'benchmark', label: 'Benchmark' },
    { id: 'audit', label: 'Audit Ledger' },
    { id: 'settings', label: 'Settings' },
    { id: 'about', label: 'Methodology' },
  ];

  const handleNavClick = (id) => {
    setCurrentScreen(id);
    setMobileMenuOpen(false);
  };

  return (
    <header style={{
      borderBottom: '1px solid var(--border-line)',
      background: 'var(--bg-backdrop)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '8px 0',
      transition: 'background-color 0.25s ease, border-color 0.25s ease'
    }}>
      <div className="container navbar-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        {/* Official Brand Logo (Switches according to selected theme) */}
        <div 
          onClick={() => handleNavClick('home')}
          style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', userSelect: 'none' }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && handleNavClick('home')}
          title="Credence Home"
        >
          <img
            src={isLight ? '/assets/credence-logo-light.png' : '/assets/credence-logo-dark.png'}
            alt="Credence"
            className="navbar-brand-logo"
            style={{
              height: '34px',
              width: 'auto',
              maxHeight: '38px',
              objectFit: 'contain',
              display: 'block',
            }}
          />
          <span style={{
            fontSize: '11px',
            fontWeight: '700',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            background: 'var(--accent-orange-subtle)',
            color: 'var(--accent-orange)',
            padding: '3px 8px',
            borderRadius: '5px',
            border: '1px solid var(--accent-orange-border)',
            alignSelf: 'center'
          }}>
            v2.0
          </span>
        </div>

        {/* Desktop Screen Navigation */}
        <nav className="desktop-nav" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '3px',
          background: 'rgba(255, 255, 255, 0.05)',
          padding: '4px',
          borderRadius: '9999px',
          border: '1px solid var(--border-line)'
        }}>
          {mainTabs.map(tab => {
            const active = currentScreen === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleNavClick(tab.id)}
                style={{
                  background: active ? 'rgba(255, 255, 255, 0.12)' : 'transparent',
                  color: active ? '#ffffff' : 'var(--text-secondary)',
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: '9999px',
                  fontSize: '12px',
                  fontWeight: active ? '600' : '500',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Controls: Theme Switch, Demo Mode Pill & Mobile Menu Toggle */}
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
              width: '34px',
              height: '34px',
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-line)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            {isLight ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
            title={demoMode ? "Demo Mode ON: Uses local sample data without live external APIs" : "Live Mode ON: Calls real academic databases"}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
              fontSize: '11.5px',
              fontWeight: '600',
              cursor: 'pointer',
              padding: '6px 14px',
              borderRadius: '9999px',
              transition: 'all 0.2s ease',
              background: 'rgba(74, 222, 128, 0.12)',
              color: '#4ade80',
              border: '1px solid rgba(74, 222, 128, 0.3)',
            }}
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: '#4ade80',
              boxShadow: '0 0 8px #4ade80'
            }} />
            <span>Demo (Offline)</span>
          </button>

          {/* Mobile Hamburger Toggle Button */}
          <button
            className="mobile-nav-toggle"
            onClick={() => setMobileMenuOpen(prev => !prev)}
            aria-label="Toggle navigation menu"
            style={{
              display: 'none',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-line)',
              color: 'var(--text-primary)',
              cursor: 'pointer'
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border-line)',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 60
          }}>
            {mainTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => handleNavClick(tab.id)}
                style={{
                  textAlign: 'left',
                  padding: '10px 14px',
                  borderRadius: '7px',
                  background: currentScreen === tab.id ? 'var(--bg-surface-elevated)' : 'transparent',
                  color: currentScreen === tab.id ? 'var(--accent-orange)' : 'var(--text-primary)',
                  border: 'none',
                  fontSize: '13.5px',
                  fontWeight: currentScreen === tab.id ? '700' : '500',
                  cursor: 'pointer'
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}
