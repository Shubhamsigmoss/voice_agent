// Small inline icons (no icon font, no emoji). All use currentColor.
const base = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

export const MicIcon = (p) => (
  <svg {...base} {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v3" />
  </svg>
);

export const StopIcon = (p) => (
  <svg {...base} {...p}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" />
  </svg>
);

export const SendIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M5 12h13" />
    <path d="M13 6l6 6-6 6" />
  </svg>
);

export const SpeakerIcon = ({ muted, ...p }) => (
  <svg {...base} {...p}>
    <path d="M4 10v4h4l5 4V6L8 10H4z" fill="currentColor" stroke="none" />
    {muted ? (
      <path d="M17 9l5 6M22 9l-5 6" />
    ) : (
      <>
        <path d="M16.5 8.5a5 5 0 0 1 0 7" />
        <path d="M19.5 5.5a9 9 0 0 1 0 13" />
      </>
    )}
  </svg>
);

export const PlayIcon = (p) => (
  <svg {...base} width={16} height={16} {...p}>
    <path d="M7 5l12 7-12 7V5z" fill="currentColor" stroke="none" />
  </svg>
);
