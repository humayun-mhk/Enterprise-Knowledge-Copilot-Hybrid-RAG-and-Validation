const paths = {
  sparkle: <><path d="m12 3-1.2 3.8a6 6 0 0 1-3.9 3.9L3 12l3.9 1.3a6 6 0 0 1 3.9 3.9L12 21l1.2-3.8a6 6 0 0 1 3.9-3.9L21 12l-3.9-1.3a6 6 0 0 1-3.9-3.9L12 3Z"/><path d="M5 3v4M3 5h4M19 17v4M17 19h4"/></>,
  chat: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 9h8M8 13h5"/></>,
  library: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 7h8M8 11h6"/></>,
  chart: <><path d="M3 3v18h18"/><path d="m7 16 4-5 3 3 5-7"/></>,
  shield: <><path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3v8Z"/><path d="m9 12 2 2 4-4"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  close: <path d="m18 6-12 12M6 6l12 12"/>,
  search: <><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5M12 3v12"/></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
  check: <path d="m20 6-11 11-5-5"/>,
  refresh: <><path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5"/><path d="M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5"/></>,
  send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
  quote: <><path d="M3 21c3 0 7-1 7-8V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2h3"/><path d="M14 21c3 0 7-1 7-8V5c0-1.1-.9-2-2-2h-3c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2h3"/></>,
  eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  coins: <><ellipse cx="8" cy="5" rx="5" ry="3"/><path d="M3 5v4c0 1.7 2.2 3 5 3s5-1.3 5-3V5M3 9v4c0 1.7 2.2 3 5 3 1 0 2-.2 2.7-.5"/><path d="M13 11.5c.8-.3 1.9-.5 3-.5 2.8 0 5 1.3 5 3s-2.2 3-5 3-5-1.3-5-3 2.2-3 5-3Z"/><path d="M11 14v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4"/></>,
  gauge: <><path d="M20 16a8 8 0 1 0-16 0"/><path d="m12 12 4-4M4 20h16"/></>,
  trend: <><path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/></>,
  thumbUp: <><path d="M7 10v12H3V10h4ZM7 20h10.3a2 2 0 0 0 2-1.7l1.4-7A2 2 0 0 0 18.7 9H14l.7-3.2A3 3 0 0 0 11.8 2L7 10Z"/></>,
  thumbDown: <><path d="M7 14V2H3v12h4ZM7 4h10.3a2 2 0 0 1 2 1.7l1.4 7a2 2 0 0 1-2 2.3H14l.7 3.2a3 3 0 0 1-2.9 3.8L7 14Z"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/></>,
  layers: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></>,
  alert: <><path d="M10.3 2.9 1.8 17a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 2.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
  info: <><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  filter: <path d="M4 5h16M7 12h10M10 19h4"/>,
  more: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
  external: <><path d="M15 3h6v6M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>,
  copy: <><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
  arrowRight: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  xCircle: <><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></>,
  bolt: <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>,
};

export function Icon({ name, size = 20, className = '', strokeWidth = 1.8, ...props }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={strokeWidth}
      {...props}
    >
      {paths[name] || paths.info}
    </svg>
  );
}
