import { Icon } from './Icon';

export const formatPercent = (value, digits = 1) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  const normalized = Math.abs(number) <= 1 ? number * 100 : number;
  return `${normalized.toFixed(digits)}%`;
};

export const formatNumber = (value, digits = 0) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(number);
};

export const formatDuration = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number >= 1000 ? `${(number / 1000).toFixed(2)}s` : `${Math.round(number)}ms`;
};

export const formatCost = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: number < 0.01 ? 4 : 2,
    maximumFractionDigits: number < 0.01 ? 5 : 2,
  }).format(number);
};

export const formatBytes = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  if (number === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const unit = Math.min(Math.floor(Math.log(number) / Math.log(1024)), units.length - 1);
  return `${(number / 1024 ** unit).toFixed(unit ? 1 : 0)} ${units[unit]}`;
};

export const formatDate = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  }).format(date);
};

export function StatusBadge({ status = 'unknown', label }) {
  const key = String(status).toLowerCase().replaceAll('_', '-');
  const success = ['approved', 'indexed', 'healthy', 'online', 'complete', 'completed', 'ready'];
  const warning = ['revise', 'processing', 'indexing', 'uploaded', 'pending', 'warning'];
  const danger = ['rejected', 'failed', 'error', 'offline', 'insufficient-evidence'];
  const tone = success.includes(key) ? 'success' : warning.includes(key) ? 'warning' : danger.includes(key) ? 'danger' : 'neutral';
  return (
    <span className={`status-badge status-${tone}`}>
      <span className="status-dot" />
      {label || key.replaceAll('-', ' ')}
    </span>
  );
}

export function Spinner({ size = 18 }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-label="Loading" />;
}

export function EmptyState({ icon = 'info', title, description, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon name={icon} size={24} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function MetricCard({ icon, label, value, detail, tone = 'blue', loading = false }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon metric-${tone}`}><Icon name={icon} size={19} /></div>
      <div className="metric-body">
        <span>{label}</span>
        <strong>{loading ? <span className="skeleton skeleton-number" /> : value}</strong>
        {detail && <small>{detail}</small>}
      </div>
    </article>
  );
}

export function ConfidenceRing({ value, size = 38 }) {
  const valid = value !== null && value !== undefined && Number.isFinite(Number(value));
  const normalized = valid ? Math.max(0, Math.min(1, Number(value))) : 0;
  const radius = 15;
  const circumference = 2 * Math.PI * radius;
  return (
    <span className="confidence-ring" title={valid ? `${Math.round(normalized * 100)}% confidence` : 'Confidence unavailable'}>
      <svg width={size} height={size} viewBox="0 0 38 38" aria-hidden="true">
        <circle className="ring-track" cx="19" cy="19" r={radius} />
        <circle
          className="ring-value"
          cx="19"
          cy="19"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - normalized)}
        />
      </svg>
      <b>{valid ? Math.round(normalized * 100) : '—'}</b>
    </span>
  );
}
