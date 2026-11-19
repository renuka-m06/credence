import React from 'react';

export default function Navbar({ currentScreen, setCurrentScreen, demoMode, onToggleDemoMode }) {
  return (
    <header style={{
      borderBottom: '1px solid var(--line)',
      background: 'rgba(11, 11, 14, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '14px 0'
    }}>
      <div className="container navbar-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Brand with Seal Badge */}
        <div 
          onClick={() => setCurrentScreen('home')}
          style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
        >
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, var(--orange), var(--orange2))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(240, 106, 44, 0.4)'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <path d="m9 12 2 2 4-4"/>
            </svg>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', fontWeight: '700', letterSpacing: '-0.01em', color: '#fff' }}>
                Credence
              </span>
              <span style={{
                fontSize: '10px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'rgba(240, 106, 44, 0.15)',
                color: 'var(--orange2)',
                padding: '2px 6px',
                borderRadius: '4px',
                border: '1px solid rgba(240, 106, 44, 0.25)'
              }}>
                SEAL v0.1
              </span>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginTop: '-2px' }}>
              Every verdict carries proof
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {[
            { id: 'home', label: 'Home' },
            { id: 'report', label: 'Report' },
            { id: 'benchmark', label: 'Benchmark' },
          ].map(tab => {
            const active = currentScreen === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentScreen(tab.id)}
                style={{
                  background: active ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                  color: active ? '#fff' : 'var(--muted)',
                  border: active ? '1px solid var(--line)' : '1px solid transparent',
                  padding: '7px 14px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: active ? '600' : '500',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Demo Mode Toggle & Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => onToggleDemoMode?.()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
              fontSize: '11px',
              fontWeight: '600',
              cursor: 'pointer',
              color: demoMode ? 'var(--supported-color)' : 'var(--muted)',
              background: demoMode ? 'rgba(95, 207, 106, 0.12)' : 'rgba(255, 255, 255, 0.05)',
              padding: '6px 12px',
              borderRadius: '20px',
              border: demoMode ? '1px solid rgba(95, 207, 106, 0.35)' : '1px solid var(--line)',
              transition: 'all 0.2s ease'
            }}
            title={demoMode ? "Demo Mode ON: Serving pre-cached results from data/demo/ with zero live API calls" : "Demo Mode OFF: Live verification pipeline"}
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: demoMode ? 'var(--supported-color)' : 'var(--faint)',
              boxShadow: demoMode ? '0 0 8px var(--supported-color)' : 'none'
            }} />
            <span>Demo Mode: <strong style={{ color: demoMode ? '#fff' : 'var(--ink)' }}>{demoMode ? 'ON (Offline)' : 'OFF (Live)'}</strong></span>
          </button>
        </div>
      </div>
    </header>
  );
}
