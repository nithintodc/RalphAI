// App shell — sidebar nav + topbar + screen switching
// Renders to #root. All screens are window.Screen<Name>

const { useState, useEffect, useMemo } = React;

const NAV_ITEMS = [
  { id: 'overview',    label: 'Overview',        icon: I.Home },
  { id: 'compare',     label: 'Pre vs Post',     icon: I.Compare, badge: 'Hero' },
  { id: 'diagnostics', label: 'Diagnostics',     icon: I.Diag },
  { id: 'stores',      label: 'Stores',          icon: I.Store },
  { id: 'slots',       label: 'Slots & Heatmap', icon: I.Slot },
  { id: 'buckets',     label: 'Order buckets',   icon: I.Bucket },
  { id: 'marketing',   label: 'Marketing',       icon: I.Mkt },
];

function Sidebar({ active, setActive }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">R</div>
        <div className="sidebar-brand-name">Ralph <span className="sub">Analyse</span></div>
      </div>

      {NAV_ITEMS.map(item => {
        const Ico = item.icon;
        return (
          <button key={item.id}
                  className={`nav-item ${active === item.id ? 'active' : ''}`}
                  onClick={() => setActive(item.id)}>
            <Ico />
            <span>{item.label}</span>
            {item.badge && <span className="badge">{item.badge}</span>}
          </button>
        );
      })}

      <div className="sidebar-footer">
        <div className="sidebar-section-label" style={{ paddingTop: 0 }}>Operator</div>
        <button className="nav-item">
          <I.Globe />
          <span>Bayview Burger Co.</span>
          <I.ChevronDown />
        </button>
        <div className="user-row" style={{ marginTop: 4 }}>
          <div className="avatar">AS</div>
          <div>
            <div className="user-name">Aman S.</div>
            <div className="user-role">Operator · Pro</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ title, crumb }) {
  return (
    <div className="topbar">
      <div className="topbar-title">{title}</div>
      {crumb && <>
        <I.ChevronRight />
        <span className="topbar-crumb">{crumb}</span>
      </>}
      <div className="topbar-spacer" />

      <PlatformTabs />

      <button className="chip">
        <I.Cal />
        <span><b className="tnum">Jan</b> vs <b className="tnum">Feb 2026</b></span>
        <I.ChevronDown />
      </button>

      <button className="chip">
        <I.Filter />
        <span>46 stores</span>
        <I.ChevronDown />
      </button>

      <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

      <button className="icon-btn"><I.Bell /></button>
      <button className="chip">
        <I.Export />
        <span>Export</span>
      </button>
    </div>
  );
}

function PlatformTabs() {
  const [v, setV] = useState('all');
  return (
    <div className="tab-row">
      {[
        { id: 'all', label: 'Combined' },
        { id: 'dd',  label: 'DoorDash' },
        { id: 'ue',  label: 'UberEats' },
      ].map(t => (
        <button key={t.id} className={`tab ${v === t.id ? 'active' : ''}`} onClick={() => setV(t.id)}>
          {t.id !== 'all' && <span className={`dot ${t.id}`} />} {t.label}
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────── Default tweaks
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "heroStyle": "spark"
}/*EDITMODE-END*/;

function App() {
  const [active, setActive] = useState('overview');
  const [t, setTweak] = window.useTweaks(TWEAK_DEFAULTS);

  // Apply theme to <html data-theme>
  useEffect(() => {
    document.documentElement.dataset.theme = t.theme;
  }, [t.theme]);

  // Screen registry
  const screens = {
    overview:    { title: 'Overview',           crumb: 'Last refresh · 4m ago',     Comp: window.ScreenOverview },
    compare:     { title: 'Pre vs Post',        crumb: 'All metrics · Combined',    Comp: window.ScreenCompare },
    diagnostics: { title: 'Diagnostics',        crumb: 'Sales decomposition',       Comp: window.ScreenDiagnostics },
    stores:      { title: 'Stores',             crumb: '46 active',                 Comp: window.ScreenStores },
    storeDetail: { title: 'Store',              crumb: 'S-1004 · Castro',           Comp: window.ScreenStoreDetail },
    slots:       { title: 'Slots & Heatmap',    crumb: 'Sales · Pre vs Post',       Comp: window.ScreenSlots },
    buckets:     { title: 'Order buckets',      crumb: 'Order count by ticket size',Comp: window.ScreenBuckets },
    marketing:   { title: 'Marketing',          crumb: 'Corp vs TODC · Post period',Comp: window.ScreenMarketing },
  };

  const handleStoreClick = () => setActive('storeDetail');
  const screen = screens[active] || screens.overview;
  const ScreenComp = screen.Comp;

  return (
    <div className="app" data-screen-label={`screen ${active}`}>
      <Sidebar active={active === 'storeDetail' ? 'stores' : active} setActive={setActive} />
      <div className="main">
        <Topbar title={screen.title} crumb={screen.crumb} />
        <div className="content">
          {ScreenComp ? <ScreenComp t={t} setActive={setActive} onStoreClick={handleStoreClick} /> :
            <div className="card">Loading…</div>}
        </div>
      </div>

      <window.TweaksPanel title="Tweaks">
        <window.TweakSection title="Appearance">
          <window.TweakRadio label="Theme" value={t.theme}
                             options={[{value:'light', label:'Light'}, {value:'dark', label:'Dark'}]}
                             onChange={v => setTweak('theme', v)} />
          <window.TweakRadio label="KPI card style" value={t.heroStyle}
                             options={[{value:'spark', label:'Sparkline-forward'}, {value:'numeric', label:'Numeric only'}]}
                             onChange={v => setTweak('heroStyle', v)} />
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
