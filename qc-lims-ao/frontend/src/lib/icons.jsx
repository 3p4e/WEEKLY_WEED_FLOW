// Inline stroke icons (20×20 viewBox) ported from the prototype's GF.ICONS /
// QC.ICONS dictionaries. Rendered as <Icon name="..." /> — matches the prototype
// `.icon` class so the reused CSS styles them identically.

export const ICONS = {
  search: 'M17 17l-3.2-3.2M15.5 9.5a6 6 0 11-12 0 6 6 0 0112 0z',
  bell: 'M6 8a4 4 0 018 0c0 4 1.5 5 2 6H4c.5-1 2-2 2-6zM8.5 17a1.6 1.6 0 003 0',
  plus: 'M10 4v12M4 10h12',
  mic: 'M10 3a2.2 2.2 0 012.2 2.2v4.6a2.2 2.2 0 01-4.4 0V5.2A2.2 2.2 0 0110 3zM5 9.5a5 5 0 0010 0M10 14.5V17M7.5 17h5',
  chevL: 'M12 5l-5 5 5 5',
  chevR: 'M8 5l5 5-5 5',
  chevD: 'M5 8l5 5 5-5',
  chevU: 'M5 12l5-5 5 5',
  check: 'M4 10.5l4 4 8-9',
  clock: 'M10 5.5V10l3 1.8M10 3a7 7 0 100 14 7 7 0 000-14z',
  user: 'M10 10a3 3 0 100-6 3 3 0 000 6zM4.5 17a5.5 5.5 0 0111 0',
  flag: 'M5 3v14M5 3.5h9l-2 3 2 3H5',
  leaf: 'M4 16c8 0 12-4 12-12C8 4 4 8 4 16zM4 16c1.5-4 3.5-6 6-7.5',
  grid: 'M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z',
  timeline: 'M3 6h9M3 11h13M3 16h6M14 4v4M9 9v4M16 14v4',
  chat: 'M4 5h12v8H9l-3 3v-3H4z',
  link: 'M8 12l4-4M7.5 7.5L6 9a3 3 0 004.2 4.2l1.3-1.3M12.5 12.5L14 11a3 3 0 00-4.2-4.2L8.5 8',
  settings: 'M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM10 2.5v2M10 15.5v2M3.5 6l1.7 1M14.8 13l1.7 1M3.5 14l1.7-1M14.8 7l1.7-1',
  sun: 'M10 13a3 3 0 100-6 3 3 0 000 6zM10 2v2M10 16v2M2 10h2M16 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4',
  drop: 'M10 3s5 5.5 5 9a5 5 0 01-10 0c0-3.5 5-9 5-9z',
  box: 'M10 3l6 3v8l-6 3-6-3V6l6-3zM4 6l6 3 6-3M10 9v8',
  shield: 'M10 3l6 2v5c0 4-3 6-6 7-3-1-6-3-6-7V5l6-2z',
  wrench: 'M12.5 4a3.5 3.5 0 00-4.7 4.2l-4 4a1.5 1.5 0 002.1 2.1l4-4A3.5 3.5 0 0016 7l-2 2-1.5-1.5 2-2A3.5 3.5 0 0012.5 4z',
  flask: 'M8 3h4M9 3v5l-4 7a1.5 1.5 0 001.3 2.2h7.4A1.5 1.5 0 0015 15l-4-7V3M6.5 13h7',
  sparkle: 'M10 3l1.6 4.4L16 9l-4.4 1.6L10 15l-1.6-4.4L4 9l4.4-1.6L10 3z',
  arrowR: 'M4 10h12M11 5l5 5-5 5',
  trash: 'M4 6h12M8 6V4h4v2M6 6l1 11h6l1-11',
  menu: 'M3 6h14M3 10h14M3 14h14',
  trend: 'M3 14l4-5 3 3 5-7M14 5h2v2',
  calendar: 'M4 6h12v11H4zM4 6V4m12 2V4M7 3v3m6-3v3M4 9h12',
  at: 'M10 10m-3 0a3 3 0 106 0 3 3 0 00-6 0M13 10v1.5a2 2 0 004 0V10a7 7 0 10-3 5.7',
  forward: 'M4 5l6 5-6 5V5zM11 5l6 5-6 5V5z',
  x: 'M5 5l10 10M15 5L5 15',
  play: 'M6 4l9 6-9 6V4z',
  info: 'M10 9v5M10 6.5h.01M10 3a7 7 0 100 14 7 7 0 000-14z',
  doc: 'M5 3h7l3 3v11H5zM12 3v3h3',
  beaker: 'M8 3h4M9 3v5l-4 7a1.5 1.5 0 001.3 2.2h7.4A1.5 1.5 0 0015 15l-4-7V3',
  alert: 'M10 4l7 12H3l7-12zM10 9v3M10 14h.01',
  lock: 'M6 9V7a4 4 0 018 0v2M5 9h10v7H5z',
  layers: 'M10 3l7 4-7 4-7-4 7-4zM3 11l7 4 7-4M3 13l7 4 7-4',
};

export function Icon({ name, className = 'icon', stroke, style }) {
  const s = stroke ? { stroke, ...style } : style;
  return (
    <svg className={className} viewBox="0 0 20 20" style={s}>
      <path d={ICONS[name] || ''} />
    </svg>
  );
}
