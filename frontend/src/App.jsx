import { useCallback, useEffect, useState } from 'react';
import { api } from './api/client';
import { Icon } from './components/Icon';
import { StatusBadge } from './components/ui';
import { ChatWorkspace } from './components/ChatWorkspace';
import { KnowledgeBase } from './components/KnowledgeBase';
import { EvaluationDashboard } from './components/EvaluationDashboard';

const views = {
  ask: {
    label: 'Ask Copilot',
    shortLabel: 'Ask',
    icon: 'chat',
    title: 'Knowledge Copilot',
    description: 'Ask questions and inspect the evidence behind every answer.',
  },
  knowledge: {
    label: 'Knowledge Base',
    shortLabel: 'Documents',
    icon: 'library',
    title: 'Knowledge Base',
    description: 'Upload, index, and manage the documents your copilot can use.',
  },
  evaluation: {
    label: 'Evaluation',
    shortLabel: 'Evaluate',
    icon: 'chart',
    title: 'Evaluation & Observability',
    description: 'Compare retrieval strategies with measured, reproducible results.',
  },
};

function Sidebar({ activeView, setActiveView, documentCount, health, open, onClose }) {
  return (
    <>
      <button
        className={`sidebar-scrim ${open ? 'visible' : ''}`}
        aria-label="Close navigation"
        onClick={onClose}
        type="button"
      />
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Icon name="sparkle" size={23} /></div>
          <div>
            <strong>Knowledge Copilot</strong>
            <span>Enterprise RAG</span>
          </div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="Close navigation" type="button">
            <Icon name="close" />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {Object.entries(views).map(([key, view]) => (
            <button
              className={`nav-item ${activeView === key ? 'active' : ''}`}
              key={key}
              onClick={() => { setActiveView(key); onClose(); }}
              type="button"
            >
              <Icon name={view.icon} size={19} />
              <span>{view.label}</span>
              {key === 'knowledge' && documentCount > 0 && <small>{documentCount}</small>}
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <div className="sidebar-card-icon"><Icon name="shield" size={18} /></div>
          <strong>Evidence first</strong>
          <p>Answers are checked claim by claim before they reach you.</p>
        </div>

        <div className="sidebar-footer">
          <div>
            <span className={`service-indicator service-${health}`} />
            <div>
              <strong>Knowledge service</strong>
              <small>{health === 'online' ? 'All systems operational' : health === 'checking' ? 'Checking connection…' : 'Connection unavailable'}</small>
            </div>
          </div>
          <span className="version-tag">v1.0</span>
        </div>
      </aside>
    </>
  );
}

function MobileNavigation({ activeView, setActiveView }) {
  return (
    <nav className="mobile-navigation" aria-label="Mobile navigation">
      {Object.entries(views).map(([key, view]) => (
        <button
          className={activeView === key ? 'active' : ''}
          key={key}
          onClick={() => setActiveView(key)}
          type="button"
        >
          <Icon name={view.icon} size={20} />
          <span>{view.shortLabel}</span>
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState('ask');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState('checking');
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [toast, setToast] = useState(null);

  const notify = useCallback((message, tone = 'success') => {
    setToast({ message, tone, id: Date.now() });
  }, []);

  const loadDocuments = useCallback(async () => {
    setDocumentsLoading(true);
    try {
      const data = await api.getDocuments();
      setDocuments(data);
    } catch {
      setDocuments([]);
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        await api.getHealth();
        if (mounted) setHealth('online');
      } catch {
        if (mounted) setHealth('offline');
      }
    };
    checkHealth();
    loadDocuments();
    const timer = window.setInterval(checkHealth, 30000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [loadDocuments]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const view = views[activeView];
  const indexedDocumentCount = documents.filter((document) => ['indexed', 'ready', 'complete', 'completed'].includes(document.status)).length;

  return (
    <div className="app-shell">
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        documentCount={documents.length}
        health={health}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main-shell">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" type="button">
            <Icon name="menu" />
          </button>
          <div className="page-heading">
            <h1>{view.title}</h1>
            <p>{view.description}</p>
          </div>
          <div className="topbar-actions">
            <StatusBadge status={health} label={health === 'checking' ? 'Connecting' : health} />
            <div className="avatar" title="Enterprise user">EK</div>
          </div>
        </header>

        <div className={`workspace workspace-${activeView}`}>
          {activeView === 'ask' && (
            <ChatWorkspace
              documentCount={indexedDocumentCount}
              health={health}
              onNavigateDocuments={() => setActiveView('knowledge')}
              notify={notify}
            />
          )}
          {activeView === 'knowledge' && (
            <KnowledgeBase
              documents={documents}
              loading={documentsLoading}
              onRefresh={loadDocuments}
              notify={notify}
            />
          )}
          {activeView === 'evaluation' && <EvaluationDashboard notify={notify} />}
        </div>
      </main>

      <MobileNavigation activeView={activeView} setActiveView={setActiveView} />

      {toast && (
        <div className={`toast toast-${toast.tone}`} role="status">
          <Icon name={toast.tone === 'danger' ? 'alert' : 'check'} size={18} />
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)} aria-label="Dismiss notification" type="button"><Icon name="close" size={16} /></button>
        </div>
      )}
    </div>
  );
}
