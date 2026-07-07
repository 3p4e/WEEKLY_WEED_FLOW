/* @ds-bundle: {"format":4,"namespace":"GrowFlowDesignSystem_7accb1","components":[{"name":"Leaf","sourcePath":"components/brand/Leaf.jsx"},{"name":"GrowFlowLockup","sourcePath":"components/brand/Leaf.jsx"},{"name":"Warbird","sourcePath":"components/brand/Warbird.jsx"},{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"AvatarStack","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Chip","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"KpiTile","sourcePath":"components/data/KpiTile.jsx"},{"name":"BarRow","sourcePath":"components/data/KpiTile.jsx"},{"name":"Modal","sourcePath":"components/feedback/Modal.jsx"},{"name":"Toast","sourcePath":"components/feedback/Modal.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Switch","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Segmented","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Field","sourcePath":"components/forms/Input.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Textarea","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Input.jsx"},{"name":"NavItem","sourcePath":"components/nav/NavItem.jsx"},{"name":"DeptRow","sourcePath":"components/nav/NavItem.jsx"},{"name":"DayPill","sourcePath":"components/nav/NavItem.jsx"},{"name":"STATUS","sourcePath":"components/task/StatusPill.jsx"},{"name":"StatusPill","sourcePath":"components/task/StatusPill.jsx"},{"name":"PriorityTag","sourcePath":"components/task/StatusPill.jsx"},{"name":"DueBadge","sourcePath":"components/task/StatusPill.jsx"},{"name":"TypeChip","sourcePath":"components/task/StatusPill.jsx"},{"name":"RefCode","sourcePath":"components/task/StatusPill.jsx"},{"name":"TaskCard","sourcePath":"components/task/TaskCard.jsx"},{"name":"LeafMark","sourcePath":"uploads/files/LeafMark.jsx"}],"sourceHashes":{"components/brand/Leaf.jsx":"3735be31ee8a","components/brand/Warbird.jsx":"6b907e408f9d","components/core/Avatar.jsx":"e7ac782c33a9","components/core/Badge.jsx":"81ff295d0f98","components/core/Button.jsx":"dcf469b839d6","components/core/IconButton.jsx":"f344d61ef7c9","components/data/KpiTile.jsx":"0cd364ba6055","components/feedback/Modal.jsx":"13f8d463d634","components/forms/Checkbox.jsx":"75b8086c4e68","components/forms/Input.jsx":"4614d09d71f6","components/nav/NavItem.jsx":"2cdbf50829eb","components/task/StatusPill.jsx":"7760fb7f4cf0","components/task/TaskCard.jsx":"c6239e3de6f2","ui_kits/growflow/app.js":"4893de1cec45","ui_kits/growflow/data.js":"6bf56cb61e22","ui_kits/growflow/screens.js":"e99fb72a5bb5","ui_kits/growflow/tweaks-panel.js":"6591467622ed","uploads/files/LeafMark.jsx":"332656811acb","uploads/files/leaf-3d-object-package/leaf-3d-export/leaf-mark.js":"9c8b1e8be6f7"},"inlinedExternals":[],"unexposedExports":[{"name":"createLeafMark","sourcePath":"uploads/files/leaf-3d-object-package/leaf-3d-export/leaf-mark.js"}]} */

(() => {

const __ds_ns = (window.GrowFlowDesignSystem_7accb1 = window.GrowFlowDesignSystem_7accb1 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/brand/Leaf.jsx
try { (() => {
/** Shared 3D extruded leaf mark: layered depth + idle tilt (or `spin` for continuous fast rotation). */
function Leaf3D({
  width,
  height,
  spin = false,
  glow = true
}) {
  const layers = Array.from({
    length: 12
  });
  return /*#__PURE__*/React.createElement("span", {
    className: 'pp-leaf3d' + (spin ? ' pp-leaf3d--spin' : ''),
    style: {
      width,
      height,
      perspective: Math.max(width, height) * 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-leaf3d-inner",
    style: glow ? undefined : {
      filter: 'none'
    }
  }, layers.map((_, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    className: "pp-leaf3d-layer"
  })), /*#__PURE__*/React.createElement("span", {
    className: "pp-leaf3d-sheen"
  })));
}

/** The Purely Plant leaf mark — always rendered with 3D depth. `animated` adds the glow; `spinning` for continuous fast rotation (e.g. splash). */
function Leaf({
  size = 42,
  animated = false,
  spinning = false,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      ...style
    }
  }, /*#__PURE__*/React.createElement(Leaf3D, {
    width: size * 0.857,
    height: size,
    spin: spinning,
    glow: animated
  }));
}

/**
 * GrowFlow brand lockup — leaf + "GrowFlow" wordmark (green "Flow") +
 * optional "PURELY PLANT" sub-mark (the original logo's own wordmark asset).
 */
function GrowFlowLockup({
  size = 'md',
  leaf = true,
  gradient = true,
  sub = true,
  onDark = false,
  match = false,
  style = {}
}) {
  const scale = {
    sm: 0.85,
    md: 1,
    lg: 1.4
  }[size] || 1;
  const wmMul = match ? 1.96 : 1.3;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 11 * scale,
      ...style
    }
  }, leaf && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block'
    }
  }, /*#__PURE__*/React.createElement(Leaf3D, {
    width: 30 * scale,
    height: 35 * scale
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      lineHeight: 1
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: 'gf-wordmark' + (gradient ? ' gf-wordmark--gradient' : '') + (onDark ? ' gf-wordmark--on-dark' : ''),
    style: {
      fontSize: `calc(var(--fs-19) * ${scale} * ${wmMul})`,
      textAlign: 'center'
    }
  }, "Grow", /*#__PURE__*/React.createElement("b", null, "Flow")), sub && /*#__PURE__*/React.createElement("span", {
    className: 'pp-wordmark' + (onDark ? ' pp-wordmark--white' : ''),
    style: {
      width: 172 * scale,
      height: 172 / 6.155 * scale,
      marginTop: 7,
      alignSelf: 'center',
      opacity: onDark ? 0.95 : 0.8
    }
  })));
}
Object.assign(__ds_scope, { Leaf, GrowFlowLockup });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/brand/Leaf.jsx", error: String((e && e.message) || e) }); }

// components/brand/Warbird.jsx
try { (() => {
/**
 * Imperial insignia — an ORIGINAL heraldic mark (not any trademarked emblem):
 * a swept double-chevron "raptor" with a plasma core, evoking the Romulan-console
 * aesthetic of the GrowFlow reskin. Use as a watermark, sidebar crest, or seal.
 *
 * `variant`: 'solid' (filled plasma) | 'line' (etched hairline) | 'ghost' (faint watermark).
 */
function Warbird({
  size = 40,
  variant = 'solid',
  glow = true,
  color = 'var(--primary)',
  style = {}
}) {
  const stroke = variant === 'solid' ? 'none' : color;
  const fill = variant === 'solid' ? color : 'none';
  const op = variant === 'ghost' ? 0.14 : 1;
  const sw = variant === 'line' ? 1.4 : 2.2;
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 64 64",
    fill: "none",
    role: "img",
    "aria-label": "GrowFlow crest",
    style: {
      display: 'inline-block',
      opacity: op,
      filter: glow && variant !== 'ghost' ? 'drop-shadow(0 0 6px color-mix(in oklab, ' + color + ' 55%, transparent))' : 'none',
      ...style
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M32 7 L60 22 L47 26 L32 17 L17 26 L4 22 Z",
    fill: fill,
    stroke: stroke,
    strokeWidth: sw,
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M32 20 L52 31 L41 35 L32 29 L23 35 L12 31 Z",
    fill: fill,
    stroke: stroke,
    strokeWidth: sw,
    strokeLinejoin: "round",
    opacity: variant === 'solid' ? 0.85 : 1
  }), /*#__PURE__*/React.createElement("path", {
    d: "M32 30 L37 45 L32 58 L27 45 Z",
    fill: fill,
    stroke: stroke,
    strokeWidth: sw,
    strokeLinejoin: "round",
    opacity: variant === 'solid' ? 0.7 : 1
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "32",
    cy: "26",
    r: "3.4",
    fill: variant === 'solid' ? 'var(--bg, #05140d)' : color
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "32",
    cy: "26",
    r: "1.5",
    fill: color
  }));
}
Object.assign(__ds_scope, { Warbird });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/brand/Warbird.jsx", error: String((e && e.message) || e) }); }

// components/core/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const PALETTE = ['var(--av-1)', 'var(--av-2)', 'var(--av-3)', 'var(--av-4)', 'var(--av-5)', 'var(--av-6)', 'var(--av-7)', 'var(--av-8)', 'var(--av-9)', 'var(--av-10)'];
function initials(name = '') {
  const p = String(name).trim().split(/\s+/);
  return ((p[0]?.[0] || '') + (p[1]?.[0] || '')).toUpperCase() || '?';
}
function colorFor(name = '', override) {
  if (override) return override;
  let h = 0;
  for (let i = 0; i < name.length; i++) h = h * 31 + name.charCodeAt(i) >>> 0;
  return PALETTE[h % PALETTE.length];
}

/** Circular initials avatar, brand-colored from a 10-color palette. */
function Avatar({
  name = '',
  size = 32,
  color,
  ring = true,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    title: name,
    style: {
      width: size,
      height: size,
      borderRadius: 999,
      flexShrink: 0,
      background: colorFor(name, color),
      color: '#fff',
      fontWeight: 700,
      fontSize: Math.round(size * 0.4),
      letterSpacing: '.2px',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: ring ? '0 0 0 2px var(--surface)' : 'none',
      ...style
    }
  }, rest), initials(name));
}

/** Overlapping stack of avatars (owner + helpers). Collapses overflow to +N. */
function AvatarStack({
  people = [],
  size = 28,
  max = 4
}) {
  const shown = people.slice(0, max);
  const extra = people.length - shown.length;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      paddingLeft: size * 0.32
    }
  }, shown.map((p, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      marginLeft: -size * 0.32
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: typeof p === 'string' ? p : p.name,
    color: p.color,
    size: size
  }))), extra > 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: -size * 0.32,
      width: size,
      height: size,
      borderRadius: 999,
      background: 'var(--surface-3)',
      color: 'var(--text-body)',
      fontWeight: 700,
      fontSize: Math.round(size * 0.36),
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 0 0 2px var(--surface)'
    }
  }, "+", extra));
}
Object.assign(__ds_scope, { Avatar, AvatarStack });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Small label chip. tone maps to the semantic palette; `soft` uses tinted bg. */
function Badge({
  tone = 'neutral',
  soft = true,
  icon = null,
  children,
  style = {},
  ...rest
}) {
  const map = {
    neutral: {
      fg: 'var(--text-body)',
      solid: 'var(--ink-3)',
      soft: 'var(--surface-3)'
    },
    green: {
      fg: 'var(--green-700)',
      solid: 'var(--green-500)',
      soft: 'var(--green-100)'
    },
    blue: {
      fg: 'var(--blue-700)',
      solid: 'var(--blue)',
      soft: 'var(--blue-soft)'
    },
    orange: {
      fg: 'var(--orange-700)',
      solid: 'var(--orange)',
      soft: 'var(--orange-soft)'
    },
    red: {
      fg: 'var(--red-700)',
      solid: 'var(--red)',
      soft: 'var(--red-soft)'
    },
    amber: {
      fg: 'var(--amber-700)',
      solid: 'var(--amber)',
      soft: 'var(--amber-soft)'
    },
    violet: {
      fg: 'var(--violet-700)',
      solid: 'var(--violet)',
      soft: 'var(--violet-soft)'
    }
  }[tone] || {};
  const solidStyle = {
    background: map.solid,
    color: '#fff'
  };
  const softStyle = {
    background: map.soft,
    color: map.fg
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      lineHeight: 1,
      padding: '4px 9px',
      borderRadius: 'var(--r-full)',
      whiteSpace: 'nowrap',
      ...(soft ? softStyle : solidStyle),
      ...style
    }
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 12,
      display: 'inline-flex'
    }
  }, icon), children);
}

/** Selectable / static chip (filter chips, RACI helper chips, options). */
function Chip({
  selected = false,
  onClick,
  icon = null,
  children,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("span", _extends({
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontSize: 'var(--fs-12)',
      fontWeight: 700,
      cursor: onClick ? 'pointer' : 'default',
      padding: '7px 12px',
      borderRadius: 'var(--r-sm)',
      userSelect: 'none',
      border: '1px solid ' + (selected ? 'var(--primary)' : 'var(--border-default)'),
      background: selected ? 'var(--primary-soft)' : hover && onClick ? 'var(--surface-2)' : 'var(--surface-2)',
      color: selected ? 'var(--primary-fg)' : 'var(--text-body)',
      transition: 'all var(--dur-ui)',
      ...style
    }
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 14,
      height: 14,
      display: 'inline-flex'
    }
  }, icon), children);
}
Object.assign(__ds_scope, { Badge, Chip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * GrowFlow primary action button. Green is the hero — `primary` is the
 * Purely Plant green. Also: orange (voice/new-task CTA), ghost, danger.
 */
function Button({
  variant = 'primary',
  size = 'md',
  icon = null,
  iconRight = null,
  disabled = false,
  full = false,
  children,
  style = {},
  ...rest
}) {
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: size === 'sm' ? 6 : 7,
    fontFamily: 'var(--font-label)',
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    textTransform: 'uppercase',
    letterSpacing: '0.10em',
    borderRadius: 'var(--r-sm)',
    border: '1px solid transparent',
    clipPath: 'var(--clip-bevel)',
    transition: 'background var(--dur-ui) var(--ease-out), filter var(--dur-ui), transform var(--dur-micro)',
    whiteSpace: 'nowrap',
    opacity: disabled ? 0.5 : 1,
    width: full ? '100%' : undefined
  };
  const sizes = {
    sm: {
      fontSize: 'var(--fs-12)',
      padding: '6px 12px'
    },
    md: {
      fontSize: 'var(--fs-13)',
      padding: '9px 16px'
    },
    lg: {
      fontSize: 'var(--fs-15)',
      padding: '12px 22px'
    }
  };
  const variants = {
    primary: {
      background: 'var(--primary)',
      color: 'var(--text-on-brand)',
      filter: 'drop-shadow(0 2px 6px rgba(0,0,0,.5)) drop-shadow(0 0 11px color-mix(in oklab, var(--primary) 45%, transparent))'
    },
    orange: {
      background: 'var(--orange)',
      color: '#0b0f06',
      filter: 'drop-shadow(0 2px 6px rgba(0,0,0,.5)) drop-shadow(0 0 11px rgba(224,167,62,.42))'
    },
    secondary: {
      background: 'var(--surface-2)',
      color: 'var(--text-body)',
      borderColor: 'var(--border-strong)'
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-body)'
    },
    danger: {
      background: 'var(--red-soft)',
      color: 'var(--red)',
      borderColor: 'var(--red-700)'
    }
  };
  const [hover, setHover] = React.useState(false);
  const hoverStyle = !disabled && hover ? {
    primary: {
      background: 'var(--primary-hover)',
      filter: 'drop-shadow(0 2px 8px rgba(0,0,0,.55)) drop-shadow(0 0 18px color-mix(in oklab, var(--primary) 70%, transparent))',
      transform: 'translateY(-1px)'
    },
    orange: {
      background: 'var(--orange-700)',
      filter: 'drop-shadow(0 2px 8px rgba(0,0,0,.55)) drop-shadow(0 0 18px rgba(224,167,62,.6))',
      transform: 'translateY(-1px)'
    },
    secondary: {
      background: 'var(--surface-3)',
      borderColor: 'var(--primary)'
    },
    ghost: {
      background: 'var(--surface-2)',
      color: 'var(--primary-fg)'
    },
    danger: {
      background: 'var(--red)',
      color: '#fff',
      filter: 'drop-shadow(0 0 16px var(--focus-ring-red, rgba(224,90,90,.5)))'
    }
  }[variant] : {};
  const ic = {
    width: size === 'lg' ? 18 : 16,
    height: size === 'lg' ? 18 : 16,
    display: 'inline-flex',
    flexShrink: 0
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      ...base,
      ...sizes[size],
      ...variants[variant],
      ...hoverStyle,
      ...style
    }
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: ic
  }, icon), children, iconRight && /*#__PURE__*/React.createElement("span", {
    style: ic
  }, iconRight));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Square icon-only button (header actions, card mini-actions). */
function IconButton({
  size = 'md',
  variant = 'default',
  active = false,
  badge = null,
  children,
  style = {},
  ...rest
}) {
  const dim = size === 'sm' ? 32 : size === 'lg' ? 44 : 38;
  const [hover, setHover] = React.useState(false);
  const variants = {
    default: {
      background: active ? 'var(--primary-soft)' : 'var(--surface)',
      color: active ? 'var(--primary-fg)' : 'var(--text-body)',
      border: '1px solid var(--border-default)'
    },
    ghost: {
      background: hover ? 'var(--surface-2)' : 'transparent',
      color: 'var(--text-body)',
      border: '1px solid transparent'
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      width: dim,
      height: dim,
      borderRadius: 'var(--r-sm)',
      flexShrink: 0,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      position: 'relative',
      transition: 'background var(--dur-ui)',
      background: hover && variant === 'default' ? 'var(--surface-2)' : undefined,
      ...variants[variant],
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      display: 'inline-flex'
    }
  }, children), badge != null && /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: -4,
      right: -4,
      minWidth: 16,
      height: 16,
      padding: '0 4px',
      borderRadius: 999,
      background: 'var(--orange)',
      color: '#fff',
      fontSize: 10,
      fontWeight: 700,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '2px solid var(--surface)'
    }
  }, badge));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/data/KpiTile.jsx
try { (() => {
/** Big-number KPI tile for the dashboard telemetry. */
function KpiTile({
  value,
  label,
  tone = 'neutral',
  icon = null,
  delta = null,
  style = {}
}) {
  const toneColor = {
    neutral: 'var(--text-strong)',
    green: 'var(--green-600)',
    orange: 'var(--orange-700)',
    blue: 'var(--blue-700)',
    red: 'var(--red-700)',
    violet: 'var(--violet-700)'
  }[tone];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-md)',
      padding: '15px 16px',
      boxShadow: 'var(--sh-1)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-28)',
      fontWeight: 800,
      letterSpacing: '-.02em',
      color: toneColor,
      lineHeight: 1
    }
  }, value), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      color: toneColor,
      opacity: .8,
      display: 'inline-flex'
    }
  }, icon)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--fs-12)',
      fontWeight: 700,
      color: 'var(--text-body)',
      marginTop: 6
    }
  }, label), delta != null && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      color: 'var(--text-muted)',
      marginTop: 2
    }
  }, delta));
}

/** Horizontal bar row (status / department / person breakdowns). */
function BarRow({
  label,
  value,
  max = 100,
  color = 'var(--primary)',
  dot = null,
  style = {}
}) {
  const pct = Math.max(0, Math.min(100, value / max * 100));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      width: 140,
      flexShrink: 0,
      fontSize: 'var(--fs-13)',
      fontWeight: 600,
      color: 'var(--text-body)'
    }
  }, dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 9,
      height: 9,
      borderRadius: 999,
      background: dot,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, label)), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      height: 8,
      borderRadius: 999,
      background: 'var(--surface-3)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'block',
      height: '100%',
      width: pct + '%',
      borderRadius: 999,
      background: color,
      transition: 'width var(--dur-panel) var(--ease-out)'
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 34,
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--fs-12)',
      fontWeight: 600,
      color: 'var(--text-strong)'
    }
  }, value));
}
Object.assign(__ds_scope, { KpiTile, BarRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/KpiTile.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Modal.jsx
try { (() => {
/** Centered modal sheet with overlay, header, body, footer. */
function Modal({
  open = true,
  title,
  onClose,
  children,
  footer = null,
  width = 480,
  dark = false,
  style = {}
}) {
  if (!open) return null;
  const surface = dark ? 'var(--navy-900)' : 'var(--surface-card)';
  const text = dark ? '#fff' : 'var(--text-strong)';
  const border = dark ? 'rgba(255,255,255,.1)' : 'var(--border-default)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 500,
      background: 'var(--overlay)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
      animation: 'gf-overlay-in var(--dur-ui) var(--ease-out)'
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      background: surface,
      color: text,
      borderRadius: 'var(--r-2xl)',
      boxShadow: 'var(--sh-3)',
      border: '1px solid var(--border-strong)',
      width: '100%',
      maxWidth: width,
      maxHeight: '90vh',
      overflowY: 'auto',
      animation: 'gf-modal-in var(--dur-panel) var(--ease-spring)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 22px',
      borderBottom: '1px solid ' + border
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontFamily: 'var(--font-display)',
      fontSize: 'var(--fs-15)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.08em'
    }
  }, title), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      left: 0,
      bottom: -1,
      height: 2,
      width: 64,
      background: 'var(--primary)',
      boxShadow: 'var(--sh-glow)'
    }
  }), onClose && /*#__PURE__*/React.createElement("span", {
    onClick: onClose,
    style: {
      cursor: 'pointer',
      color: dark ? 'rgba(255,255,255,.7)' : 'var(--text-muted)',
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "20",
    height: "20",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M5 5l10 10M15 5L5 15"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px 22px'
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '16px 22px',
      borderTop: '1px solid ' + border,
      display: 'flex',
      gap: 10,
      justifyContent: 'flex-end'
    }
  }, footer)));
}

/** Toast notification (left-accent by tone). */
function Toast({
  tone = 'info',
  icon = null,
  children,
  onClose,
  style = {}
}) {
  const accent = {
    success: 'var(--green-500)',
    error: 'var(--red)',
    info: 'var(--blue)',
    warning: 'var(--amber)'
  }[tone];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-strong)',
      borderLeft: '3px solid ' + accent,
      borderRadius: 'var(--r-md)',
      boxShadow: 'var(--sh-3)',
      padding: '12px 16px',
      fontSize: 'var(--fs-13)',
      fontWeight: 600,
      color: 'var(--text-strong)',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      minWidth: 220,
      animation: 'gf-toast-in var(--dur-panel) var(--ease-out)',
      ...style
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      color: accent,
      display: 'inline-flex',
      filter: 'drop-shadow(0 0 6px ' + accent + ')'
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, children), onClose && /*#__PURE__*/React.createElement("span", {
    onClick: onClose,
    style: {
      cursor: 'pointer',
      color: 'var(--text-muted)',
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M5 5l10 10M15 5L5 15"
  }))));
}
Object.assign(__ds_scope, { Modal, Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Modal.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
/** Round-square checkbox — fills green when checked (matches task done-check). */
function Checkbox({
  checked = false,
  onChange,
  size = 20,
  label = null,
  disabled = false,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 9,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    onClick: () => !disabled && onChange && onChange(!checked),
    style: {
      width: size,
      height: size,
      borderRadius: 7,
      flexShrink: 0,
      border: '2px solid ' + (checked ? 'var(--primary)' : 'var(--border-strong)'),
      background: checked ? 'var(--primary)' : 'transparent',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all var(--dur-ui)'
    }
  }, checked && /*#__PURE__*/React.createElement("svg", {
    width: size * 0.62,
    height: size * 0.62,
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "#fff",
    strokeWidth: "3",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 10.5l4 4 8-9"
  }))), label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-14)',
      fontWeight: 600,
      color: 'var(--text-strong)'
    }
  }, label));
}

/** Toggle switch (settings, language, AI backend). */
function Switch({
  checked = false,
  onChange,
  label = null,
  disabled = false,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    onClick: () => !disabled && onChange && onChange(!checked),
    style: {
      width: 40,
      height: 24,
      borderRadius: 999,
      flexShrink: 0,
      padding: 3,
      background: checked ? 'var(--primary)' : 'var(--border-strong)',
      transition: 'background var(--dur-ui)',
      display: 'inline-flex',
      justifyContent: checked ? 'flex-end' : 'flex-start'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      borderRadius: 999,
      background: '#fff',
      boxShadow: 'var(--sh-1)',
      transition: 'all var(--dur-ui)'
    }
  })), label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-14)',
      fontWeight: 600,
      color: 'var(--text-strong)'
    }
  }, label));
}

/** Segmented control (EN | МК language toggle, small view switches). */
function Segmented({
  options = [],
  value,
  onChange,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      gap: 2,
      background: 'var(--surface-2)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-sm)',
      padding: 3,
      ...style
    }
  }, options.map(o => {
    const val = typeof o === 'string' ? o : o.value;
    const lab = typeof o === 'string' ? o : o.label;
    const on = val === value;
    return /*#__PURE__*/React.createElement("span", {
      key: val,
      onClick: () => onChange && onChange(val),
      style: {
        padding: '5px 12px',
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        background: on ? 'var(--surface)' : 'transparent',
        color: on ? 'var(--text-strong)' : 'var(--text-muted)',
        boxShadow: on ? 'var(--sh-1)' : 'none',
        transition: 'all var(--dur-ui)'
      }
    }, lab);
  }));
}
Object.assign(__ds_scope, { Checkbox, Switch, Segmented });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Labeled form field wrapper (label + optional hint + control). */
function Field({
  label,
  hint,
  htmlFor,
  required = false,
  children,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 'var(--sp-4)',
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: htmlFor,
    style: {
      display: 'block',
      fontFamily: 'var(--font-label)',
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.1em',
      color: 'var(--text-muted)',
      marginBottom: 7
    }
  }, label, required && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--red)',
      marginLeft: 3
    }
  }, "*")), children, hint && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '6px 0 0',
      fontSize: 'var(--fs-11)',
      color: 'var(--text-muted)'
    }
  }, hint));
}
const controlBase = {
  width: '100%',
  fontFamily: 'var(--font-app)',
  fontSize: 'var(--fs-14)',
  color: 'var(--text-strong)',
  background: 'var(--surface-2)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--r-md)',
  padding: '10px 12px',
  outline: 'none',
  transition: 'border-color var(--dur-ui), box-shadow var(--dur-ui)'
};
function useFocusRing() {
  const [f, setF] = React.useState(false);
  const props = {
    onFocus: e => {
      setF(true);
    },
    onBlur: () => setF(false)
  };
  const ring = f ? {
    borderColor: 'var(--primary)',
    boxShadow: 'var(--sh-focus)'
  } : {};
  return [ring, props];
}

/** Text input. */
function Input({
  icon = null,
  style = {},
  ...rest
}) {
  const [ring, fp] = useFocusRing();
  if (icon) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        ...controlBase,
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '0 12px',
        ...ring
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 16,
        height: 16,
        color: 'var(--text-muted)',
        display: 'inline-flex'
      }
    }, icon), /*#__PURE__*/React.createElement("input", _extends({}, fp, rest, {
      style: {
        flex: 1,
        border: 'none',
        background: 'none',
        outline: 'none',
        padding: '10px 0',
        fontFamily: 'inherit',
        fontSize: 'var(--fs-14)',
        color: 'var(--text-strong)',
        ...style
      }
    })));
  }
  return /*#__PURE__*/React.createElement("input", _extends({}, fp, rest, {
    style: {
      ...controlBase,
      ...ring,
      ...style
    }
  }));
}

/** Multi-line textarea. */
function Textarea({
  rows = 3,
  style = {},
  ...rest
}) {
  const [ring, fp] = useFocusRing();
  return /*#__PURE__*/React.createElement("textarea", _extends({
    rows: rows
  }, fp, rest, {
    style: {
      ...controlBase,
      resize: 'vertical',
      minHeight: 64,
      ...ring,
      ...style
    }
  }));
}

/** Native select styled to match. */
function Select({
  children,
  style = {},
  ...rest
}) {
  const [ring, fp] = useFocusRing();
  return /*#__PURE__*/React.createElement("select", _extends({}, fp, rest, {
    style: {
      ...controlBase,
      appearance: 'none',
      cursor: 'pointer',
      backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'16\' height=\'16\' fill=\'none\' stroke=\'%237385A0\' stroke-width=\'2\' stroke-linecap=\'round\'%3E%3Cpath d=\'M4 6l4 4 4-4\'/%3E%3C/svg%3E")',
      backgroundRepeat: 'no-repeat',
      backgroundPosition: 'right 12px center',
      paddingRight: 34,
      ...ring,
      ...style
    }
  }), children);
}
Object.assign(__ds_scope, { Field, Input, Textarea, Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/nav/NavItem.jsx
try { (() => {
/** Sidebar nav item — icon + label, active = soft-green pill. */
function NavItem({
  icon = null,
  label,
  active = false,
  badge = null,
  dot = false,
  onClick,
  style = {}
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      gap: 11,
      padding: '10px 12px 10px 14px',
      borderRadius: 'var(--r-sm)',
      cursor: 'pointer',
      fontWeight: active ? 700 : 600,
      fontSize: 'var(--fs-14)',
      fontFamily: active ? 'var(--font-label)' : 'var(--font-app)',
      letterSpacing: active ? '0.06em' : 0,
      textTransform: active ? 'uppercase' : 'none',
      color: active ? 'var(--primary-fg)' : 'var(--text-body)',
      background: active ? 'var(--primary-soft)' : hover ? 'var(--surface-2)' : 'transparent',
      boxShadow: active ? 'inset 2px 0 0 var(--primary), 0 0 18px rgba(35,200,138,.12)' : 'none',
      transition: 'background var(--dur-ui), color var(--dur-ui)',
      ...style
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      display: 'inline-flex',
      color: active ? 'var(--primary)' : 'var(--text-muted)',
      filter: active ? 'drop-shadow(0 0 6px rgba(35,200,138,.6))' : 'none'
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, label), badge != null && /*#__PURE__*/React.createElement("span", {
    style: {
      background: 'var(--primary)',
      color: 'var(--text-on-brand)',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: 'var(--r-full)'
    }
  }, badge), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: 999,
      background: 'var(--red)',
      boxShadow: 'var(--sh-glow-red)'
    }
  }));
}

/** Department row — color dot + name + count. */
function DeptRow({
  color,
  name,
  count,
  active = false,
  onClick,
  style = {}
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '7px 12px',
      borderRadius: 'var(--r-sm)',
      cursor: 'pointer',
      fontSize: 'var(--fs-13)',
      fontWeight: 600,
      color: active ? 'var(--text-strong)' : 'var(--text-body)',
      background: active ? 'var(--surface-3)' : hover ? 'var(--surface-2)' : 'transparent',
      transition: 'background var(--dur-ui)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 9,
      height: 9,
      borderRadius: 999,
      background: color,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, name), count != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      color: 'var(--text-muted)'
    }
  }, count));
}

/** Day pill (Mon–Sun) with a count; active = dark ink fill. */
function DayPill({
  day,
  count,
  active = false,
  onClick,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("span", {
    onClick: onClick,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '7px 13px',
      borderRadius: 'var(--r-full)',
      cursor: 'pointer',
      fontSize: 'var(--fs-12)',
      fontWeight: 700,
      userSelect: 'none',
      border: '1px solid ' + (active ? 'var(--ink)' : 'var(--border-default)'),
      background: active ? 'var(--ink)' : 'var(--surface)',
      color: active ? '#fff' : 'var(--text-body)',
      transition: 'all var(--dur-ui)',
      ...style
    }
  }, day, count != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-10)',
      minWidth: 18,
      textAlign: 'center',
      padding: '1px 6px',
      borderRadius: 999,
      background: active ? 'rgba(255,255,255,.22)' : 'var(--surface-3)',
      color: active ? '#fff' : 'var(--text-body)'
    }
  }, count));
}
Object.assign(__ds_scope, { NavItem, DeptRow, DayPill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/nav/NavItem.jsx", error: String((e && e.message) || e) }); }

// components/task/StatusPill.jsx
try { (() => {
const STATUS = {
  pending: {
    label: 'Not started',
    labelMk: 'Не започнато',
    dot: 'var(--st-pending)',
    fg: 'var(--text-body)',
    bg: 'var(--surface-3)'
  },
  working: {
    label: 'Working on it',
    labelMk: 'Во тек',
    dot: 'var(--st-working)',
    fg: 'var(--orange)',
    bg: 'var(--orange-soft)'
  },
  review: {
    label: 'In review',
    labelMk: 'На преглед',
    dot: 'var(--st-review)',
    fg: 'var(--blue)',
    bg: 'var(--blue-soft)'
  },
  stuck: {
    label: 'Stuck',
    labelMk: 'Блокирано',
    dot: 'var(--st-stuck)',
    fg: 'var(--red)',
    bg: 'var(--red-soft)'
  },
  postponed: {
    label: 'Postponed',
    labelMk: 'Одложено',
    dot: 'var(--st-postponed)',
    fg: 'var(--amber)',
    bg: 'var(--amber-soft)'
  },
  done: {
    label: 'Done',
    labelMk: 'Завршено',
    dot: 'var(--st-done)',
    fg: 'var(--primary-fg)',
    bg: 'var(--green-100)'
  }
};

/** Status pill — click to cycle/open picker. */
function StatusPill({
  status = 'pending',
  lang = 'en',
  onClick,
  style = {}
}) {
  const s = STATUS[status] || STATUS.pending;
  return /*#__PURE__*/React.createElement("span", {
    onClick: onClick,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 7,
      whiteSpace: 'nowrap',
      fontFamily: 'var(--font-label)',
      fontSize: 'var(--fs-12)',
      fontWeight: 700,
      lineHeight: 1,
      userSelect: 'none',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      padding: '5px 11px',
      borderRadius: 'var(--r-full)',
      cursor: onClick ? 'pointer' : 'default',
      color: s.fg,
      background: s.bg,
      border: '1px solid ' + s.bg,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: 999,
      background: s.dot,
      boxShadow: '0 0 8px ' + s.dot
    }
  }), lang === 'mk' ? s.labelMk : s.label);
}
const PRIORITY = {
  critical: {
    label: 'Critical',
    bg: 'var(--pr-critical)',
    fg: '#180305'
  },
  high: {
    label: 'High',
    bg: 'var(--pr-high)',
    fg: '#150f03'
  },
  medium: {
    label: 'Medium',
    bg: 'var(--pr-medium)',
    fg: '#03110f'
  },
  low: {
    label: 'Low',
    bg: 'var(--surface-3)',
    fg: 'var(--text-muted)'
  }
};

/** Priority tag. */
function PriorityTag({
  priority = 'medium',
  style = {}
}) {
  const p = PRIORITY[priority] || PRIORITY.medium;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-label)',
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      padding: '4px 9px',
      borderRadius: 'var(--r-full)',
      background: p.bg,
      color: p.fg,
      whiteSpace: 'nowrap',
      ...style
    }
  }, p.label);
}

/** Due badge — turns red when overdue. */
function DueBadge({
  label,
  overdue = false,
  icon = null,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: 'var(--r-xs)',
      whiteSpace: 'nowrap',
      background: overdue ? 'var(--red-soft)' : 'var(--surface-3)',
      color: overdue ? 'var(--red-700)' : 'var(--text-body)',
      ...style
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 12,
      display: 'inline-flex'
    }
  }, icon), label);
}

/** Task-type chip (CAPA / SOP / Validation / …). */
function TypeChip({
  children,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-label)',
      fontSize: 'var(--fs-10)',
      fontWeight: 700,
      letterSpacing: '.1em',
      textTransform: 'uppercase',
      padding: '2px 7px',
      borderRadius: 'var(--r-xs)',
      whiteSpace: 'nowrap',
      background: 'var(--violet-soft)',
      color: 'var(--violet)',
      border: '1px solid var(--violet-soft)',
      ...style
    }
  }, children);
}

/** Mono reference-code chip. */
function RefCode({
  children,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--fs-11)',
      fontWeight: 600,
      padding: '2px 6px',
      borderRadius: 5,
      whiteSpace: 'nowrap',
      background: 'var(--surface-3)',
      color: 'var(--text-body)',
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { STATUS, StatusPill, PriorityTag, DueBadge, TypeChip, RefCode });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/task/StatusPill.jsx", error: String((e && e.message) || e) }); }

// components/task/TaskCard.jsx
try { (() => {
const actionBtn = (primary, danger) => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  fontFamily: 'var(--font-app)',
  fontWeight: 700,
  fontSize: 'var(--fs-12)',
  padding: '7px 12px',
  borderRadius: 'var(--r-sm)',
  cursor: 'pointer',
  border: primary ? 'none' : '1px solid var(--border-default)',
  background: primary ? 'var(--primary)' : 'var(--surface-card)',
  color: primary ? 'var(--text-on-brand)' : danger ? 'var(--red)' : 'var(--text-body)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  transition: 'background var(--dur-ui)'
});
const Chevron = ({
  open
}) => /*#__PURE__*/React.createElement("svg", {
  width: "18",
  height: "18",
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "var(--ink-3)",
  strokeWidth: "1.8",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  style: {
    transform: open ? 'rotate(180deg)' : 'none',
    transition: 'transform var(--dur-ui)'
  }
}, /*#__PURE__*/React.createElement("path", {
  d: "M5 8l5 5 5-5"
}));
const Check = ({
  done,
  onClick
}) => /*#__PURE__*/React.createElement("span", {
  onClick: e => {
    e.stopPropagation();
    onClick && onClick();
  },
  style: {
    width: 20,
    height: 20,
    borderRadius: 'var(--r-xs)',
    flexShrink: 0,
    cursor: 'pointer',
    border: '2px solid ' + (done ? 'var(--primary)' : 'var(--border-strong)'),
    background: done ? 'var(--primary)' : 'transparent',
    boxShadow: done ? 'var(--sh-glow)' : 'none',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all var(--dur-ui)'
  }
}, done && /*#__PURE__*/React.createElement("svg", {
  width: "12",
  height: "12",
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "var(--text-on-brand)",
  strokeWidth: "3",
  strokeLinecap: "round",
  strokeLinejoin: "round"
}, /*#__PURE__*/React.createElement("path", {
  d: "M4 10.5l4 4 8-9"
})));

/**
 * The crafted task card — heart of GrowFlow. Collapsed shows status bar,
 * check, title, meta row, avatar stack, status pill, priority, chevron.
 * Expands in place to description, blocker, notes, dependencies, actions.
 */
function TaskCard({
  task = {},
  expanded: controlledExpanded,
  onToggle,
  onStatusClick,
  onCheck,
  lang = 'en',
  style = {},
  handoffTo,
  onEdit,
  onDelete,
  onAdvance,
  canEdit = true,
  canDelete = false
}) {
  const [internal, setInternal] = React.useState(false);
  const expanded = controlledExpanded ?? internal;
  const toggle = () => onToggle ? onToggle() : setInternal(v => !v);
  const {
    id,
    title,
    status = 'pending',
    priority = 'medium',
    people = [],
    due,
    overdue,
    type,
    refCode,
    hours,
    subtasks,
    tags = [],
    description,
    blocker,
    notes = [],
    deps = []
  } = task;
  const done = status === 'done';
  const L = lang === 'mk';
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: 'var(--surface-card)',
      border: '1px solid ' + (hover ? 'var(--border-strong)' : 'var(--border-default)'),
      borderLeft: '3px solid ' + __ds_scope.STATUS[status].dot,
      borderRadius: 'var(--r-lg)',
      boxShadow: hover ? 'var(--sh-2), 0 0 22px rgba(35,200,138,.10)' : 'var(--sh-1)',
      transition: 'box-shadow var(--dur-ui) var(--ease-out), border-color var(--dur-ui)',
      overflow: 'hidden',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: toggle,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '13px 15px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Check, {
    done: done,
    onClick: onCheck
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 700,
      fontSize: 'var(--fs-14)',
      letterSpacing: '-.01em',
      color: done ? 'var(--text-muted)' : 'var(--text-strong)',
      textDecoration: done ? 'line-through' : 'none'
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 4,
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--fs-11)',
      color: 'var(--text-muted)',
      flexWrap: 'wrap'
    }
  }, id && /*#__PURE__*/React.createElement("span", null, id), due && /*#__PURE__*/React.createElement(__ds_scope.DueBadge, {
    label: due,
    overdue: overdue
  }), type && /*#__PURE__*/React.createElement(__ds_scope.TypeChip, null, type), refCode && /*#__PURE__*/React.createElement(__ds_scope.RefCode, null, refCode), subtasks && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--blue-700)',
      fontWeight: 700
    }
  }, "\u2713 ", subtasks), hours && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--green-700)',
      fontWeight: 700
    }
  }, hours, "h"), tags.map(t => /*#__PURE__*/React.createElement("span", {
    key: t,
    style: {
      background: 'var(--blue-soft)',
      color: 'var(--blue-700)',
      padding: '1px 7px',
      borderRadius: 999,
      fontFamily: 'var(--font-app)',
      fontWeight: 700
    }
  }, t)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      flexShrink: 0
    }
  }, people.length > 0 && /*#__PURE__*/React.createElement(__ds_scope.AvatarStack, {
    people: people,
    size: 28
  }), /*#__PURE__*/React.createElement(__ds_scope.StatusPill, {
    status: status,
    lang: lang,
    onClick: e => {
      if (e) e.stopPropagation?.();
      onStatusClick && onStatusClick();
    }
  }), /*#__PURE__*/React.createElement(__ds_scope.PriorityTag, {
    priority: priority
  }), /*#__PURE__*/React.createElement(Chevron, {
    open: expanded
  }))), expanded && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 15px 15px',
      borderTop: '1px solid var(--line-2)',
      animation: 'gf-overlay-in var(--dur-ui) var(--ease-out)'
    }
  }, description && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--fs-13)',
      lineHeight: 1.55,
      color: 'var(--text-strong)',
      background: 'var(--surface-2)',
      border: '1px solid var(--line-2)',
      borderRadius: 'var(--r-md)',
      padding: '11px 13px',
      marginBottom: 14,
      whiteSpace: 'pre-wrap'
    }
  }, description), blocker && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      alignItems: 'center',
      background: 'var(--red-soft)',
      border: '1px solid rgba(229,72,77,.28)',
      borderRadius: 'var(--r-md)',
      padding: '11px 13px',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "17",
    height: "17",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "var(--red)",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M10 6v5M10 14h.01M10 3a7 7 0 100 14 7 7 0 000-14z"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 700,
      fontSize: 'var(--fs-13)',
      color: 'var(--red-700)'
    }
  }, blocker)), notes.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      letterSpacing: '.04em',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      marginBottom: 8
    }
  }, "Progress notes"), notes.map((n, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      gap: 10,
      padding: '7px 0',
      borderBottom: i < notes.length - 1 ? '1px dashed var(--line)' : 'none',
      fontSize: 'var(--fs-13)',
      color: 'var(--text-strong)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      color: 'var(--primary-fg)',
      fontSize: 'var(--fs-11)',
      flexShrink: 0,
      width: 34
    }
  }, n.date), /*#__PURE__*/React.createElement("span", null, n.text)))), deps.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 6,
      marginBottom: 14
    }
  }, deps.map((d, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      fontSize: 'var(--fs-12)',
      fontWeight: 600,
      padding: '4px 9px',
      borderRadius: 'var(--r-xs)',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      background: d.met ? 'var(--green-100)' : 'var(--red-soft)',
      color: d.met ? 'var(--green-700)' : 'var(--red-700)'
    }
  }, d.met ? '✓' : '⏳', " ", d.label))), handoffTo && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: 'linear-gradient(100deg, var(--blue-soft-2, var(--blue-soft)), var(--orange-soft-2, var(--orange-soft)))',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-md)',
      padding: '11px 13px',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "var(--ink-2)",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 10h12M11 5l5 5-5 5"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-12)',
      fontWeight: 700,
      color: 'var(--text-body)'
    }
  }, L ? 'Предавање кон' : 'Hands off to'), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--fs-13)',
      fontWeight: 800,
      color: 'var(--text-strong)'
    }
  }, handoffTo)), (onEdit || onAdvance || onDelete && canDelete) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 8,
      paddingTop: 14,
      borderTop: '1px solid var(--line-2)'
    }
  }, onAdvance && /*#__PURE__*/React.createElement("button", {
    onClick: e => {
      e.stopPropagation();
      onAdvance();
    },
    style: actionBtn(true)
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 10h12M11 5l5 5-5 5"
  })), L ? 'Напредни статус' : 'Advance status'), onEdit && canEdit && /*#__PURE__*/React.createElement("button", {
    onClick: e => {
      e.stopPropagation();
      onEdit();
    },
    style: actionBtn(false)
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M13 4l3 3-8 8H5v-3z"
  })), L ? 'Уреди' : 'Edit'), onDelete && canDelete && /*#__PURE__*/React.createElement("button", {
    onClick: e => {
      e.stopPropagation();
      onDelete();
    },
    style: actionBtn(false, true)
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10"
  })), L ? 'Избриши' : 'Delete'))));
}
Object.assign(__ds_scope, { TaskCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/task/TaskCard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/growflow/app.js
try { (() => {
// GrowFlow UI kit — interactive app composition. Uses design-system components.
(function () {
  const {
    GF_DEPARTMENTS,
    GF_HANDOFF,
    GF_TASK_TYPES,
    GF_ROLES,
    GF_ROLE_PERMS,
    GF_T,
    GF_PEOPLE,
    GF_PERSON,
    GF_TASKS
  } = window;
  const DS = window.GrowFlowDesignSystem_7accb1;
  const {
    Button,
    IconButton,
    Avatar,
    AvatarStack,
    Badge,
    Chip,
    Field,
    Input,
    Textarea,
    Select,
    Checkbox,
    Switch,
    Segmented,
    StatusPill,
    PriorityTag,
    TaskCard,
    KpiTile,
    BarRow,
    NavItem,
    DeptRow,
    DayPill,
    Modal,
    Toast,
    Leaf,
    GrowFlowLockup
  } = DS;
  const PopSelect = window.PopSelect;
  const Warbird = DS.Warbird || (() => null);
  const I = (name, sz = 18) => {
    const n = window.lucide && lucide.icons[name];
    if (!n) return null;
    const kids = n.find(Array.isArray) || [];
    return React.createElement('svg', {
      width: sz,
      height: sz,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round',
      strokeLinejoin: 'round'
    }, kids.map(([t, a], i) => React.createElement(t, {
      key: i,
      ...a
    })));
  };

  // ─── Tweaks: three expressive whole-feel levers, driven by design-system tokens ───
  const {
    useTweaks,
    TweaksPanel,
    TweakSection,
    TweakRadio,
    TweakColor
  } = window;
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "softness": "balanced",
    "accent": "#15A86B",
    "tempo": "lively",
    "logo": "leaf"
  } /*EDITMODE-END*/;

  // Softness — reshapes every corner radius + shadow at once (industrial ↔ pillowy).
  const SOFTNESS = {
    crisp: {
      '--r-sm': '3px',
      '--r-md': '5px',
      '--r-lg': '7px',
      '--r-xl': '9px',
      '--r-2xl': '11px',
      '--sh-1': '0 1px 1px rgba(16,35,60,.05)',
      '--sh-2': '0 2px 6px rgba(16,35,60,.07)',
      '--sh-3': '0 6px 18px rgba(16,35,60,.12)'
    },
    balanced: {},
    pillowy: {
      '--r-sm': '12px',
      '--r-md': '16px',
      '--r-lg': '22px',
      '--r-xl': '28px',
      '--r-2xl': '34px',
      '--sh-1': '0 2px 6px rgba(16,35,60,.09)',
      '--sh-2': '0 10px 26px rgba(16,35,60,.13)',
      '--sh-3': '0 24px 64px rgba(16,35,60,.22)'
    }
  };
  // Tempo — re-times every interactive transition (snappy ↔ cinematic).
  const TEMPO = {
    snappy: {
      '--dur-micro': '.05s',
      '--dur-ui': '.08s',
      '--dur-panel': '.13s'
    },
    lively: {},
    cinematic: {
      '--dur-micro': '.22s',
      '--dur-ui': '.4s',
      '--dur-panel': '.64s'
    }
  };
  // Accent — re-hues the whole brand from one chosen primary (green / blue / violet / amber).
  function hexRgb(h) {
    const n = parseInt(h.slice(1), 16);
    return [n >> 16 & 255, n >> 8 & 255, n & 255];
  }
  function mix(h, f) {
    const [r, g, b] = hexRgb(h);
    const j = c => Math.round(c * (1 - f));
    return `rgb(${j(r)},${j(g)},${j(b)})`;
  }
  function accentVars(hex) {
    const [r, g, b] = hexRgb(hex);
    return {
      '--primary': hex,
      '--primary-hover': mix(hex, 0.14),
      '--primary-soft': `rgba(${r},${g},${b},.13)`,
      '--primary-fg': mix(hex, 0.28),
      '--focus-ring': `rgba(${r},${g},${b},.32)`,
      '--sh-brand': `0 6px 18px rgba(${r},${g},${b},.30)`
    };
  }
  const FEEL_KEYS = ['--r-sm', '--r-md', '--r-lg', '--r-xl', '--r-2xl', '--sh-1', '--sh-2', '--sh-3', '--primary', '--primary-hover', '--primary-soft', '--primary-fg', '--focus-ring', '--sh-brand', '--dur-micro', '--dur-ui', '--dur-panel'];
  function useFeel(tw) {
    React.useEffect(() => {
      const root = document.documentElement;
      FEEL_KEYS.forEach(k => root.style.removeProperty(k));
      const merged = {
        ...(SOFTNESS[tw.softness] || {}),
        ...accentVars(tw.accent),
        ...(TEMPO[tw.tempo] || {})
      };
      Object.entries(merged).forEach(([k, v]) => root.style.setProperty(k, v));
    }, [tw.softness, tw.accent, tw.tempo]);
  }
  function FeelTweaks({
    tw,
    setTweak,
    lang
  }) {
    const L = lang === 'mk';
    return /*#__PURE__*/React.createElement(TweaksPanel, {
      title: "Tweaks"
    }, /*#__PURE__*/React.createElement(TweakSection, {
      label: L ? 'Мекост' : 'Softness'
    }), /*#__PURE__*/React.createElement(TweakRadio, {
      label: L ? 'Форма' : 'Shape',
      value: tw.softness,
      options: [{
        value: 'crisp',
        label: L ? 'Остро' : 'Crisp'
      }, {
        value: 'balanced',
        label: L ? 'Средно' : 'Balanced'
      }, {
        value: 'pillowy',
        label: L ? 'Меко' : 'Pillowy'
      }],
      onChange: v => setTweak('softness', v)
    }), /*#__PURE__*/React.createElement(TweakSection, {
      label: L ? 'Бренд акцент' : 'Brand accent'
    }), /*#__PURE__*/React.createElement(TweakColor, {
      label: L ? 'Примарна' : 'Primary',
      value: tw.accent,
      options: ['#15A86B', '#2A6FDB', '#7A5AE0', '#E8912A'],
      onChange: v => setTweak('accent', v)
    }), /*#__PURE__*/React.createElement(TweakSection, {
      label: L ? 'Темпо' : 'Tempo'
    }), /*#__PURE__*/React.createElement(TweakRadio, {
      label: L ? 'Движење' : 'Motion',
      value: tw.tempo,
      options: [{
        value: 'snappy',
        label: L ? 'Брзо' : 'Snappy'
      }, {
        value: 'lively',
        label: L ? 'Живо' : 'Lively'
      }, {
        value: 'cinematic',
        label: L ? 'Кино' : 'Cinematic'
      }],
      onChange: v => setTweak('tempo', v)
    }), /*#__PURE__*/React.createElement(TweakSection, {
      label: L ? 'Лого модел' : 'Logo model'
    }), /*#__PURE__*/React.createElement(TweakRadio, {
      label: L ? 'Знак' : 'Mark',
      value: tw.logo,
      options: [{
        value: 'leaf',
        label: L ? 'Лист' : 'Leaf'
      }, {
        value: 'borg',
        label: L ? 'Борг' : 'Borg'
      }],
      onChange: v => setTweak('logo', v)
    }));
  }
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const WEEK_LABELS = {
    en: ['Week 26', 'Week 27', 'Week 28'],
    mk: ['Недела 26', 'Недела 27', 'Недела 28']
  };
  const RISE = (i, dur = 0.55) => ({
    animation: `gfRise ${dur}s cubic-bezier(.22,.61,.36,1) backwards`,
    animationDelay: i * 0.09 + 's'
  });

  // ─── OBJ → BufferGeometry (v + triangulated f only; no normals/mtl needed) ───
  function parseOBJToGeometry(text, THREE) {
    const verts = [];
    const positions = [];
    const lines = text.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.charCodeAt(0) === 118 && line.charCodeAt(1) === 32) {
        // "v "
        const p = line.split(/\s+/);
        verts.push(+p[1], +p[2], +p[3]);
      } else if (line.charCodeAt(0) === 102 && line.charCodeAt(1) === 32) {
        // "f "
        const p = line.split(/\s+/);
        const idx = [];
        for (let k = 1; k < p.length; k++) {
          if (!p[k]) continue;
          let vi = parseInt(p[k], 10); // ignore /vt/vn if present
          if (vi < 0) vi = verts.length / 3 + vi + 1;
          idx.push(vi - 1);
        }
        for (let k = 1; k < idx.length - 1; k++) {
          // fan triangulate
          const tri = [idx[0], idx[k], idx[k + 1]];
          for (let m = 0; m < 3; m++) {
            const b = tri[m] * 3;
            positions.push(verts[b], verts[b + 1], verts[b + 2]);
          }
        }
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    return geo;
  }

  // ─── CSS fallback: deep extruded stack (used only if WebGL is unavailable) ───
  function LeafMarkCSS({
    size = 210,
    phase = ''
  }) {
    const DEPTH = 26;
    const stepZ = size * 0.17 / DEPTH; // thicker wall ≈ 17% of height
    const layers = Array.from({
      length: DEPTH
    }, (_, i) => {
      const t = i / (DEPTH - 1); // 0 = front face, 1 = deepest
      const bright = i === 0 ? 1.18 : 0.8 - t * 0.6;
      const sat = i === 0 ? 1.5 : 1.9;
      return /*#__PURE__*/React.createElement("span", {
        key: i,
        className: "gf-splash-layer",
        style: {
          transform: `translateZ(${-i * stepZ}px)`,
          filter: `brightness(${bright}) saturate(${sat}) contrast(${1 + t * 0.2})`,
          zIndex: DEPTH - i
        }
      });
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-stage",
      style: {
        width: size,
        height: size * 1.166
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: ('gf-splash-wobble ' + phase).trim()
    }, /*#__PURE__*/React.createElement("div", {
      className: ('gf-splash-spin ' + phase).trim()
    }, layers)), /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-shadow",
      style: {
        width: size * 0.7,
        height: size * 0.124
      }
    }));
  }

  // ─── Real 3D leaf — the uploaded solid mesh rendered in WebGL (Three.js) ───
  // Idle: slow Y-sweep + cross-axis wobble. Click: burst-spin, then settle flat.
  function LeafMark({
    size = 210,
    phase = ''
  }) {
    const mountRef = React.useRef(null);
    const phaseRef = React.useRef(phase);
    phaseRef.current = phase;
    const [failed, setFailed] = React.useState(false);
    React.useEffect(() => {
      const THREE = window.THREE;
      if (!THREE || !mountRef.current) {
        setFailed(true);
        return;
      }
      let renderer,
        raf,
        disposed = false;
      try {
        const width = size,
          height = Math.round(size * 1.166);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 6000);
        renderer = new THREE.WebGLRenderer({
          alpha: true,
          antialias: true,
          preserveDrawingBuffer: true
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        if ('outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.domElement.style.filter = 'drop-shadow(0 0 26px rgba(43,232,160,.55)) drop-shadow(0 0 12px rgba(47,217,217,.4))';
        mountRef.current.appendChild(renderer.domElement);

        // Plasma-green material + Tal Shiar lighting (green key, cyan rim)
        scene.add(new THREE.AmbientLight(0x22403a, 1.15));
        const key = new THREE.DirectionalLight(0xa9ffdb, 2.3);
        key.position.set(-0.7, 1.1, 1.3);
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x2fd9d9, 1.7);
        rim.position.set(1.1, 0.4, -0.9);
        scene.add(rim);
        const fill = new THREE.DirectionalLight(0x2be8a0, 0.85);
        fill.position.set(0.2, -1, 0.6);
        scene.add(fill);
        const mat = new THREE.MeshStandardMaterial({
          color: 0x1fb877,
          emissive: 0x0b6b45,
          emissiveIntensity: 0.5,
          metalness: 0.4,
          roughness: 0.32
        });
        const group = new THREE.Group();
        scene.add(group);
        fetch('../../assets/pp-leaf-3d.obj').then(r => r.text()).then(text => {
          if (disposed) return;
          const geo = parseOBJToGeometry(text, THREE);
          geo.center();
          geo.computeVertexNormals();
          geo.computeBoundingSphere();
          const R = geo.boundingSphere && geo.boundingSphere.radius || 40;
          group.add(new THREE.Mesh(geo, mat));
          camera.position.set(0, 0, R / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.02);
          camera.lookAt(0, 0, 0);
        }).catch(() => {
          if (!disposed) setFailed(true);
        });
        const D = THREE.MathUtils.degToRad;
        const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const t0 = performance.now();
        let prev = '',
          burstStart = 0,
          settleStart = 0,
          settleFrom = 0,
          settleTo = 0,
          lastRy = 0.28;
        function frame(now) {
          raf = requestAnimationFrame(frame);
          const ph = phaseRef.current;
          const t = (now - t0) / 1000;
          let ry, rx, rz;
          if (reduce) {
            ry = 0.2;
            rx = D(6);
            rz = 0;
          } else if (ph === 'burst') {
            if (prev !== 'burst') burstStart = now;
            const p = (now - burstStart) / 1000;
            ry = 0.28 + p * (2 * Math.PI * 3.0); // ~3 fast turns / sec
            rx = D(6 + 7 * Math.cos(t * 2 * Math.PI));
            rz = D(2.5 * Math.sin(t * 2 * Math.PI));
            lastRy = ry;
          } else if (ph === 'settle') {
            if (prev !== 'settle') {
              settleStart = now;
              settleFrom = lastRy;
              settleTo = Math.ceil(settleFrom / (2 * Math.PI)) * 2 * Math.PI; // forward to flat
            }
            const p = Math.min((now - settleStart) / 1000, 1);
            const e = 1 - Math.pow(1 - p, 3);
            ry = settleFrom + (settleTo - settleFrom) * e;
            rx = D(6) * (1 - e);
            rz = 0;
          } else {
            ry = 0.28 + 0.62 * (0.5 - 0.5 * Math.cos(t * 2 * Math.PI / 4.6)); // 16°→52° sweep
            rx = D(6.5 + 2.5 * Math.cos(t * 2 * Math.PI / 3.4)); // rock (period ≠ sweep)
            rz = D(1.2 * Math.sin(t * 2 * Math.PI / 3.4)); // twist
            lastRy = ry;
          }
          group.rotation.set(rx, ry, rz);
          renderer.render(scene, camera);
          prev = ph;
        }
        raf = requestAnimationFrame(frame);
      } catch (e) {
        setFailed(true);
      }
      return () => {
        disposed = true;
        if (raf) cancelAnimationFrame(raf);
        if (renderer) {
          renderer.dispose();
          const el = renderer.domElement;
          if (el && el.parentNode) el.parentNode.removeChild(el);
        }
      };
    }, [size]);
    if (failed) return /*#__PURE__*/React.createElement(LeafMarkCSS, {
      size: size,
      phase: phase
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-stage",
      style: {
        width: size,
        height: size * 1.166
      }
    }, /*#__PURE__*/React.createElement("div", {
      ref: mountRef,
      style: {
        width: size,
        height: size * 1.166
      }
    }), /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-shadow",
      style: {
        width: size * 0.7,
        height: size * 0.124
      }
    }));
  }

  // ─── Borgified leaf — GLB with baked neon-circuit materials, via <model-viewer> ───
  function LeafMarkBorg({
    size = 210,
    phase = ''
  }) {
    const ref = React.useRef(null);
    React.useEffect(() => {
      const el = ref.current;
      if (!el) return;
      // Spin faster during the burst, normal idle otherwise.
      el.setAttribute('rotation-per-second', phase === 'burst' ? '900deg' : '26deg');
    }, [phase]);
    return /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-stage",
      style: {
        width: size,
        height: size * 1.166
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: size,
        height: size * 1.166,
        filter: 'drop-shadow(0 0 26px rgba(43,232,160,.55)) drop-shadow(0 0 12px rgba(47,217,217,.4))'
      }
    }, React.createElement('model-viewer', {
      ref,
      src: '../../assets/PP_Leaf_Borg.glb',
      alt: 'Purely Plant Borg leaf mark',
      'auto-rotate': true,
      'auto-rotate-delay': 0,
      'rotation-per-second': '26deg',
      'interaction-prompt': 'none',
      'disable-zoom': true,
      'shadow-intensity': '0',
      exposure: '1.2',
      'environment-image': 'neutral',
      'camera-orbit': '25deg 80deg 108%',
      'field-of-view': '30deg',
      style: {
        width: '100%',
        height: '100%',
        background: 'transparent',
        pointerEvents: 'none'
      }
    })), /*#__PURE__*/React.createElement("div", {
      className: "gf-splash-shadow",
      style: {
        width: size * 0.7,
        height: size * 0.124
      }
    }));
  }

  // ─────────────────────────────── Splash ───────────────────────────────
  function Splash({
    onDone,
    lang,
    logo
  }) {
    const [phase, setPhase] = React.useState('idle'); // idle | burst | settle

    function enter() {
      if (phase !== 'idle') return;
      setPhase('burst');
      setTimeout(() => setPhase('settle'), 1000);
      setTimeout(onDone, 2000);
    }
    const spinPhase = phase === 'idle' ? '' : phase;
    const leaving = phase === 'settle';
    return /*#__PURE__*/React.createElement("div", {
      className: "gf-splash",
      style: {
        opacity: leaving ? 0 : 1,
        transform: leaving ? 'scale(1.14)' : 'scale(1)',
        transition: 'opacity 1s ease, transform 1s cubic-bezier(.3,.9,.4,1)'
      },
      onClick: enter
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 22,
        transform: leaving ? 'scale(1.06)' : 'scale(1)',
        transition: 'transform 1s cubic-bezier(.3,.9,.4,1)'
      }
    }, logo === 'borg' ? /*#__PURE__*/React.createElement(LeafMarkBorg, {
      size: 210,
      phase: spinPhase
    }) : /*#__PURE__*/React.createElement(LeafMark, {
      size: 210,
      phase: spinPhase
    }), /*#__PURE__*/React.createElement("div", {
      style: RISE(0, 0.5)
    }, /*#__PURE__*/React.createElement(GrowFlowLockup, {
      size: "lg",
      onDark: true,
      leaf: false,
      match: true
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        ...RISE(2, 0.5),
        fontSize: 12,
        fontWeight: 700,
        color: 'rgba(255,255,255,.4)',
        letterSpacing: '.02em'
      }
    }, lang === 'mk' ? 'Кликни за да продолжиш' : 'Tap the leaf to enter')));
  }

  // ─────────────────────────────── Login ───────────────────────────────
  function Login({
    onSignIn,
    lang,
    logo
  }) {
    const [mode, setMode] = React.useState('signin');
    const [user, setUser] = React.useState('qcm.blani');
    const [pass, setPass] = React.useState('password');
    const [resetUser, setResetUser] = React.useState('qcm.blani');
    const [error, setError] = React.useState(null);
    const [busy, setBusy] = React.useState(false);
    const t = GF_T[lang];
    function submitSignIn(e) {
      e && e.preventDefault();
      if (!user.trim() || !pass.trim()) {
        setError(lang === 'mk' ? 'Внесете корисничко име и лозинка.' : 'Enter a username and password.');
        return;
      }
      setError(null);
      setBusy(true);
      setTimeout(() => {
        setBusy(false);
        onSignIn();
      }, 380);
    }
    function submitForgot(e) {
      e && e.preventDefault();
      if (!resetUser.trim()) return;
      setBusy(true);
      setTimeout(() => {
        setBusy(false);
        setMode('sent');
      }, 420);
    }
    return /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        background: 'radial-gradient(120% 80% at 20% 0%, #0c2419 0%, var(--navy-900) 55%)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      "aria-hidden": true,
      style: {
        position: 'absolute',
        inset: 0,
        opacity: .5,
        backgroundImage: 'radial-gradient(circle at 15% 20%, rgba(43,232,160,.16), transparent 42%), radial-gradient(circle at 85% 82%, rgba(47,217,217,.14), transparent 46%)'
      }
    }), /*#__PURE__*/React.createElement("div", {
      "aria-hidden": true,
      style: {
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        opacity: .4,
        mixBlendMode: 'overlay',
        background: 'var(--scanlines), var(--plasma-grid)'
      }
    }), /*#__PURE__*/React.createElement("div", {
      "aria-hidden": true,
      style: {
        position: 'absolute',
        left: '50%',
        top: '50%',
        transform: 'translate(-50%,-50%)',
        pointerEvents: 'none'
      }
    }, /*#__PURE__*/React.createElement(Warbird, {
      size: 620,
      variant: "ghost",
      glow: false
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'relative',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 26
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: RISE(0)
    }, logo === 'borg' ? /*#__PURE__*/React.createElement(LeafMarkBorg, {
      size: 150
    }) : /*#__PURE__*/React.createElement(LeafMark, {
      size: 150
    })), /*#__PURE__*/React.createElement("div", {
      style: RISE(1)
    }, /*#__PURE__*/React.createElement(GrowFlowLockup, {
      size: "lg",
      onDark: true,
      leaf: false,
      match: true
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        ...RISE(3),
        background: 'var(--surface)',
        border: '1px solid var(--border-strong)',
        borderRadius: 'var(--r-2xl)',
        boxShadow: 'var(--sh-3)',
        padding: 26,
        width: 340,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        position: 'relative',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("span", {
      "aria-hidden": true,
      style: {
        position: 'absolute',
        top: 0,
        left: 24,
        right: 24,
        height: 2,
        background: 'var(--hairline-plasma)'
      }
    }), mode === 'signin' && /*#__PURE__*/React.createElement("form", {
      onSubmit: submitSignIn,
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: lang === 'mk' ? 'Корисничко име' : 'Username'
    }, /*#__PURE__*/React.createElement(Input, {
      value: user,
      onChange: e => setUser(e.target.value),
      placeholder: "qcm.blani"
    })), /*#__PURE__*/React.createElement(Field, {
      label: lang === 'mk' ? 'Лозинка' : 'Password'
    }, /*#__PURE__*/React.createElement(Input, {
      type: "password",
      value: pass,
      onChange: e => setPass(e.target.value),
      placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
    })), error && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 8,
        alignItems: 'center',
        background: 'var(--red-soft)',
        color: 'var(--red-700)',
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        borderRadius: 'var(--r-sm)',
        padding: '8px 11px'
      }
    }, I('CircleAlert', 15), error), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      full: true,
      size: "lg",
      disabled: busy
    }, busy ? lang === 'mk' ? 'Најавување…' : 'Signing in…' : t.signin), /*#__PURE__*/React.createElement("span", {
      onClick: () => {
        setError(null);
        setMode('forgot');
      },
      style: {
        alignSelf: 'center',
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--primary-fg)',
        cursor: 'pointer'
      }
    }, lang === 'mk' ? 'Заборавена лозинка?' : 'Forgot password?')), mode === 'forgot' && /*#__PURE__*/React.createElement("form", {
      onSubmit: submitForgot,
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 800,
        fontSize: 'var(--fs-15)',
        marginBottom: 4
      }
    }, lang === 'mk' ? 'Барање нова лозинка' : 'Request a password reset'), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: 0,
        fontSize: 'var(--fs-12)',
        color: 'var(--text-body)',
        lineHeight: 1.5
      }
    }, lang === 'mk' ? 'Нема самопослужување — администратор ќе издаде нова привремена лозинка на вашата сметка.' : 'Accounts are provisioned — no self-service reset. An administrator will issue a new one-time password to your account.')), /*#__PURE__*/React.createElement(Field, {
      label: lang === 'mk' ? 'Корисничко име' : 'Username'
    }, /*#__PURE__*/React.createElement(Input, {
      value: resetUser,
      onChange: e => setResetUser(e.target.value),
      placeholder: "qcm.blani",
      autoFocus: true
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      type: "button",
      full: true,
      onClick: () => setMode('signin')
    }, lang === 'mk' ? 'Назад' : 'Back'), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      full: true,
      disabled: busy
    }, busy ? lang === 'mk' ? 'Испраќање…' : 'Sending…' : lang === 'mk' ? 'Испрати барање' : 'Send request'))), mode === 'sent' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        gap: 12,
        padding: '6px 0 2px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 46,
        height: 46,
        borderRadius: 999,
        background: 'var(--green-100)',
        color: 'var(--green-700)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I('Check', 22)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 800,
        fontSize: 'var(--fs-15)'
      }
    }, lang === 'mk' ? 'Барањето е испратено' : 'Request sent'), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: 0,
        fontSize: 'var(--fs-12)',
        color: 'var(--text-body)',
        lineHeight: 1.5
      }
    }, lang === 'mk' ? `Администратор ќе издаде нова привремена лозинка за „${resetUser}“ и ќе ве извести лично.` : `An administrator will issue a new one-time password for "${resetUser}" and notify you directly.`), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      full: true,
      onClick: () => setMode('signin')
    }, lang === 'mk' ? 'Назад кон најава' : 'Back to sign in'))))));
  }

  // ─────────────────────────────── Sidebar ───────────────────────────────
  function Sidebar({
    view,
    setView,
    lang,
    me,
    tasks,
    deptFilter,
    setDeptFilter
  }) {
    const t = GF_T[lang];
    const L = lang === 'mk';
    const nav = [{
      id: 'myweek',
      icon: 'LayoutGrid',
      label: t.myweek
    }, {
      id: 'planning',
      icon: 'CalendarRange',
      label: L ? 'Планирање' : 'Planning'
    }, {
      id: 'board',
      icon: 'Columns3',
      label: t.board
    }, {
      id: 'timeline',
      icon: 'CalendarRange',
      label: t.timeline
    }, {
      id: 'coord',
      icon: 'GitBranch',
      label: t.coord
    }, {
      id: 'dash',
      icon: 'ChartColumn',
      label: t.dash
    }, {
      id: 'team',
      icon: 'Users',
      label: t.team
    }, {
      id: 'report',
      icon: 'Sparkles',
      label: 'AI Report'
    }, {
      id: 'qclab',
      icon: 'FlaskConical',
      label: L ? 'QC лаб' : 'QC Lab'
    }, {
      id: 'analytics',
      icon: 'ChartPie',
      label: L ? 'Аналитика' : 'Analytics'
    }, {
      id: 'audit',
      icon: 'ScrollText',
      label: L ? 'Дневник' : 'Audit'
    }, {
      id: 'import',
      icon: 'Upload',
      label: L ? 'Увоз' : 'Import'
    }, {
      id: 'access',
      icon: 'ShieldCheck',
      label: L ? 'Пристап' : 'Access'
    }, {
      id: 'governance',
      icon: 'GitPullRequestArrow',
      label: L ? 'Управување' : 'Governance'
    }, {
      id: 'settings',
      icon: 'Settings',
      label: t.settings
    }];
    return /*#__PURE__*/React.createElement("aside", {
      style: {
        width: 250,
        flexShrink: 0,
        background: 'var(--surface)',
        borderRight: '1px solid var(--line)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '18px 18px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(Warbird, {
      size: 26,
      variant: "line"
    }), /*#__PURE__*/React.createElement(GrowFlowLockup, {
      size: "md",
      leaf: false
    })), /*#__PURE__*/React.createElement("nav", {
      style: {
        padding: '2px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2
      }
    }, nav.map(n => /*#__PURE__*/React.createElement(NavItem, {
      key: n.id,
      icon: I(n.icon),
      label: n.label,
      active: view === n.id,
      onClick: () => setView(n.id)
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 1,
        background: 'var(--line-2)',
        margin: '14px 18px'
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '0 16px',
        marginBottom: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "eyebrow"
    }, t.depts)), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '0 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        overflowY: 'auto',
        flex: 1
      }
    }, GF_DEPARTMENTS.map(d => /*#__PURE__*/React.createElement(DeptRow, {
      key: d.id,
      color: d.color,
      name: lang === 'mk' ? d.mk : d.name,
      count: (tasks || []).filter(x => x.dept === d.id).length,
      active: deptFilter === d.id,
      onClick: () => {
        setDeptFilter(deptFilter === d.id ? null : d.id);
        if (view !== 'myweek' && view !== 'board') setView('myweek');
      }
    }))), /*#__PURE__*/React.createElement("div", {
      onClick: () => setView('settings'),
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: 12,
        margin: 12,
        borderRadius: 'var(--r-md)',
        background: 'var(--surface-2)',
        cursor: 'pointer'
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: me.name,
      size: 34,
      color: me.color
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 700,
        fontSize: 'var(--fs-13)'
      }
    }, me.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        color: 'var(--text-body)',
        fontWeight: 600
      }
    }, GF_ROLES[me.role] ? GF_ROLES[me.role][lang] : me.roleLabel))));
  }

  // ─────────────────────────────── Header ───────────────────────────────
  function Header({
    lang,
    setLang,
    theme,
    setTheme,
    onNew,
    onVoice,
    onOpenReport,
    onWorklog,
    onAssistant,
    me,
    query,
    setQuery,
    weekIdx,
    setWeekIdx
  }) {
    const t = GF_T[lang];
    return /*#__PURE__*/React.createElement("header", {
      style: {
        height: 64,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '0 22px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--line)',
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flex: 1,
        maxWidth: 380,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '0 13px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-muted)',
        display: 'inline-flex'
      }
    }, I('Search', 16)), /*#__PURE__*/React.createElement("input", {
      id: "gf-search",
      value: query,
      onChange: e => setQuery(e.target.value),
      placeholder: t.search,
      style: {
        border: 'none',
        background: 'none',
        outline: 'none',
        padding: '10px 0',
        fontSize: 'var(--fs-13)',
        fontWeight: 500,
        width: '100%',
        fontFamily: 'inherit',
        color: 'var(--text-strong)'
      }
    }), query && /*#__PURE__*/React.createElement("span", {
      onClick: () => setQuery(''),
      style: {
        cursor: 'pointer',
        color: 'var(--text-muted)',
        display: 'inline-flex'
      }
    }, I('X', 14))), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '3px 4px'
      },
      title: ['Jun 26 – Jul 2', 'Jul 3 – Jul 9', 'Jul 10 – Jul 16'][weekIdx]
    }, /*#__PURE__*/React.createElement(IconButton, {
      size: "sm",
      variant: "ghost",
      disabled: weekIdx === 0,
      onClick: () => weekIdx > 0 && setWeekIdx(weekIdx - 1)
    }, I('ChevronLeft', 16)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        minWidth: 92,
        textAlign: 'center',
        color: 'var(--text-strong)'
      }
    }, WEEK_LABELS[lang][weekIdx]), /*#__PURE__*/React.createElement(IconButton, {
      size: "sm",
      variant: "ghost",
      disabled: weekIdx === 2,
      onClick: () => weekIdx < 2 && setWeekIdx(weekIdx + 1)
    }, I('ChevronRight', 16))), /*#__PURE__*/React.createElement(Segmented, {
      options: [{
        value: 'en',
        label: 'EN'
      }, {
        value: 'mk',
        label: 'МК'
      }],
      value: lang,
      onChange: setLang
    }), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "sm",
      icon: I('Plus', 16),
      onClick: onNew
    }, t.newtask), /*#__PURE__*/React.createElement(Button, {
      variant: "orange",
      size: "sm",
      icon: I('Mic', 16),
      onClick: onVoice
    }, t.voice), /*#__PURE__*/React.createElement(IconButton, {
      onClick: () => setTheme(theme === 'dark' ? 'light' : 'dark')
    }, I(theme === 'dark' ? 'Sun' : 'Moon', 18)), /*#__PURE__*/React.createElement(IconButton, {
      onClick: onWorklog,
      title: lang === 'mk' ? 'Работни сесии' : 'Work sessions'
    }, I('Clock', 18)), /*#__PURE__*/React.createElement(IconButton, {
      active: true,
      badge: "3",
      onClick: onAssistant
    }, I('Sparkles', 18)));
  }

  // ─────────────────────────────── Week strip ───────────────────────────────
  function WeekStrip({
    lang,
    day,
    setDay,
    weekIdx,
    setWeekIdx,
    tasks
  }) {
    const t = GF_T[lang];
    const counts = {
      Mon: 0,
      Tue: 0,
      Wed: 0,
      Thu: 0,
      Fri: 0
    };
    (tasks || []).forEach(x => (x.days || [x.day]).forEach(d => {
      if (counts[d] != null) counts[d] += 1;
    }));
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '18px 24px 6px',
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        letterSpacing: '-.01em'
      }
    }, WEEK_LABELS[lang][weekIdx]), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        color: 'var(--text-body)',
        fontWeight: 600
      }
    }, ['Jun 26 – Jul 2', 'Jul 3 – Jul 9', 'Jul 10 – Jul 16'][weekIdx]), weekIdx === 1 && /*#__PURE__*/React.createElement(Badge, {
      tone: "green"
    }, t.thisweek), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(IconButton, {
      size: "sm",
      variant: "ghost",
      disabled: weekIdx === 0,
      onClick: () => weekIdx > 0 && setWeekIdx(weekIdx - 1)
    }, I('ChevronLeft', 18)), /*#__PURE__*/React.createElement(IconButton, {
      size: "sm",
      variant: "ghost",
      disabled: weekIdx === 2,
      onClick: () => weekIdx < 2 && setWeekIdx(weekIdx + 1)
    }, I('ChevronRight', 18))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        flexWrap: 'wrap',
        padding: '8px 24px 4px'
      }
    }, DAYS.map(d => /*#__PURE__*/React.createElement(DayPill, {
      key: d,
      day: lang === 'mk' ? {
        Mon: 'Пон',
        Tue: 'Вто',
        Wed: 'Сре',
        Thu: 'Чет',
        Fri: 'Пет'
      }[d] : d,
      count: counts[d],
      active: d === day,
      onClick: () => setDay(d === day ? null : d)
    }))));
  }

  // ─────────────────────────────── My Week ───────────────────────────────
  function MyWeek({
    lang,
    day,
    setDay,
    weekIdx,
    setWeekIdx,
    tasks,
    query,
    onCycle,
    onCheck,
    onNew,
    onEdit,
    onDelete,
    onOpen,
    canEdit,
    canDelete
  }) {
    const t = GF_T[lang];
    const [openId, setOpenId] = React.useState('T-4KZ9');
    const q = query.trim().toLowerCase();
    let shown = day ? tasks.filter(x => x.day === day) : tasks;
    if (q) shown = shown.filter(x => x.title.toLowerCase().includes(q) || (x.refCode || '').toLowerCase().includes(q) || (x.type || '').toLowerCase().includes(q));
    const done = shown.filter(x => x.status === 'done').length;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%'
      }
    }, /*#__PURE__*/React.createElement(WeekStrip, {
      lang: lang,
      day: day,
      setDay: setDay,
      weekIdx: weekIdx,
      setWeekIdx: setWeekIdx,
      tasks: tasks
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        margin: '12px 24px 4px',
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        display: 'flex',
        alignItems: 'center',
        gap: 26,
        padding: '13px 18px',
        flexWrap: 'wrap'
      }
    }, [[tasks.length + '', t.total], [done + '', STATUS_LABEL(lang, 'done')], [tasks.filter(x => x.status === 'working').length + '', t.working], [tasks.filter(x => x.status === 'stuck').length + '', t.stuck], ['Wed', t.busiest]].map(([v, l], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-19)',
        fontWeight: 800,
        letterSpacing: '-.02em'
      }
    }, v), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-body)'
      }
    }, l)))), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '10px 24px 40px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '6px 2px 6px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-17)',
        fontWeight: 800
      }
    }, day ? day : lang === 'mk' ? 'Оваа недела' : 'This week'), /*#__PURE__*/React.createElement(Badge, {
      tone: "neutral"
    }, shown.length)), shown.length === 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '30px',
        textAlign: 'center',
        color: 'var(--text-muted)',
        fontWeight: 600,
        border: '1px dashed var(--line)',
        borderRadius: 'var(--r-lg)'
      }
    }, q ? `${t.noresults} "${query}"` : t.notasks), shown.map(task => /*#__PURE__*/React.createElement("div", {
      key: task.id,
      style: {
        position: 'relative'
      },
      className: "gf-mw-card"
    }, /*#__PURE__*/React.createElement(TaskCard, {
      task: {
        ...task,
        deps: task._depObjs || []
      },
      lang: lang,
      expanded: openId === task.id,
      onToggle: () => setOpenId(openId === task.id ? null : task.id),
      onStatusClick: () => onCycle(task.id),
      onCheck: () => onCheck(task.id),
      handoffTo: GF_HANDOFF[task.dept] ? DEPT_NAME(GF_HANDOFF[task.dept], lang) : null,
      onEdit: () => onEdit(task),
      onAdvance: () => onCycle(task.id),
      onDelete: () => onDelete(task.id),
      canEdit: canEdit(task),
      canDelete: canDelete
    }), /*#__PURE__*/React.createElement("button", {
      onClick: e => {
        e.stopPropagation();
        onOpen && onOpen(task);
      },
      title: lang === 'mk' ? 'Отвори детали' : 'Open details',
      style: {
        position: 'absolute',
        top: 12,
        right: 12,
        width: 28,
        height: 28,
        borderRadius: 'var(--r-sm)',
        border: '1px solid var(--line)',
        background: 'var(--surface)',
        color: 'var(--text-muted)',
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 0,
        transition: 'opacity var(--dur-1) var(--ease-out)'
      },
      onMouseEnter: e => {
        e.currentTarget.style.color = 'var(--primary)';
        e.currentTarget.style.borderColor = 'var(--primary)';
      },
      onMouseLeave: e => {
        e.currentTarget.style.color = 'var(--text-muted)';
        e.currentTarget.style.borderColor = 'var(--line)';
      }
    }, I('Maximize2', 14)))), /*#__PURE__*/React.createElement("div", {
      onClick: onNew,
      style: {
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        background: 'var(--surface)',
        border: '1px dashed var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '12px 15px',
        cursor: 'pointer',
        color: 'var(--text-muted)',
        fontWeight: 600,
        fontSize: 'var(--fs-13)'
      }
    }, I('Plus', 16), " ", t.addtask)));
  }

  // ─────────────────────────────── Board ───────────────────────────────
  function Board({
    lang,
    tasks,
    query,
    onDrop,
    onOpen
  }) {
    const [overCol, setOverCol] = React.useState(null);
    const q = query.trim().toLowerCase();
    const filtered = q ? tasks.filter(x => x.title.toLowerCase().includes(q)) : tasks;
    const cols = [{
      id: 'pending',
      label: STATUS_LABEL(lang, 'pending'),
      dot: 'var(--st-pending)'
    }, {
      id: 'working',
      label: STATUS_LABEL(lang, 'working'),
      dot: 'var(--st-working)'
    }, {
      id: 'review',
      label: STATUS_LABEL(lang, 'review'),
      dot: 'var(--st-review)'
    }, {
      id: 'stuck',
      label: STATUS_LABEL(lang, 'stuck'),
      dot: 'var(--st-stuck)'
    }, {
      id: 'done',
      label: STATUS_LABEL(lang, 'done'),
      dot: 'var(--st-done)'
    }];
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflow: 'auto',
        height: '100%',
        padding: 24
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(5, minmax(200px, 1fr))',
        gap: 14,
        minWidth: 'min-content'
      }
    }, cols.map(c => {
      const items = filtered.filter(x => x.status === c.id);
      return /*#__PURE__*/React.createElement("div", {
        key: c.id,
        onDragOver: e => {
          e.preventDefault();
          setOverCol(c.id);
        },
        onDragLeave: () => setOverCol(v => v === c.id ? null : v),
        onDrop: e => {
          e.preventDefault();
          const id = e.dataTransfer.getData('text/task');
          setOverCol(null);
          if (id) onDrop(id, c.id);
        },
        style: {
          background: overCol === c.id ? 'var(--primary-soft)' : 'var(--surface-2)',
          border: '1px solid ' + (overCol === c.id ? 'var(--primary)' : 'var(--line)'),
          borderRadius: 'var(--r-lg)',
          padding: 12,
          minHeight: 200,
          transition: 'background var(--dur-ui), border-color var(--dur-ui)'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 12,
          padding: '0 2px'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 9,
          height: 9,
          borderRadius: 999,
          background: c.dot
        }
      }), /*#__PURE__*/React.createElement("span", {
        style: {
          fontWeight: 700,
          fontSize: 'var(--fs-13)'
        }
      }, c.label), /*#__PURE__*/React.createElement(Badge, {
        tone: "neutral"
      }, items.length)), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 8
        }
      }, items.length === 0 && /*#__PURE__*/React.createElement("div", {
        style: {
          padding: 14,
          textAlign: 'center',
          color: 'var(--text-faint)',
          fontSize: 'var(--fs-12)'
        }
      }, "\u2014"), items.map(x => /*#__PURE__*/React.createElement("div", {
        key: x.id,
        draggable: true,
        onClick: () => onOpen(x),
        onDragStart: e => {
          e.dataTransfer.setData('text/task', x.id);
          e.currentTarget.style.opacity = '.4';
        },
        onDragEnd: e => {
          e.currentTarget.style.opacity = '1';
        },
        style: {
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          borderLeft: '3px solid ' + x.color,
          borderRadius: 'var(--r-md)',
          padding: 11,
          boxShadow: 'var(--sh-1)',
          cursor: 'grab',
          transition: 'opacity var(--dur-ui), box-shadow var(--dur-ui)'
        },
        onMouseEnter: e => e.currentTarget.style.boxShadow = 'var(--sh-2)',
        onMouseLeave: e => e.currentTarget.style.boxShadow = 'var(--sh-1)'
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 800,
          letterSpacing: '.04em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: 5
        }
      }, DEPT_NAME(x.dept, lang)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 700,
          marginBottom: 9,
          lineHeight: 1.3
        }
      }, x.title), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }
      }, /*#__PURE__*/React.createElement(AvatarStack, {
        people: x.people,
        size: 24
      }), /*#__PURE__*/React.createElement(PriorityTag, {
        priority: x.priority
      }))))));
    })));
  }

  // ─────────────────────────────── Dashboard ───────────────────────────────
  function Dashboard({
    lang,
    tasks
  }) {
    const t = GF_T[lang];
    const byStatus = ['done', 'working', 'review', 'stuck', 'pending'];
    const countBy = s => tasks.filter(x => x.status === s).length;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 12,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement(KpiTile, {
      value: Math.round(countBy('done') / tasks.length * 100) + '%',
      label: t.completion,
      tone: "green",
      icon: I('TrendingUp', 18)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: tasks.length,
      label: t.total,
      icon: I('ListChecks', 18)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: countBy('working'),
      label: t.working,
      tone: "orange",
      icon: I('Loader', 18)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: countBy('stuck'),
      label: t.stuck,
      tone: "red",
      icon: I('OctagonAlert', 18)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: "Wed",
      label: t.busiest,
      tone: "violet",
      icon: I('CalendarClock', 18)
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 16
      }
    }, /*#__PURE__*/React.createElement(Panel, {
      title: lang === 'mk' ? 'По статус' : 'Completion by status'
    }, byStatus.map(s => /*#__PURE__*/React.createElement(BarRow, {
      key: s,
      label: STATUS_LABEL(lang, s),
      value: countBy(s),
      max: tasks.length,
      color: STATUS_COLOR(s)
    }))), /*#__PURE__*/React.createElement(Panel, {
      title: lang === 'mk' ? 'По оддел' : 'By department'
    }, GF_DEPARTMENTS.map(d => ({
      d,
      n: tasks.filter(x => x.dept === d.id).length
    })).filter(o => o.n > 0).sort((a, b) => b.n - a.n).slice(0, 6).map(({
      d,
      n
    }) => /*#__PURE__*/React.createElement(BarRow, {
      key: d.id,
      label: lang === 'mk' ? d.mk : d.name,
      value: n,
      max: Math.max(...GF_DEPARTMENTS.map(z => tasks.filter(x => x.dept === z.id).length), 1),
      dot: d.color,
      color: d.color
    }))), /*#__PURE__*/React.createElement(Panel, {
      title: lang === 'mk' ? 'Оптоварување' : 'Workload'
    }, [...GF_PEOPLE].sort((a, b) => b.active - a.active).slice(0, 4).map(p => /*#__PURE__*/React.createElement("div", {
      key: p.id,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: p.name,
      size: 30
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 700
      }
    }, p.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        color: 'var(--text-muted)',
        fontWeight: 600
      }
    }, GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.roleLabel)), /*#__PURE__*/React.createElement(Badge, {
      tone: "neutral"
    }, p.active)))), /*#__PURE__*/React.createElement(Panel, {
      title: lang === 'mk' ? 'Блокери' : 'Blockers'
    }, tasks.filter(x => x.status === 'stuck').length === 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--text-muted)',
        fontSize: 'var(--fs-13)',
        fontWeight: 600
      }
    }, lang === 'mk' ? 'Нема блокери 🎉' : 'None 🎉'), tasks.filter(x => x.status === 'stuck').map(x => /*#__PURE__*/React.createElement("div", {
      key: x.id,
      style: {
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start',
        background: 'var(--red-soft)',
        borderRadius: 'var(--r-md)',
        padding: 12
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--red)',
        display: 'inline-flex',
        marginTop: 1
      }
    }, I('OctagonAlert', 16)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: 'var(--red-700)'
      }
    }, x.title), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--red-700)',
        opacity: .85,
        marginTop: 2
      }
    }, x.blocker)))))));
  }
  function Panel({
    title,
    children
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
        boxShadow: 'var(--sh-1)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-14)',
        fontWeight: 800,
        marginBottom: 14
      }
    }, title), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }
    }, children));
  }
  function STATUS_LABEL(lang, s) {
    return DS.STATUS[s][lang === 'mk' ? 'labelMk' : 'label'];
  }
  function STATUS_COLOR(s) {
    return DS.STATUS[s].dot;
  }
  window.STATUS_LABEL = STATUS_LABEL;
  window.STATUS_COLOR = STATUS_COLOR;
  function DEPT_NAME(id, lang) {
    const d = GF_DEPARTMENTS.find(x => x.id === id);
    return d ? lang === 'mk' ? d.mk : d.name : id;
  }

  // ─────────────────────────────── Voice modal ───────────────────────────────
  function VoiceModal({
    onClose,
    onConfirm,
    lang
  }) {
    const L = lang === 'mk';
    const [stage, setStage] = React.useState('recording'); // recording | parsing | parsed
    const [live, setLive] = React.useState(true);
    const [transcript, setTranscript] = React.useState('');
    const bars = Array.from({
      length: 22
    }, (_, i) => 8 + Math.abs(Math.sin(i * 0.9)) * 40);
    const fullText = L ? 'Валидирај го HPLC методот за јачина за серија F27, висок приоритет, рок четврток.' : 'Validate the HPLC potency method for batch F27, high priority, due Thursday.';

    // stream transcript while recording
    React.useEffect(() => {
      if (stage !== 'recording' || !live) return;
      const words = fullText.split(' ');
      let i = 0;
      const id = setInterval(() => {
        i += 1;
        setTranscript(words.slice(0, i).join(' '));
        if (i >= words.length) clearInterval(id);
      }, 130);
      return () => clearInterval(id);
    }, [stage, live]);
    function parse() {
      setStage('parsing');
      setTimeout(() => setStage('parsed'), 1400);
    }
    const fields = [{
      l: L ? 'Наслов' : 'Title',
      v: L ? 'Валидирај HPLC метод' : 'Validate HPLC method',
      c: 96
    }, {
      l: L ? 'Оддел' : 'Department',
      v: L ? 'Контрола на квалитет' : 'Quality Control',
      c: 92
    }, {
      l: L ? 'Приоритет' : 'Priority',
      v: L ? 'Критичен' : 'Critical',
      c: 88
    }, {
      l: L ? 'Рок' : 'Due',
      v: L ? 'Четврток' : 'Thursday',
      c: 79
    }, {
      l: L ? 'Реф.' : 'Ref',
      v: 'PP-QC-012',
      c: 71
    }];
    const cColor = c => c >= 90 ? 'var(--green-600)' : c >= 78 ? 'var(--amber)' : 'var(--orange)';
    const footer = stage === 'parsed' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => {
        setStage('recording');
        setTranscript('');
        setLive(true);
      }
    }, I('RotateCcw', 15), L ? 'Повтори' : 'Redo'), /*#__PURE__*/React.createElement(Button, {
      onClick: onConfirm
    }, I('Check', 15), L ? 'Создади задача' : 'Create task')) : stage === 'recording' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => setLive(!live)
    }, live ? L ? 'Паузирај' : 'Pause' : L ? 'Продолжи' : 'Resume'), /*#__PURE__*/React.createElement(Button, {
      onClick: parse,
      disabled: !transcript
    }, I('Sparkles', 15), L ? 'Парсирај со AI' : 'Parse with AI')) : null;
    return /*#__PURE__*/React.createElement(Modal, {
      dark: true,
      title: L ? 'Кажете ја задачата' : 'Speak your task',
      onClose: onClose,
      width: 460,
      footer: footer
    }, stage === 'recording' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 20,
        padding: '10px 0 4px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'relative',
        width: 118,
        height: 118,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        position: 'absolute',
        inset: 0,
        borderRadius: 999,
        background: 'rgba(255,122,26,.14)'
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        position: 'absolute',
        inset: 15,
        borderRadius: 999,
        background: 'rgba(255,122,26,.22)'
      }
    }), /*#__PURE__*/React.createElement("button", {
      onClick: () => setLive(!live),
      style: {
        width: 78,
        height: 78,
        borderRadius: 999,
        background: 'var(--orange)',
        border: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        cursor: 'pointer',
        boxShadow: '0 10px 30px rgba(255,122,26,.5)' + (live ? ', 0 0 0 14px rgba(255,122,26,.12)' : '')
      }
    }, I(live ? 'Mic' : 'Play', 30))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        height: 46
      }
    }, bars.map((h, i) => /*#__PURE__*/React.createElement("span", {
      key: i,
      style: {
        width: 4,
        borderRadius: 4,
        background: 'var(--orange)',
        height: live ? h : 8,
        transition: 'height .2s'
      }
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        minHeight: 44,
        fontSize: 'var(--fs-15)',
        fontWeight: 600,
        lineHeight: 1.5,
        textAlign: 'center',
        color: transcript ? 'var(--text-strong)' : 'var(--text-muted)',
        maxWidth: 380
      }
    }, transcript ? `“${transcript}${live ? '…' : ''}”` : L ? 'Слушам…' : 'Listening…')), stage === 'parsing' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 16,
        padding: '40px 0'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--primary)',
        display: 'inline-flex',
        animation: 'gfSpin 1s linear infinite'
      }
    }, I('LoaderCircle', 40)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-14)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, L ? 'AI ги извлекува полињата…' : 'AI is extracting fields…'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-muted)'
      }
    }, L ? 'Наслов · Оддел · Приоритет · Рок' : 'Title · Department · Priority · Due')), stage === 'parsed' && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '4px 0'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 14,
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-muted)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--primary)',
        display: 'inline-flex'
      }
    }, I('Sparkles', 15)), L ? 'Извлечено од: ' : 'Parsed from: ', /*#__PURE__*/React.createElement("span", {
      style: {
        fontStyle: 'italic'
      }
    }, "\u201C", fullText, "\u201D")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8
      }
    }, fields.map(f => /*#__PURE__*/React.createElement("div", {
      key: f.l,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '10px 13px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 84,
        flexShrink: 0,
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.03em'
      }
    }, f.l), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, f.v), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 40,
        height: 4,
        borderRadius: 999,
        background: 'var(--line)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'block',
        height: '100%',
        width: `${f.c}%`,
        background: cColor(f.c)
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: cColor(f.c),
        width: 28
      }
    }, f.c, "%")))))));
  }

  // ─────────────────────────────── Add / Edit task ───────────────────────────────
  function AddTaskModal({
    onClose,
    onCreate,
    lang,
    editTask
  }) {
    const L = lang === 'mk';
    const isEdit = !!editTask;
    const [title, setTitle] = React.useState(editTask ? editTask.title : '');
    const [desc, setDesc] = React.useState(editTask ? editTask.desc || '' : '');
    const [pri, setPri] = React.useState(editTask ? editTask.priority : 'high');
    const [dept, setDept] = React.useState(editTask ? editTask.dept : GF_DEPARTMENTS[0].id);
    const [type, setType] = React.useState(editTask ? editTask.type || 'validation' : 'validation');
    const [owner, setOwner] = React.useState(editTask ? editTask.owner : GF_PEOPLE[0].id);
    const [helpers, setHelpers] = React.useState(editTask ? editTask.helpers || [] : []);
    const [days, setDays] = React.useState(editTask ? editTask.days || [] : ['Mon']);
    const [est, setEst] = React.useState(editTask ? editTask.sessionHours != null ? String(editTask.sessionHours) : '' : '');
    const [rec, setRec] = React.useState(editTask ? editTask.recurrence || '' : '');
    const [due, setDue] = React.useState(editTask ? editTask.due || '' : '');
    const [ref, setRef] = React.useState(editTask ? editTask.ref || '' : '');
    const [tags, setTags] = React.useState(editTask ? (editTask.tags || []).join(', ') : '');
    const [err, setErr] = React.useState(false);
    const priLabel = {
      critical: L ? 'Критично' : 'Critical',
      high: L ? 'Високо' : 'High',
      medium: L ? 'Средно' : 'Medium',
      low: L ? 'Ниско' : 'Low'
    };
    const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    const dayLabel = {
      Mon: L ? 'Пон' : 'Mon',
      Tue: L ? 'Вто' : 'Tue',
      Wed: L ? 'Сре' : 'Wed',
      Thu: L ? 'Чет' : 'Thu',
      Fri: L ? 'Пет' : 'Fri'
    };
    const recLabel = {
      '': L ? 'Без' : 'None',
      daily: L ? 'Дневно' : 'Daily',
      weekly: L ? 'Неделно' : 'Weekly',
      monthly: L ? 'Месечно' : 'Monthly'
    };
    const toggleHelper = id => setHelpers(hs => hs.includes(id) ? hs.filter(x => x !== id) : [...hs, id]);
    const toggleDay = d => setDays(ds => ds.includes(d) ? ds.filter(x => x !== d) : [...ds, d]);
    function submit() {
      if (!title.trim()) {
        setErr(true);
        return;
      }
      onCreate({
        id: editTask && editTask.id,
        title: title.trim(),
        desc: desc.trim(),
        priority: pri,
        dept,
        type,
        owner,
        helpers: helpers.filter(h => h !== owner),
        days: days.length ? days : ['Mon'],
        sessionHours: est.trim() ? parseFloat(est) : null,
        recurrence: rec || null,
        due: due || null,
        ref: ref.trim() || null,
        tags: tags.split(',').map(s => s.trim()).filter(Boolean)
      });
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: isEdit ? L ? 'Уреди задача' : 'Edit task' : L ? 'Нова задача' : 'Add a task',
      onClose: onClose,
      width: 520,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        onClick: onClose
      }, L ? 'Откажи' : 'Cancel'), /*#__PURE__*/React.createElement(Button, {
        onClick: submit
      }, isEdit ? L ? 'Зачувај' : 'Save changes' : L ? 'Креирај' : 'Create task'))
    }, /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Наслов' : 'Task title',
      required: true,
      hint: err ? L ? 'Задолжително поле' : 'This field is required' : null
    }, /*#__PURE__*/React.createElement(Input, {
      placeholder: L ? 'Валидирај HPLC метод…' : 'Validate HPLC method…',
      autoFocus: true,
      value: title,
      onChange: e => {
        setTitle(e.target.value);
        if (err) setErr(false);
      },
      style: err ? {
        borderColor: 'var(--red)'
      } : {}
    })), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Опис' : 'Description'
    }, /*#__PURE__*/React.createElement(Textarea, {
      placeholder: L ? 'Додади детали…' : 'Add detail…',
      value: desc,
      onChange: e => setDesc(e.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Оддел' : 'Department'
    }, /*#__PURE__*/React.createElement(PopSelect, {
      value: dept,
      onChange: setDept,
      title: L ? 'Оддел' : 'Department',
      options: GF_DEPARTMENTS.map(d => ({
        value: d.id,
        label: L ? d.mk : d.name,
        color: d.color
      }))
    })), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Носител' : 'Owner'
    }, /*#__PURE__*/React.createElement(PopSelect, {
      value: owner,
      onChange: setOwner,
      title: L ? 'Носител' : 'Owner',
      options: GF_PEOPLE.map(p => ({
        value: p.id,
        label: p.name,
        color: p.color
      }))
    }))), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Соработници (Одговорни)' : 'Helpers (Responsible)'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 7,
        flexWrap: 'wrap'
      }
    }, GF_PEOPLE.filter(p => p.id !== owner).map(p => /*#__PURE__*/React.createElement(Chip, {
      key: p.id,
      selected: helpers.includes(p.id),
      onClick: () => toggleHelper(p.id)
    }, p.name.split(' ')[0])))), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Тип' : 'Type'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 7,
        flexWrap: 'wrap'
      }
    }, Object.entries(GF_TASK_TYPES).map(([k, v]) => /*#__PURE__*/React.createElement(Chip, {
      key: k,
      selected: type === k,
      onClick: () => setType(k)
    }, v[lang])))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Рок' : 'Due date'
    }, /*#__PURE__*/React.createElement(Input, {
      type: "date",
      value: due,
      onChange: e => setDue(e.target.value)
    })), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Реф. код' : 'Ref code'
    }, /*#__PURE__*/React.createElement(Input, {
      placeholder: "PP-QC-012",
      value: ref,
      onChange: e => setRef(e.target.value)
    }))), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Закажи за денови' : 'Schedule for days'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 7,
        flexWrap: 'wrap'
      }
    }, WEEKDAYS.map(d => /*#__PURE__*/React.createElement(Chip, {
      key: d,
      selected: days.includes(d),
      onClick: () => toggleDay(d)
    }, dayLabel[d])))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Проценети часови' : 'Estimated hours'
    }, /*#__PURE__*/React.createElement(Input, {
      type: "number",
      min: "0",
      step: "0.5",
      placeholder: "0",
      value: est,
      onChange: e => setEst(e.target.value)
    })), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Повторување' : 'Recurrence'
    }, /*#__PURE__*/React.createElement(PopSelect, {
      value: rec,
      onChange: setRec,
      title: L ? 'Повторување' : 'Recurrence',
      options: ['', 'daily', 'weekly', 'monthly'].map(r => ({
        value: r,
        label: recLabel[r]
      }))
    }))), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Приоритет' : 'Priority'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 7,
        flexWrap: 'wrap'
      }
    }, ['critical', 'high', 'medium', 'low'].map(p => /*#__PURE__*/React.createElement(Chip, {
      key: p,
      selected: pri === p,
      onClick: () => setPri(p)
    }, priLabel[p])))), /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Ознаки (одвоени со запирка)' : 'Tags (comma-separated)'
    }, /*#__PURE__*/React.createElement(Input, {
      placeholder: "potency, batch-F27",
      value: tags,
      onChange: e => setTags(e.target.value)
    })));
  }

  // ─────────────────────────────── User profile / edit modal ───────────────────────────────
  const AVATAR_COLORS = ['#2F6BFF', '#15A86B', '#E0603A', '#7A5BE0', '#0891B2', '#D4A017', '#DB2777', '#0EA5A5', '#F97316', '#6366F1'];
  function UserModal({
    person,
    lang,
    onClose,
    canManage,
    isActive,
    onSetActive,
    onSave,
    onRemove
  }) {
    const L = lang === 'mk';
    const isNew = !person;
    const [editing, setEditing] = React.useState(isNew);
    const [name, setName] = React.useState(person ? person.name : '');
    const [role, setRole] = React.useState(person ? person.role : 'operator');
    const [dept, setDept] = React.useState(person ? person.dept : GF_DEPARTMENTS[0].id);
    const [color, setColor] = React.useState(person ? person.color : AVATAR_COLORS[0]);
    const [err, setErr] = React.useState(false);
    if (editing) {
      const save = () => {
        if (!name.trim()) {
          setErr(true);
          return;
        }
        onSave({
          id: person && person.id,
          name: name.trim(),
          role,
          dept,
          color
        });
      };
      return /*#__PURE__*/React.createElement(Modal, {
        title: isNew ? L ? 'Нов член' : 'Add member' : L ? 'Уреди член' : 'Edit member',
        onClose: onClose,
        width: 460,
        footer: /*#__PURE__*/React.createElement(React.Fragment, null, !isNew && /*#__PURE__*/React.createElement(Button, {
          variant: "secondary",
          onClick: () => setEditing(false)
        }, L ? 'Откажи' : 'Cancel'), /*#__PURE__*/React.createElement(Button, {
          onClick: save
        }, isNew ? L ? 'Додади' : 'Add member' : L ? 'Зачувај' : 'Save'))
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          marginBottom: 16
        }
      }, /*#__PURE__*/React.createElement(Avatar, {
        name: name || '?',
        size: 54,
        color: color
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 600,
          color: 'var(--text-muted)'
        }
      }, L ? 'Преглед на аватар' : 'Avatar preview')), /*#__PURE__*/React.createElement(Field, {
        label: L ? 'Име' : 'Full name',
        required: true,
        hint: err ? L ? 'Задолжително' : 'Required' : null
      }, /*#__PURE__*/React.createElement(Input, {
        placeholder: L ? 'на пр. Ана Николова' : 'e.g. Ana Nikolova',
        autoFocus: true,
        value: name,
        onChange: e => {
          setName(e.target.value);
          if (err) setErr(false);
        },
        style: err ? {
          borderColor: 'var(--red)'
        } : {}
      })), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12
        }
      }, /*#__PURE__*/React.createElement(Field, {
        label: L ? 'Улога' : 'Role'
      }, /*#__PURE__*/React.createElement(PopSelect, {
        value: role,
        onChange: setRole,
        title: L ? 'Улога' : 'Role',
        options: Object.keys(GF_ROLES).map(r => ({
          value: r,
          label: GF_ROLES[r][lang]
        }))
      })), /*#__PURE__*/React.createElement(Field, {
        label: L ? 'Оддел' : 'Department'
      }, /*#__PURE__*/React.createElement(PopSelect, {
        value: dept,
        onChange: setDept,
        title: L ? 'Оддел' : 'Department',
        options: GF_DEPARTMENTS.map(d => ({
          value: d.id,
          label: L ? d.mk : d.name,
          color: d.color
        }))
      }))), /*#__PURE__*/React.createElement(Field, {
        label: L ? 'Боја на аватар' : 'Avatar color'
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap'
        }
      }, AVATAR_COLORS.map(c => /*#__PURE__*/React.createElement("span", {
        key: c,
        onClick: () => setColor(c),
        style: {
          width: 26,
          height: 26,
          borderRadius: 999,
          background: c,
          cursor: 'pointer',
          boxShadow: color === c ? '0 0 0 3px var(--surface), 0 0 0 5px ' + c : 'none'
        }
      })))));
    }
    const pdept = GF_DEPARTMENTS.find(d => d.id === person.dept) || {};
    const perms = GF_ROLE_PERMS(person.role);
    const permRows = [[L ? 'Создавање задачи' : 'Create tasks', perms.create], [L ? 'Уреди сите' : 'Edit any task', perms.editAny], [L ? 'Избриши сите' : 'Delete any task', perms.deleteAny], [L ? 'Статус: сите' : 'Change any status', perms.status === 'any'], [L ? 'Преглед на тим' : 'View team', perms.team]];
    return /*#__PURE__*/React.createElement(Modal, {
      title: L ? 'Профил' : 'Team member',
      onClose: onClose,
      width: 460
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        marginBottom: 18
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: person.name,
      size: 54,
      color: person.color
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-19)',
        fontWeight: 800
      }
    }, person.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: 'var(--text-body)'
      }
    }, GF_ROLES[person.role] ? GF_ROLES[person.role][lang] : person.role), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        marginTop: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 9,
        height: 9,
        borderRadius: 999,
        background: pdept.color
      }
    }), L ? pdept.mk : pdept.name))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 10,
        marginBottom: 18
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '12px 14px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-28)',
        fontWeight: 800,
        color: 'var(--primary)'
      }
    }, person.active), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, L ? 'Активни задачи' : 'Active tasks')), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '12px 14px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-28)',
        fontWeight: 800,
        color: 'var(--st-done)'
      }
    }, person.done), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, L ? 'Завршени' : 'Completed'))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        marginBottom: 8
      }
    }, L ? 'Дозволи' : 'Permissions'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 2
      }
    }, permRows.map(([label, on]) => /*#__PURE__*/React.createElement("div", {
      key: label,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '7px 0',
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: on ? 'var(--text-strong)' : 'var(--text-faint)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: on ? 'var(--st-done)' : 'var(--text-faint)'
      }
    }, I(on ? 'Check' : 'Minus', 16)), label))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 8,
        marginTop: 20,
        flexWrap: 'wrap'
      }
    }, isActive ? /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--st-done)',
        background: 'var(--st-done-soft)',
        borderRadius: 999,
        padding: '8px 13px'
      }
    }, I('Check', 15), L ? 'Активен корисник' : 'Active user') : /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => {
        onSetActive(person.id);
        onClose();
      }
    }, I('UserCheck', 15), "\xA0", L ? 'Постави како активен' : 'Set as active'), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), canManage && /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => setEditing(true)
    }, L ? 'Уреди' : 'Edit'), canManage && !isActive && /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => {
        onRemove(person.id);
        onClose();
      },
      style: {
        color: 'var(--red)'
      }
    }, L ? 'Отстрани' : 'Remove')));
  }

  // ─────────────────────────────── Worklog modal ───────────────────────────────
  function WorklogModal({
    lang,
    onClose
  }) {
    const L = lang === 'mk';
    const classes = {
      regular: {
        label: L ? 'Редовно' : 'Regular',
        bg: 'var(--st-done-soft)',
        fg: 'var(--st-done)'
      },
      overtime: {
        label: L ? 'Прекувремено' : 'Overtime',
        bg: 'var(--orange-soft)',
        fg: 'var(--orange-700)'
      },
      night: {
        label: L ? 'Ноќна' : 'Night',
        bg: 'var(--av-violet-soft, #ECE6FB)',
        fg: '#7A5BE0'
      },
      weekend: {
        label: L ? 'Викенд' : 'Weekend',
        bg: 'var(--st-stuck-soft)',
        fg: 'var(--st-stuck)'
      }
    };
    const sessions = [{
      day: 'Mon',
      who: 'blagoj',
      task: 'T-4KZ9',
      from: '08:00',
      to: '11:30',
      h: 3.5,
      cls: 'regular'
    }, {
      day: 'Mon',
      who: 'ivo',
      task: 'T-2M1P',
      from: '18:00',
      to: '20:00',
      h: 2,
      cls: 'overtime'
    }, {
      day: 'Tue',
      who: 'blagoj',
      task: 'T-4KZ9',
      from: '22:00',
      to: '01:00',
      h: 3,
      cls: 'night'
    }, {
      day: 'Wed',
      who: 'goran',
      task: 'T-9F3B',
      from: '09:00',
      to: '11:00',
      h: 2,
      cls: 'regular'
    }, {
      day: 'Sat',
      who: 'elena',
      task: 'T-7B2N',
      from: '10:00',
      to: '13:00',
      h: 3,
      cls: 'weekend'
    }];
    const total = sessions.reduce((s, x) => s + x.h, 0);
    return /*#__PURE__*/React.createElement(Modal, {
      title: L ? 'Работни сесии' : 'Work sessions',
      onClose: onClose,
      width: 560,
      footer: /*#__PURE__*/React.createElement("div", {
        style: {
          marginRight: 'auto',
          fontSize: 'var(--fs-13)',
          fontWeight: 700,
          color: 'var(--text-body)'
        }
      }, L ? 'Вкупно' : 'Total', ": ", /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-strong)'
        }
      }, total.toFixed(1), "h"))
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }
    }, sessions.map((s, i) => {
      const c = classes[s.cls];
      const p = GF_PERSON(s.who);
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '8px 10px',
          background: 'var(--surface-2)',
          border: '1px solid var(--line-2)',
          borderRadius: 'var(--r-sm)',
          fontSize: 'var(--fs-12)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: 'var(--text-muted)',
          width: 30
        }
      }, s.day), /*#__PURE__*/React.createElement(Avatar, {
        name: p.name,
        size: 24,
        color: p.color
      }), /*#__PURE__*/React.createElement("span", {
        style: {
          fontWeight: 700,
          flex: 1
        }
      }, p.name), /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-body)'
        }
      }, s.from, "\u2013", s.to), /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-mono)',
          fontWeight: 700
        }
      }, s.h, "h"), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 800,
          letterSpacing: '.04em',
          textTransform: 'uppercase',
          padding: '2px 8px',
          borderRadius: 999,
          background: c.bg,
          color: c.fg,
          whiteSpace: 'nowrap'
        }
      }, c.label));
    })));
  }

  // ─────────────────────────────── Task detail (from Board) ───────────────────────────────
  // Type-driven subtask step templates → meaningful checklist labels
  const SUBTASK_TEMPLATES = {
    validation: [['Equilibrate column & prep mobile phase', 'Еквилибрирај колона и подготви мобилна фаза'], ['Run system suitability', 'Изврши системска подобност'], ['Linearity across levels', 'Линеарност по нивоа'], ['Precision / repeatability', 'Прецизност / повторливост'], ['Compile validation report', 'Состави извештај за валидација']],
    lab: [['Draw samples per formula', 'Земи мостри по формула'], ['Run pass/fail gates', 'Изврши порти за помин/пад'], ['Record disposition', 'Запиши диспозиција'], ['Log to LIMS', 'Запиши во LIMS']],
    sop: [['Draft revision', 'Нацрт ревизија'], ['Internal review', 'Внатрешен преглед'], ['QA approval', 'Одобрување од КО'], ['Publish & train', 'Објави и обучи']],
    capa: [['Root-cause analysis', 'Анализа на основна причина'], ['Define action plan', 'Дефинирај акционен план'], ['Implement corrective action', 'Спроведи корективна акција'], ['Verify effectiveness', 'Потврди ефективност']],
    _default: [['Prepare', 'Подготви'], ['Execute', 'Изврши'], ['Verify', 'Потврди'], ['Sign off', 'Потпиши']]
  };
  function buildSubs(task) {
    const n = task.subCount || 0;
    const tpl = SUBTASK_TEMPLATES[task.type] || SUBTASK_TEMPLATES._default;
    return Array.from({
      length: n
    }, (_, i) => tpl[i % tpl.length]);
  }
  function DetailSection({
    icon,
    title,
    right,
    children
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 16
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        marginBottom: 9
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-muted)',
        display: 'inline-flex'
      }
    }, I(icon, 15)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 800,
        letterSpacing: '.05em',
        textTransform: 'uppercase',
        color: 'var(--text-muted)'
      }
    }, title), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), right), children);
  }
  function TaskDetailModal({
    task,
    lang,
    allTasks,
    canEdit,
    onClose,
    onCycle,
    onCheck
  }) {
    const L = lang === 'mk';
    const initialSubs = React.useMemo(() => buildSubs(task).map((s, i) => ({
      label: s[L ? 1 : 0],
      done: i < (task.subDone || 0)
    })), [task.id, L]);
    const [subs, setSubs] = React.useState(initialSubs);
    React.useEffect(() => {
      setSubs(buildSubs(task).map((s, i) => ({
        label: s[L ? 1 : 0],
        done: i < (task.subDone || 0)
      })));
    }, [task.id, L]);
    const [notes, setNotes] = React.useState(task.notes || []);
    const [draft, setDraft] = React.useState('');
    const [ack, setAck] = React.useState(task.ack || null); // 'accepted' | 'declined' | null
    if (!task) return null;
    const doneCount = subs.filter(s => s.done).length;
    const owner = GF_PERSON(task.owner);
    const helpers = (task.helpers || []).map(GF_PERSON);
    const deps = (task.deps || []).map(id => (allTasks || []).find(t => t.id === id)).filter(Boolean);
    const typeLabel = GF_TASK_TYPES[task.type] ? GF_TASK_TYPES[task.type][lang] : task.type;
    const chip = (label, val, tone) => /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '8px 11px',
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        marginBottom: 4
      }
    }, label), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: tone || 'var(--text-strong)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    }, val));
    function toggleSub(i) {
      if (!canEdit) return;
      setSubs(s => s.map((x, j) => j === i ? {
        ...x,
        done: !x.done
      } : x));
    }
    function addNote() {
      const n = draft.trim();
      if (!n) return;
      setNotes(ns => [...ns, {
        d: L ? 'Денес' : 'Today',
        n
      }]);
      setDraft('');
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: task.title,
      onClose: onClose,
      width: 560
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement(StatusPill, {
      status: task.status,
      lang: lang,
      onClick: canEdit ? () => onCycle(task.id) : undefined
    }), /*#__PURE__*/React.createElement(PriorityTag, {
      priority: task.priority
    }), task.overdue && /*#__PURE__*/React.createElement(Badge, {
      tone: "red"
    }, I('CalendarClock', 12), L ? 'Задоцнета' : 'Overdue'), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), ack === 'accepted' && /*#__PURE__*/React.createElement(Badge, {
      tone: "green"
    }, I('Check', 12), L ? 'Прифатена' : 'Accepted'), ack === 'declined' && /*#__PURE__*/React.createElement(Badge, {
      tone: "red"
    }, I('X', 12), L ? 'Одбиена' : 'Declined')), task.status === 'stuck' && task.blocker && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 14,
        display: 'flex',
        gap: 9,
        alignItems: 'flex-start',
        background: 'color-mix(in srgb, var(--red) 10%, var(--surface))',
        border: '1px solid color-mix(in srgb, var(--red) 35%, var(--line))',
        borderRadius: 'var(--r-md)',
        padding: '11px 13px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--red)',
        display: 'inline-flex',
        flexShrink: 0,
        marginTop: 1
      }
    }, I('OctagonAlert', 16)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 800,
        color: 'var(--red)',
        textTransform: 'uppercase',
        letterSpacing: '.04em'
      }
    }, L ? 'Блокатор' : 'Blocker'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: 'var(--text-strong)',
        marginTop: 2
      }
    }, task.blocker))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 8,
        marginTop: 14
      }
    }, chip(L ? 'Реф.' : 'Ref', task.ref || '—'), chip(L ? 'Тип' : 'Type', typeLabel), chip(L ? 'Оддел' : 'Dept', DEPT_NAME(task.dept, lang)), chip(L ? 'Рок' : 'Due', task.due || '—', task.overdue ? 'var(--red)' : null)), task.description && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 14,
        fontSize: 'var(--fs-13)',
        lineHeight: 1.55,
        color: 'var(--text-body)'
      }
    }, task.description), /*#__PURE__*/React.createElement(DetailSection, {
      icon: "Users",
      title: L ? 'Луѓе' : 'People'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 999,
        padding: '4px 12px 4px 4px'
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: owner.name,
      color: owner.color,
      size: 26
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700
      }
    }, owner.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        color: 'var(--primary)'
      }
    }, L ? 'Носител' : 'Owner'))), helpers.map(h => /*#__PURE__*/React.createElement("div", {
      key: h.name,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 999,
        padding: '4px 12px 4px 4px'
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: h.name,
      color: h.color,
      size: 26
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700
      }
    }, h.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, L ? 'Помош' : 'Helper')))))), subs.length > 0 && /*#__PURE__*/React.createElement(DetailSection, {
      icon: "ListChecks",
      title: L ? 'Чекори' : 'Steps',
      right: /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 800,
          color: 'var(--text-muted)'
        }
      }, doneCount, "/", subs.length)
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: 5,
        borderRadius: 999,
        background: 'var(--surface-2)',
        overflow: 'hidden',
        marginBottom: 10
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: '100%',
        width: `${doneCount / subs.length * 100}%`,
        background: 'var(--primary)',
        borderRadius: 999,
        transition: 'width var(--dur-2) var(--ease-out)'
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 2
      }
    }, subs.map((s, i) => /*#__PURE__*/React.createElement("button", {
      key: i,
      onClick: () => toggleSub(i),
      disabled: !canEdit,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '7px 9px',
        borderRadius: 'var(--r-sm)',
        border: 'none',
        background: 'transparent',
        cursor: canEdit ? 'pointer' : 'default',
        textAlign: 'left',
        width: '100%'
      },
      onMouseEnter: e => canEdit && (e.currentTarget.style.background = 'var(--surface-2)'),
      onMouseLeave: e => e.currentTarget.style.background = 'transparent'
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 19,
        height: 19,
        flexShrink: 0,
        borderRadius: 6,
        border: `2px solid ${s.done ? 'var(--primary)' : 'var(--line-strong, var(--line))'}`,
        background: s.done ? 'var(--primary)' : 'transparent',
        color: '#fff',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, s.done && I('Check', 12)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: s.done ? 'var(--text-muted)' : 'var(--text-strong)',
        textDecoration: s.done ? 'line-through' : 'none'
      }
    }, s.label))))), deps.length > 0 && /*#__PURE__*/React.createElement(DetailSection, {
      icon: "GitBranch",
      title: L ? 'Зависности' : 'Dependencies'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 7
      }
    }, deps.map(d => /*#__PURE__*/React.createElement("div", {
      key: d.id,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '9px 11px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        fontFamily: 'monospace'
      }
    }, d.id), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    }, d.title), /*#__PURE__*/React.createElement(StatusPill, {
      status: d.status,
      lang: lang
    }))))), /*#__PURE__*/React.createElement(DetailSection, {
      icon: "MessageSquareText",
      title: L ? 'Белешки за напредок' : 'Progress notes'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8
      }
    }, notes.length === 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)',
        fontWeight: 600
      }
    }, L ? 'Сè уште нема белешки.' : 'No notes yet.'), notes.map((n, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 44,
        flexShrink: 0,
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        paddingTop: 2,
        textTransform: 'uppercase'
      }
    }, n.d), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: 'var(--text-body)',
        borderLeft: '2px solid var(--line)',
        paddingLeft: 10
      }
    }, n.n))), canEdit && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 8,
        marginTop: 2
      }
    }, /*#__PURE__*/React.createElement(Input, {
      placeholder: L ? 'Додади белешка…' : 'Add a note…',
      value: draft,
      onChange: e => setDraft(e.target.value),
      onKeyDown: e => e.key === 'Enter' && addNote()
    }), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: addNote
    }, I('Plus', 15))))), !ack && canEdit && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 9,
        marginTop: 18,
        paddingTop: 16,
        borderTop: '1px solid var(--line)'
      }
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      onClick: () => setAck('accepted'),
      style: {
        flex: 1
      }
    }, I('Check', 15), L ? 'Прифати задача' : 'Accept task'), /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      onClick: () => setAck('declined'),
      style: {
        flex: 1
      }
    }, I('X', 15), L ? 'Одбиј' : 'Decline')));
  }

  // ─────────────────────────────── Assistant panel ───────────────────────────────
  function AssistantPanel({
    lang,
    tasks,
    onClose,
    onOpenTask
  }) {
    const L = lang === 'mk';
    const stuck = tasks.filter(x => x.status === 'stuck');
    const overdue = tasks.filter(x => x.overdue);
    const suggestions = L ? ['Што е блокирано оваа недела?', 'Резимирај ги задачите на QC', 'Кои задачи се задоцнети?'] : ['What is blocked this week?', 'Summarize QC tasks', 'Which tasks are overdue?'];
    const [msgs, setMsgs] = React.useState([{
      role: 'ai',
      text: L ? 'Здраво! Јас сум GrowFlow асистентот. Прашај ме за задачите, блокадите или планот за неделата.' : "Hi! I'm the GrowFlow assistant. Ask me about tasks, blockers, or this week's plan."
    }]);
    const [input, setInput] = React.useState('');
    const [typing, setTyping] = React.useState(false);
    const [mode, setMode] = React.useState('ask'); // ask | draft
    const [tone, setTone] = React.useState('formal');
    const [purpose, setPurpose] = React.useState('handoff');
    const [drafting, setDrafting] = React.useState(false);
    const [draftOut, setDraftOut] = React.useState('');
    const [copied, setCopied] = React.useState(false);
    const tones = [{
      id: 'formal',
      en: 'Formal',
      mk: 'Формален'
    }, {
      id: 'friendly',
      en: 'Friendly',
      mk: 'Пријателски'
    }, {
      id: 'direct',
      en: 'Direct',
      mk: 'Директен'
    }, {
      id: 'concise',
      en: 'Concise',
      mk: 'Концизен'
    }];
    const purposes = [{
      id: 'handoff',
      en: 'Dept handoff note',
      mk: 'Белешка за предавање'
    }, {
      id: 'escalate',
      en: 'Blocker escalation',
      mk: 'Ескалација на блокада'
    }, {
      id: 'update',
      en: 'Weekly status update',
      mk: 'Неделен статус'
    }, {
      id: 'reminder',
      en: 'Task reminder',
      mk: 'Потсетник за задача'
    }];
    function composeDraft() {
      const stuckOne = stuck[0];
      const map = {
        handoff: {
          formal: 'Please be advised that batch F27 has completed post-curing and is ready for QC intake. Kindly confirm receipt and schedule sampling at your earliest convenience.',
          friendly: "Hi team — F27 just wrapped post-curing and it's all yours for QC intake! Let me know when you can slot in the sampling. Thanks!",
          direct: 'F27 is done post-curing. QC intake needed now. Confirm receipt and sampling slot.',
          concise: 'F27 ready for QC intake. Confirm + schedule sampling.'
        },
        escalate: {
          formal: `The following task is blocked and requires attention: "${stuckOne ? stuckOne.title : 'QC water verdict'}". ${stuckOne && stuckOne.blocker ? stuckOne.blocker + ' ' : ''}Please advise on resolution to avoid downstream delay.`,
          friendly: `Quick heads-up — we're stuck on "${stuckOne ? stuckOne.title : 'the QC water verdict'}" and it's holding things up. Could you help us get it moving?`,
          direct: `Blocked: "${stuckOne ? stuckOne.title : 'QC water verdict'}". Need resolution today — downstream tasks are waiting.`,
          concise: `Blocker: ${stuckOne ? stuckOne.title : 'QC water verdict'}. Needs resolution today.`
        },
        update: {
          formal: `This week the team has ${tasks.filter(t => t.status === 'done').length} completed and ${stuck.length} blocked task(s). Priorities remain on schedule with the exception of the noted QC blocker.`,
          friendly: `Week in review: ${tasks.filter(t => t.status === 'done').length} done and ${stuck.length} blocked — mostly on track apart from the QC snag we're clearing.`,
          direct: `Status: ${tasks.filter(t => t.status === 'done').length} done, ${stuck.length} blocked. On track except QC blocker.`,
          concise: `${tasks.filter(t => t.status === 'done').length} done · ${stuck.length} blocked · QC blocker open.`
        },
        reminder: {
          formal: 'This is a courtesy reminder that your assigned task is due Thursday. Please ensure progress notes are recorded ahead of the deadline.',
          friendly: 'Friendly nudge — your task is due Thursday! Drop a progress note when you get a sec 🙂',
          direct: 'Reminder: task due Thursday. Log progress before then.',
          concise: 'Due Thursday. Log progress.'
        }
      };
      const mkMap = {
        handoff: 'Серијата F27 е завршена по сушење и е подготвена за прием во КК. Ве молиме потврдете прием и закажете земање мостри.',
        escalate: `Задачата „${stuckOne ? stuckOne.title : 'вердикт за QC вода'}" е блокирана и бара внимание. Ве молиме за решение за да избегнеме доцнење.`,
        update: `Оваа недела: ${tasks.filter(t => t.status === 'done').length} завршени, ${stuck.length} блокирани. На тек, освен блокадата во КК.`,
        reminder: 'Потсетник: вашата задача е со рок четврток. Запишете белешка за напредок пред рокот.'
      };
      return L ? mkMap[purpose] : map[purpose][tone];
    }
    function generate() {
      setDrafting(true);
      setDraftOut('');
      setCopied(false);
      setTimeout(() => {
        setDrafting(false);
        setDraftOut(composeDraft());
      }, 900);
    }
    const bodyRef = React.useRef(null);
    React.useEffect(() => {
      if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }, [msgs, typing]);
    function answer(q) {
      const ql = q.toLowerCase();
      if (ql.includes('block') || ql.includes('блок') || ql.includes('stuck')) {
        if (!stuck.length) return L ? 'Нема блокирани задачи. 🎉' : 'Nothing is blocked right now.';
        return (L ? 'Блокирани задачи:\n' : 'Blocked tasks:\n') + stuck.map(x => `• ${x.title}${x.blocker ? ' — ' + x.blocker : ''}`).join('\n');
      }
      if (ql.includes('overdue') || ql.includes('задоцн') || ql.includes('доцн')) {
        if (!overdue.length) return L ? 'Нема задоцнети задачи.' : 'No overdue tasks.';
        return (L ? 'Задоцнети:\n' : 'Overdue:\n') + overdue.map(x => `• ${x.title} (${x.due})`).join('\n');
      }
      if (ql.includes('qc') || ql.includes('quality') || ql.includes('квалит')) {
        const qc = tasks.filter(x => x.dept === 'qc' || x.dept === 'qa');
        return (L ? `${qc.length} задачи во QC/QA:\n` : `${qc.length} QC/QA tasks:\n`) + qc.map(x => `• ${x.title} — ${STATUS_LABEL(lang, x.status)}`).join('\n');
      }
      const done = tasks.filter(x => x.status === 'done').length;
      return L ? `Оваа недела: ${tasks.length} задачи, ${done} завршени, ${stuck.length} блокирани. Најголем ризик е блокадата во QC.` : `This week: ${tasks.length} tasks, ${done} done, ${stuck.length} blocked. Biggest risk is the QC blocker.`;
    }
    function send(q) {
      const text = (q ?? input).trim();
      if (!text) return;
      setMsgs(m => [...m, {
        role: 'user',
        text
      }]);
      setInput('');
      setTyping(true);
      setTimeout(() => {
        setTyping(false);
        setMsgs(m => [...m, {
          role: 'ai',
          text: answer(text)
        }]);
      }, 700);
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      onClick: onClose,
      style: {
        position: 'fixed',
        inset: 0,
        background: 'rgba(22,35,59,.35)',
        backdropFilter: 'blur(3px)',
        zIndex: 640,
        animation: 'gfFade .2s ease'
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 400,
        maxWidth: '92vw',
        background: 'var(--surface)',
        borderLeft: '1px solid var(--line)',
        boxShadow: 'var(--sh-3)',
        zIndex: 650,
        display: 'flex',
        flexDirection: 'column',
        animation: 'gfSlideIn .26s cubic-bezier(.22,.61,.36,1)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '16px 18px',
        borderBottom: '1px solid var(--line)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 32,
        height: 32,
        borderRadius: 999,
        background: 'var(--violet-soft)',
        color: 'var(--violet-700)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I('Sparkles', 17)), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 800,
        fontSize: 'var(--fs-15)'
      }
    }, L ? 'Асистент' : 'Assistant'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        color: 'var(--text-muted)',
        fontWeight: 600
      }
    }, L ? 'Прашај за твојата недела' : 'Ask about your week')), /*#__PURE__*/React.createElement(IconButton, {
      size: "sm",
      variant: "ghost",
      onClick: onClose
    }, I('X', 18))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 4,
        padding: '8px 14px 0',
        borderBottom: '1px solid var(--line)'
      }
    }, [['ask', L ? 'Прашај' : 'Ask', 'MessageCircle'], ['draft', L ? 'Состави' : 'Draft', 'PenLine']].map(([id, label, icon]) => /*#__PURE__*/React.createElement("button", {
      key: id,
      onClick: () => setMode(id),
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '9px 14px',
        border: 'none',
        background: 'none',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: mode === id ? 'var(--primary)' : 'var(--text-muted)',
        borderBottom: `2px solid ${mode === id ? 'var(--primary)' : 'transparent'}`,
        marginBottom: -1
      }
    }, I(icon, 15), label))), mode === 'ask' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      ref: bodyRef,
      style: {
        flex: 1,
        overflowY: 'auto',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, msgs.map((m, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
        maxWidth: '85%',
        background: m.role === 'user' ? 'var(--primary)' : 'var(--surface-2)',
        color: m.role === 'user' ? '#fff' : 'var(--text-strong)',
        border: m.role === 'user' ? 'none' : '1px solid var(--line)',
        borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        padding: '10px 13px',
        fontSize: 'var(--fs-13)',
        fontWeight: 500,
        lineHeight: 1.5,
        whiteSpace: 'pre-wrap'
      }
    }, m.text)), typing && /*#__PURE__*/React.createElement("div", {
      style: {
        alignSelf: 'flex-start',
        display: 'flex',
        gap: 4,
        padding: '12px 14px',
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: '14px 14px 14px 4px'
      }
    }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("span", {
      key: i,
      style: {
        width: 6,
        height: 6,
        borderRadius: 999,
        background: 'var(--text-muted)',
        animation: `gfBounce 1s ${i * 0.15}s infinite`
      }
    })))), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '10px 14px',
        borderTop: '1px solid var(--line)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        flexWrap: 'wrap',
        marginBottom: 10
      }
    }, suggestions.map(s => /*#__PURE__*/React.createElement("button", {
      key: s,
      onClick: () => send(s),
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 600,
        padding: '5px 10px',
        borderRadius: 999,
        border: '1px solid var(--line)',
        background: 'var(--surface-2)',
        color: 'var(--text-body)',
        cursor: 'pointer',
        fontFamily: 'inherit'
      }
    }, s))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 8,
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement("input", {
      value: input,
      onChange: e => setInput(e.target.value),
      onKeyDown: e => e.key === 'Enter' && send(),
      placeholder: L ? 'Напиши прашање…' : 'Type a question…',
      style: {
        flex: 1,
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '10px 12px',
        fontSize: 'var(--fs-13)',
        outline: 'none',
        background: 'var(--surface-2)',
        fontFamily: 'inherit',
        color: 'var(--text-strong)'
      }
    }), /*#__PURE__*/React.createElement(IconButton, {
      onClick: () => send()
    }, I('Send', 18))))), mode === 'draft' && /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        overflowY: 'auto',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 16
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        marginBottom: 8
      }
    }, L ? 'Намена' : 'Purpose'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }
    }, purposes.map(p => /*#__PURE__*/React.createElement("button", {
      key: p.id,
      onClick: () => {
        setPurpose(p.id);
        setDraftOut('');
      },
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '10px 12px',
        borderRadius: 'var(--r-md)',
        border: `1px solid ${purpose === p.id ? 'var(--primary)' : 'var(--line)'}`,
        background: purpose === p.id ? 'color-mix(in srgb, var(--primary) 8%, var(--surface))' : 'var(--surface-2)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        textAlign: 'left'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 16,
        height: 16,
        borderRadius: 999,
        border: `2px solid ${purpose === p.id ? 'var(--primary)' : 'var(--line-strong, var(--line))'}`,
        background: purpose === p.id ? 'var(--primary)' : 'transparent',
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, L ? p.mk : p.en))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 800,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        marginBottom: 8
      }
    }, L ? 'Тон' : 'Tone'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        flexWrap: 'wrap'
      }
    }, tones.map(tn => /*#__PURE__*/React.createElement("button", {
      key: tn.id,
      onClick: () => {
        setTone(tn.id);
        if (draftOut) setDraftOut('');
      },
      disabled: L,
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        padding: '7px 13px',
        borderRadius: 999,
        border: `1px solid ${tone === tn.id ? 'var(--primary)' : 'var(--line)'}`,
        background: tone === tn.id ? 'var(--primary)' : 'var(--surface-2)',
        color: tone === tn.id ? '#fff' : 'var(--text-body)',
        cursor: L ? 'default' : 'pointer',
        opacity: L ? 0.5 : 1,
        fontFamily: 'inherit'
      }
    }, L ? tn.mk : tn.en)))), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      onClick: generate,
      style: {
        width: '100%'
      }
    }, drafting ? /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        animation: 'gfSpin 1s linear infinite'
      }
    }, I('LoaderCircle', 16)) : I('Sparkles', 16), drafting ? L ? 'Составувам…' : 'Drafting…' : L ? 'Состави порака' : 'Draft message'), draftOut && /*#__PURE__*/React.createElement("div", {
      style: {
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '13px 14px',
        fontSize: 'var(--fs-13)',
        fontWeight: 500,
        lineHeight: 1.6,
        color: 'var(--text-strong)',
        whiteSpace: 'pre-wrap',
        background: 'var(--surface)'
      }
    }, draftOut), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        padding: '8px 10px',
        borderTop: '1px solid var(--line)',
        background: 'var(--surface-2)'
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: () => {
        navigator.clipboard && navigator.clipboard.writeText(draftOut);
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      },
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        padding: '6px 11px',
        borderRadius: 'var(--r-sm)',
        border: '1px solid var(--line)',
        background: 'var(--surface)',
        color: copied ? 'var(--green-600)' : 'var(--text-body)',
        cursor: 'pointer',
        fontFamily: 'inherit'
      }
    }, I(copied ? 'Check' : 'Copy', 14), copied ? L ? 'Копирано' : 'Copied' : L ? 'Копирај' : 'Copy'), /*#__PURE__*/React.createElement("button", {
      onClick: generate,
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        padding: '6px 11px',
        borderRadius: 'var(--r-sm)',
        border: '1px solid var(--line)',
        background: 'var(--surface)',
        color: 'var(--text-body)',
        cursor: 'pointer',
        fontFamily: 'inherit'
      }
    }, I('RefreshCw', 14), L ? 'Преработи' : 'Rewrite'))))));
  }

  // ─────────────────────────────── Toasts ───────────────────────────────
  function ToastStack({
    toasts,
    onClose
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'fixed',
        bottom: 22,
        right: 22,
        zIndex: 700,
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, toasts.map(t => /*#__PURE__*/React.createElement(Toast, {
      key: t.id,
      tone: t.tone,
      icon: I(t.icon, 16),
      onClose: () => onClose(t.id)
    }, t.text)));
  }
  const STATUS_CYCLE = ['pending', 'working', 'review', 'stuck', 'postponed', 'done'];
  let taskSeq = 100;

  // ─────────────────────────────── App ───────────────────────────────
  function App() {
    const [authed, setAuthed] = React.useState(false);
    const [stage, setStage] = React.useState('splash'); // splash | login
    const [view, setView] = React.useState('myweek');
    const [lang, setLang] = React.useState('en');
    const [theme, setTheme] = React.useState('light');
    const [day, setDay] = React.useState(null);
    const [weekIdx, setWeekIdx] = React.useState(1);
    const [query, setQuery] = React.useState('');
    const [deptFilter, setDeptFilter] = React.useState(null);
    const [modal, setModal] = React.useState(null);
    const [detailTask, setDetailTask] = React.useState(null);
    const [editTask, setEditTask] = React.useState(null);
    const [userPerson, setUserPerson] = React.useState(null);
    const [assistant, setAssistant] = React.useState(false);
    const [currentUser, setCurrentUser] = React.useState('blagoj');
    const [peopleVer, setPeopleVer] = React.useState(0);
    const me = GF_PEOPLE.find(p => p.id === currentUser) || GF_PEOPLE[0];
    const myPerms = GF_ROLE_PERMS(me.role);
    const ownsTask = React.useCallback(t => !!t && (t.owner === currentUser || (t.helpers || []).includes(currentUser)), [currentUser]);
    const canStatus = React.useCallback(t => myPerms.status === 'any' || myPerms.status === 'own' && ownsTask(t), [myPerms, ownsTask]);
    const denyToast = React.useCallback(() => pushToast('error', (lang === 'mk' ? 'Немате дозвола (улога: ' : 'Not permitted for your role (') + (GF_ROLES[me.role] ? GF_ROLES[me.role][lang] : me.role) + ')', 'Lock'), [lang, me]);
    const [tasks, setTasks] = React.useState(() => GF_TASKS.map(t => ({
      ...t,
      color: (GF_DEPARTMENTS.find(d => d.id === t.dept) || {}).color
    })));
    const [toasts, setToasts] = React.useState([]);
    const [handoffs, setHandoffs] = React.useState([{
      from: 'Cultivation',
      to: 'Production',
      item: 'Batch F27 — harvest lot ready for intake',
      status: 'pending',
      by: 'Marko I'
    }, {
      from: 'Production',
      to: 'Quality Control',
      item: 'Batch F26 — post-cure samples staged',
      status: 'done',
      by: 'Ivo K'
    }, {
      from: 'Quality Control',
      to: 'Quality Assurance',
      item: 'Potency results for F25 awaiting QP review',
      status: 'working',
      by: 'Blagoj N'
    }, {
      from: 'Quality Assurance',
      to: 'Logistics',
      item: 'F24 release memo — cleared for shipment',
      status: 'done',
      by: 'Ana P'
    }]);
    const [notifs, setNotifs] = React.useState({
      stuck: true,
      report: true,
      handoff: false
    });
    const [aiBackend, setAiBackend] = React.useState('claude');
    const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);
    useFeel(tw);
    const panel = /*#__PURE__*/React.createElement(FeelTweaks, {
      tw: tw,
      setTweak: setTweak,
      lang: lang
    });
    const pushToast = React.useCallback((tone, text, icon = 'Check') => {
      const id = Math.random().toString(36).slice(2);
      setToasts(ts => [...ts, {
        id,
        tone,
        text,
        icon
      }]);
      setTimeout(() => setToasts(ts => ts.filter(t => t.id !== id)), 3600);
    }, []);
    const closeToast = id => setToasts(ts => ts.filter(t => t.id !== id));
    const cycleStatus = React.useCallback(id => {
      setTasks(ts => ts.map(x => {
        if (x.id !== id) return x;
        if (!canStatus(x)) {
          denyToast();
          return x;
        }
        const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(x.status) + 1) % STATUS_CYCLE.length];
        pushToast(next === 'done' ? 'success' : next === 'stuck' ? 'error' : 'info', `${x.title} → ${STATUS_LABEL(lang, next)}`, next === 'done' ? 'CheckCheck' : next === 'stuck' ? 'OctagonAlert' : 'Loader');
        const updated = {
          ...x,
          status: next,
          overdue: next === 'done' ? false : x.overdue
        };
        setDetailTask(d => d && d.id === id ? updated : d);
        return updated;
      }));
    }, [lang, pushToast, canStatus, denyToast]);
    const toggleDone = React.useCallback(id => {
      setTasks(ts => ts.map(x => {
        if (x.id !== id) return x;
        if (!canStatus(x)) {
          denyToast();
          return x;
        }
        const done = x.status !== 'done';
        if (done) pushToast('success', `${x.title} marked done`, 'CheckCheck');
        const updated = {
          ...x,
          status: done ? 'done' : 'pending'
        };
        setDetailTask(d => d && d.id === id ? updated : d);
        return updated;
      }));
    }, [pushToast, canStatus, denyToast]);
    const dropOnColumn = React.useCallback((id, status) => {
      setTasks(ts => ts.map(x => {
        if (x.id !== id || x.status === status) return x;
        pushToast('info', `${x.title} moved to ${STATUS_LABEL(lang, status)}`, 'Move');
        return {
          ...x,
          status
        };
      }));
    }, [lang, pushToast]);
    const createTask = React.useCallback(({
      id,
      title,
      priority,
      dept,
      type,
      owner,
      helpers,
      days,
      sessionHours,
      recurrence,
      due,
      ref,
      desc,
      tags
    }) => {
      const color = (GF_DEPARTMENTS.find(d => d.id === dept) || {}).color;
      const hp = helpers || [];
      if (id) {
        setTasks(ts => ts.map(x => x.id === id ? {
          ...x,
          title,
          priority,
          pr: priority,
          dept,
          type,
          owner,
          helpers: hp,
          days: days || x.days,
          day: days && days[0] || x.day,
          sessionHours,
          recurrence,
          due,
          ref,
          refCode: ref,
          desc,
          description: desc,
          tags,
          color,
          people: [owner, ...hp].map(pid => {
            const p = GF_PERSON(pid);
            return {
              name: p.name,
              color: p.color
            };
          })
        } : x));
        pushToast('success', `"${title}" updated`, 'Check');
        return;
      }
      taskSeq += 1;
      const newTask = {
        id: `T-${taskSeq}`,
        title,
        status: 'pending',
        priority,
        pr: priority,
        dept,
        type,
        owner,
        helpers: hp,
        due,
        ref,
        refCode: ref,
        desc,
        description: desc,
        sessionHours,
        recurrence,
        tags: tags || [],
        day: days && days[0] || 'Mon',
        days: days && days.length ? days : ['Mon'],
        weekIdx,
        color,
        people: [owner, ...hp].map(pid => {
          const p = GF_PERSON(pid);
          return {
            name: p.name,
            color: p.color
          };
        })
      };
      setTasks(ts => [newTask, ...ts]);
      pushToast('success', `"${title}" created`, 'Plus');
    }, [pushToast, weekIdx]);
    const saveUser = React.useCallback(({
      id,
      name,
      role,
      dept,
      color
    }) => {
      if (id) {
        const p = GF_PEOPLE.find(x => x.id === id);
        if (p) {
          p.name = name;
          p.role = role;
          p.dept = dept;
          p.color = color;
        }
        pushToast('success', (lang === 'mk' ? 'Зачувано: ' : 'Saved: ') + name, 'Check');
      } else {
        const nid = name.toLowerCase().replace(/[^a-z]+/g, '-').slice(0, 12) + '-' + Math.random().toString(36).slice(2, 5);
        GF_PEOPLE.push({
          id: nid,
          name,
          role,
          dept,
          color,
          active: 0,
          done: 0
        });
        pushToast('success', (lang === 'mk' ? 'Додаден член: ' : 'Member added: ') + name, 'UserPlus');
      }
      setPeopleVer(v => v + 1);
    }, [pushToast, lang]);
    const removeUser = React.useCallback(id => {
      if (!myPerms.team) {
        denyToast();
        return;
      }
      if (GF_PEOPLE.length <= 1) return;
      const idx = GF_PEOPLE.findIndex(x => x.id === id);
      if (idx >= 0) {
        const nm = GF_PEOPLE[idx].name;
        GF_PEOPLE.splice(idx, 1);
        pushToast('info', (lang === 'mk' ? 'Отстранет: ' : 'Removed: ') + nm, 'Trash2');
      }
      if (currentUser === id) setCurrentUser(GF_PEOPLE[0].id);
      setPeopleVer(v => v + 1);
    }, [myPerms, denyToast, pushToast, lang, currentUser]);
    const setActiveUser = React.useCallback(id => {
      setCurrentUser(id);
      const p = GF_PEOPLE.find(x => x.id === id);
      if (p) pushToast('success', (lang === 'mk' ? 'Активен: ' : 'Now acting as ') + p.name, 'UserCheck');
    }, [pushToast, lang]);
    const deleteTask = React.useCallback(id => {
      if (!myPerms.deleteAny) {
        denyToast();
        return;
      }
      setTasks(ts => ts.filter(x => x.id !== id));
      pushToast('info', lang === 'mk' ? 'Задачата е избришана' : 'Task deleted', 'Trash2');
    }, [myPerms, denyToast, pushToast, lang]);
    const advanceHandoff = React.useCallback(i => {
      setHandoffs(hs => hs.map((h, idx) => {
        if (idx !== i) return h;
        const seq = ['pending', 'working', 'review', 'done'];
        const next = seq[Math.min(seq.indexOf(h.status) + 1, seq.length - 1)];
        pushToast(next === 'done' ? 'success' : 'info', `${h.from} → ${h.to}: ${STATUS_LABEL(lang, next)}`, next === 'done' ? 'CheckCheck' : 'Loader');
        return {
          ...h,
          status: next
        };
      }));
    }, [lang, pushToast]);
    const toggleNotif = React.useCallback(key => setNotifs(n => ({
      ...n,
      [key]: !n[key]
    })), []);
    React.useEffect(() => {
      document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);
    React.useEffect(() => {
      const onKey = e => {
        const tag = (e.target.tagName || '').toUpperCase();
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
          e.preventDefault();
          const el = document.getElementById('gf-search');
          if (el) el.focus();
          return;
        }
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) {
          if (e.key === 'Escape') e.target.blur();
          return;
        }
        if (e.key === 'n' && stage === 'app') {
          e.preventDefault();
          setModal('add');
        }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [stage]);
    if (stage === 'splash') return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Splash, {
      onDone: () => setStage('login'),
      lang: lang,
      logo: tw.logo
    }), panel);
    if (!authed) return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Login, {
      onSignIn: () => {
        setAuthed(true);
        pushToast('success', 'Signed in as Blagoj Nikolov');
      },
      lang: lang,
      logo: tw.logo
    }), panel);
    const weekTasks = tasks.filter(x => x.weekIdx === weekIdx);
    const scoped = deptFilter ? weekTasks.filter(x => x.dept === deptFilter) : weekTasks;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        height: '100%',
        width: '100%'
      }
    }, /*#__PURE__*/React.createElement(Sidebar, {
      view: view,
      setView: setView,
      lang: lang,
      me: me,
      tasks: tasks,
      deptFilter: deptFilter,
      setDeptFilter: setDeptFilter
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement(Header, {
      lang: lang,
      setLang: setLang,
      theme: theme,
      setTheme: setTheme,
      onNew: () => setModal('add'),
      onVoice: () => setModal('voice'),
      onOpenReport: () => setView('report'),
      onWorklog: () => setModal('worklog'),
      onAssistant: () => setAssistant(true),
      me: me,
      query: query,
      setQuery: setQuery,
      weekIdx: weekIdx,
      setWeekIdx: setWeekIdx
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minHeight: 0,
        background: 'var(--bg)',
        backgroundImage: 'var(--plasma-grid)',
        display: 'flex',
        flexDirection: 'column'
      }
    }, deptFilter && (view === 'myweek' || view === 'board') && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '9px 24px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--line)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-muted)'
      }
    }, lang === 'mk' ? 'Филтрирано по:' : 'Filtered by:'), /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-strong)',
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 999,
        padding: '4px 6px 4px 11px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 8,
        height: 8,
        borderRadius: 999,
        background: (GF_DEPARTMENTS.find(d => d.id === deptFilter) || {}).color
      }
    }), (() => {
      const d = GF_DEPARTMENTS.find(x => x.id === deptFilter) || {};
      return lang === 'mk' ? d.mk : d.name;
    })(), /*#__PURE__*/React.createElement("button", {
      onClick: () => setDeptFilter(null),
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 18,
        height: 18,
        borderRadius: 999,
        border: 'none',
        background: 'var(--line)',
        color: 'var(--text-body)',
        cursor: 'pointer'
      }
    }, I('X', 12)))), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minHeight: 0
      }
    }, view === 'myweek' && /*#__PURE__*/React.createElement(MyWeek, {
      lang: lang,
      day: day,
      setDay: setDay,
      weekIdx: weekIdx,
      setWeekIdx: setWeekIdx,
      tasks: scoped,
      query: query,
      onCycle: cycleStatus,
      onCheck: toggleDone,
      onNew: () => setModal('add'),
      onEdit: setEditTask,
      onDelete: deleteTask,
      onOpen: setDetailTask,
      canEdit: tk => myPerms.editAny || ownsTask(tk),
      canDelete: myPerms.deleteAny
    }), view === 'board' && /*#__PURE__*/React.createElement(Board, {
      lang: lang,
      tasks: scoped,
      query: query,
      onDrop: dropOnColumn,
      onOpen: setDetailTask
    }), view === 'dash' && /*#__PURE__*/React.createElement(Dashboard, {
      lang: lang,
      tasks: weekTasks
    }), view === 'timeline' && /*#__PURE__*/React.createElement(window.GFScreens.Timeline, {
      lang: lang,
      tasks: weekTasks
    }), view === 'coord' && /*#__PURE__*/React.createElement(window.GFScreens.Coordination, {
      lang: lang,
      handoffs: handoffs,
      onAdvance: advanceHandoff
    }), view === 'team' && /*#__PURE__*/React.createElement(window.GFScreens.Team, {
      lang: lang,
      onOpenPerson: setUserPerson,
      onAdd: () => setUserPerson({
        __new: true
      }),
      canManage: myPerms.team,
      currentUser: currentUser,
      peopleVer: peopleVer
    }), view === 'report' && /*#__PURE__*/React.createElement(window.GFScreens.AIReport, {
      lang: lang,
      tasks: weekTasks,
      onToast: pushToast
    }), view === 'settings' && /*#__PURE__*/React.createElement(window.GFScreens.Settings, {
      lang: lang,
      setLang: setLang,
      theme: theme,
      setTheme: setTheme,
      notifs: notifs,
      onToggleNotif: toggleNotif,
      aiBackend: aiBackend,
      setAiBackend: setAiBackend,
      currentUser: currentUser,
      setCurrentUser: setCurrentUser,
      myPerms: myPerms
    }), view === 'audit' && /*#__PURE__*/React.createElement(window.GFScreens.AuditTrail, {
      lang: lang
    }), view === 'import' && /*#__PURE__*/React.createElement(window.GFScreens.ImportView, {
      lang: lang,
      onToast: pushToast
    }), view === 'analytics' && /*#__PURE__*/React.createElement(window.GFScreens.Analytics, {
      lang: lang
    }), view === 'planning' && /*#__PURE__*/React.createElement(window.GFScreens.Planning, {
      lang: lang,
      onToast: pushToast
    }), view === 'qclab' && /*#__PURE__*/React.createElement(window.GFScreens.QCLab, {
      lang: lang,
      onToast: pushToast
    }), view === 'access' && /*#__PURE__*/React.createElement(window.GFScreens.Access, {
      lang: lang,
      onToast: pushToast
    }), view === 'governance' && /*#__PURE__*/React.createElement(window.GFScreens.Governance, {
      lang: lang,
      onToast: pushToast
    })))), modal === 'voice' && /*#__PURE__*/React.createElement(VoiceModal, {
      onClose: () => setModal(null),
      onConfirm: () => {
        setModal(null);
        createTask({
          title: 'Validate HPLC method for potency (voice)',
          priority: 'critical',
          dept: 'qc',
          type: 'Validation'
        });
        pushToast('success', 'Task created from voice capture', 'Mic');
      },
      lang: lang
    }), modal === 'add' && /*#__PURE__*/React.createElement(AddTaskModal, {
      onClose: () => setModal(null),
      onCreate: vals => {
        setModal(null);
        createTask(vals);
      },
      lang: lang
    }), editTask && /*#__PURE__*/React.createElement(AddTaskModal, {
      editTask: editTask,
      onClose: () => setEditTask(null),
      onCreate: vals => {
        setEditTask(null);
        createTask(vals);
      },
      lang: lang
    }), userPerson && /*#__PURE__*/React.createElement(UserModal, {
      person: userPerson.__new ? null : userPerson,
      lang: lang,
      onClose: () => setUserPerson(null),
      canManage: myPerms.team,
      isActive: userPerson && userPerson.id === currentUser,
      onSetActive: setActiveUser,
      onSave: v => {
        saveUser(v);
        setUserPerson(null);
      },
      onRemove: removeUser
    }), modal === 'worklog' && /*#__PURE__*/React.createElement(WorklogModal, {
      lang: lang,
      onClose: () => setModal(null)
    }), detailTask && /*#__PURE__*/React.createElement(TaskDetailModal, {
      task: detailTask,
      lang: lang,
      allTasks: tasks,
      canEdit: canStatus(detailTask),
      onClose: () => setDetailTask(null),
      onCycle: cycleStatus,
      onCheck: toggleDone
    }), assistant && /*#__PURE__*/React.createElement(AssistantPanel, {
      lang: lang,
      tasks: tasks,
      onClose: () => setAssistant(false)
    }), /*#__PURE__*/React.createElement(ToastStack, {
      toasts: toasts,
      onClose: closeToast
    }), panel);
  }
  ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(App, null));
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/growflow/app.js", error: String((e && e.message) || e) }); }

// ui_kits/growflow/data.js
try { (() => {
// Real org model (from WEEKLY_WEED_FLOW/web/gf/data.js) — 11 departments.
const GF_DEPARTMENTS = [{
  id: 'clone',
  name: 'Cloning & Nursery',
  mk: 'Клонирање и расадник',
  icon: 'Sprout',
  color: '#15A86B'
}, {
  id: 'veg',
  name: 'Vegetation',
  mk: 'Вегетација',
  icon: 'Leaf',
  color: '#3FA34D'
}, {
  id: 'flower',
  name: 'Flowering',
  mk: 'Цветање',
  icon: 'Sun',
  color: '#FF7A1A'
}, {
  id: 'irr',
  name: 'Irrigation',
  mk: 'Наводнување',
  icon: 'Droplet',
  color: '#0EA5A5'
}, {
  id: 'prod',
  name: 'Production',
  mk: 'Производство',
  icon: 'Package',
  color: '#2F6BFF'
}, {
  id: 'qc',
  name: 'Quality Control',
  mk: 'Контрола на квалитет',
  icon: 'FlaskConical',
  color: '#7A5BE0'
}, {
  id: 'qa',
  name: 'QA / QP',
  mk: 'ОК / КвЛ',
  icon: 'ShieldCheck',
  color: '#C2410C'
}, {
  id: 'whin',
  name: 'Warehouse In',
  mk: 'Магацин (влез)',
  icon: 'PackagePlus',
  color: '#0891B2'
}, {
  id: 'whout',
  name: 'Warehouse Out',
  mk: 'Магацин (излез)',
  icon: 'PackageMinus',
  color: '#D6336C'
}, {
  id: 'sec',
  name: 'Security',
  mk: 'Обезбедување',
  icon: 'Shield',
  color: '#566884'
}, {
  id: 'maint',
  name: 'Maintenance',
  mk: 'Одржување',
  icon: 'Wrench',
  color: '#5A6B82'
}];

// Cross-department handoff chain (render.js GF.HANDOFF)
const GF_HANDOFF = {
  clone: 'veg',
  veg: 'flower',
  flower: 'prod',
  prod: 'qc',
  qc: 'qa',
  qa: 'whout',
  irr: 'prod',
  whin: 'prod',
  maint: 'irr'
};

// 8 task types (backend enum) with EN/МК chip labels
const GF_TASK_TYPES = {
  capa: {
    en: 'CAPA',
    mk: 'CAPA'
  },
  sop: {
    en: 'SOP',
    mk: 'СОП'
  },
  validation: {
    en: 'Validation',
    mk: 'Валидација'
  },
  document: {
    en: 'Document',
    mk: 'Документ'
  },
  lab: {
    en: 'Lab',
    mk: 'Лабораторија'
  },
  meeting: {
    en: 'Meeting',
    mk: 'Состанок'
  },
  admin: {
    en: 'Admin',
    mk: 'Админ'
  },
  other: {
    en: 'Other',
    mk: 'Друго'
  }
};

// Roles (core.js GF.ROLES) — admin is a system role, never offered in the picker.
const GF_ROLES = {
  admin: {
    en: 'Administrator',
    mk: 'Администратор'
  },
  ceo: {
    en: 'CEO',
    mk: 'Извршен директор'
  },
  coo: {
    en: 'COO',
    mk: 'Оперативен директор'
  },
  qa_mgr: {
    en: 'QA Manager',
    mk: 'Менаџер за КО'
  },
  qc_mgr: {
    en: 'QC Manager',
    mk: 'Менаџер за КК'
  },
  pr_mgr: {
    en: 'Production Manager',
    mk: 'Менаџер за производство'
  },
  wh_mgr: {
    en: 'Warehouse Manager',
    mk: 'Менаџер за магацин'
  },
  sc_mgr: {
    en: 'Supply Chain Manager',
    mk: 'Менаџер за снабдување'
  },
  cu_mgr: {
    en: 'Cultivation Manager',
    mk: 'Менаџер за одгледување'
  },
  qp: {
    en: 'Qualified Person',
    mk: 'Квалификувано лице'
  },
  operator: {
    en: 'Operator',
    mk: 'Оператор'
  }
};
// Permissions: execs + managers + QP get the full row; operator is own-tasks-only.
const GF_PERMS = {
  _full: {
    create: true,
    editAny: true,
    deleteAny: true,
    status: 'any',
    team: true
  },
  operator: {
    create: true,
    editAny: false,
    deleteAny: false,
    status: 'own',
    team: false
  }
};
const GF_ROLE_PERMS = role => role === 'operator' ? GF_PERMS.operator : GF_PERMS._full;
const GF_T = {
  en: {
    myweek: 'My Week',
    board: 'Board',
    timeline: 'Timeline',
    coord: 'Coordination',
    dash: 'Dashboard',
    team: 'Team',
    depts: 'Departments',
    settings: 'Settings',
    assistant: 'Assistant',
    newtask: 'New task',
    voice: 'Voice task',
    today: 'Today',
    addtask: 'Add a task — or speak it',
    thisweek: 'This week',
    search: 'Search tasks, batches, rooms…',
    notasks: 'No tasks here yet.',
    noresults: 'No matches for',
    signin: 'Sign in',
    completion: 'Completion',
    total: 'Total',
    working: 'Working',
    stuck: 'Stuck',
    busiest: 'Busiest day'
  },
  mk: {
    myweek: 'Моја недела',
    board: 'Табла',
    timeline: 'Времеплов',
    coord: 'Координација',
    dash: 'Контролна табла',
    team: 'Тим',
    depts: 'Оддели',
    settings: 'Поставки',
    assistant: 'Асистент',
    newtask: 'Нова задача',
    voice: 'Гласовна задача',
    today: 'Денес',
    addtask: 'Додај задача — или кажи ја',
    thisweek: 'Оваа недела',
    search: 'Барај задачи, серии, простории…',
    notasks: 'Сè уште нема задачи.',
    noresults: 'Нема резултати за',
    signin: 'Најави се',
    completion: 'Завршеност',
    total: 'Вкупно',
    working: 'Во тек',
    stuck: 'Блокирани',
    busiest: 'Најнатоварен ден'
  }
};

// People keyed by id (core.js GF.PEOPLE). role uses GF_ROLES tokens.
const GF_PEOPLE = [{
  id: 'marko',
  name: 'Marko Ilievski',
  role: 'coo',
  dept: 'prod',
  active: 8,
  done: 41,
  color: '#2F6BFF'
}, {
  id: 'blagoj',
  name: 'Blagoj Nikolov',
  role: 'qc_mgr',
  dept: 'qc',
  active: 6,
  done: 37,
  color: '#7A5BE0'
}, {
  id: 'ana',
  name: 'Ana Petrova',
  role: 'qa_mgr',
  dept: 'qa',
  active: 6,
  done: 33,
  color: '#C2410C'
}, {
  id: 'elena',
  name: 'Elena Stojanova',
  role: 'qp',
  dept: 'qa',
  active: 3,
  done: 28,
  color: '#D6336C'
}, {
  id: 'goran',
  name: 'Goran Stojanov',
  role: 'cu_mgr',
  dept: 'veg',
  active: 5,
  done: 29,
  color: '#3FA34D'
}, {
  id: 'ivo',
  name: 'Ivo Kirov',
  role: 'operator',
  dept: 'flower',
  active: 4,
  done: 22,
  color: '#FF7A1A'
}, {
  id: 'sara',
  name: 'Sara Mitrova',
  role: 'wh_mgr',
  dept: 'whout',
  active: 3,
  done: 18,
  color: '#0891B2'
}, {
  id: 'kire',
  name: 'Kire Todorov',
  role: 'operator',
  dept: 'whin',
  active: 2,
  done: 15,
  color: '#0EA5A5'
}];
const GF_PERSON = id => GF_PEOPLE.find(p => p.id === id) || {
  name: '?',
  color: '#8A99B0'
};

// Rich tasks — owner + helpers (RACI), multi-day, v2 badges (ref/type/due/subtasks/hours/tags).
const GF_TASKS = [{
  id: 'T-4KZ9',
  title: 'Validate HPLC method for potency',
  status: 'working',
  pr: 'critical',
  weekIdx: 1,
  owner: 'blagoj',
  helpers: ['ana'],
  due: '2026-07-09',
  type: 'validation',
  ref: 'PP-QC-012',
  sessionHours: 3.5,
  subDone: 2,
  subCount: 3,
  tags: ['potency', 'batch-F27'],
  days: ['Wed', 'Thu'],
  dept: 'qc',
  desc: 'Run system-suitability + linearity per protocol PP-QC-012. Record retention times and tailing factors before releasing batch F27.',
  notes: [{
    d: 'Mon',
    n: 'Column equilibrated; mobile phase prepared.'
  }, {
    d: 'Tue',
    n: 'Linearity R²=0.9997 across 5 levels.'
  }],
  deps: ['T-1H7C']
}, {
  id: 'T-2M1P',
  title: 'Post-curing sampling — Batch F27',
  status: 'stuck',
  pr: 'high',
  weekIdx: 1,
  owner: 'ivo',
  helpers: ['blagoj'],
  due: '2026-06-29',
  type: 'lab',
  ref: 'SP-06',
  days: ['Mon'],
  dept: 'flower',
  blocker: 'Waiting on QC water verdict before sampling can proceed.',
  desc: 'Post-curing sampling wizard SP-06: draw containers per formula, run pass/fail gates, record disposition.'
}, {
  id: 'T-8Q4A',
  title: 'Update transport SOP for finished goods',
  status: 'review',
  pr: 'medium',
  weekIdx: 1,
  owner: 'sara',
  helpers: ['kire'],
  due: '2026-07-10',
  type: 'sop',
  ref: 'PP-LOG-004',
  subDone: 3,
  subCount: 4,
  days: ['Fri'],
  dept: 'whout',
  desc: 'Revise cold-chain handling section; align with new GDP guidance.',
  tags: ['gdp']
}, {
  id: 'T-1H7C',
  title: 'CAPA — deviation on RH sensor calibration',
  status: 'pending',
  pr: 'high',
  weekIdx: 1,
  owner: 'ana',
  helpers: [],
  due: '2026-07-10',
  type: 'capa',
  ref: 'PP-QA-089',
  days: ['Thu'],
  dept: 'qa'
}, {
  id: 'T-5D0X',
  title: 'Weekly line-clearance checklist',
  status: 'done',
  pr: 'low',
  weekIdx: 1,
  owner: 'ana',
  helpers: [],
  type: 'admin',
  sessionHours: 1,
  days: ['Mon'],
  dept: 'prod'
}, {
  id: 'T-9F3B',
  title: 'Irrigation dosing — Veg room 2',
  status: 'working',
  pr: 'medium',
  weekIdx: 1,
  owner: 'goran',
  helpers: [],
  due: '2026-07-08',
  type: 'other',
  sessionHours: 2,
  days: ['Wed'],
  dept: 'irr',
  tags: ['veg-2']
}, {
  id: 'T-6R2K',
  title: 'Label reconciliation — Batch F26',
  status: 'postponed',
  pr: 'medium',
  weekIdx: 1,
  owner: 'sara',
  helpers: [],
  type: 'document',
  ref: 'PP-WH-021',
  days: ['Fri'],
  dept: 'whin'
}, {
  id: 'T-3T7L',
  title: 'Mother-plant health check — Clone room',
  status: 'working',
  pr: 'medium',
  weekIdx: 1,
  owner: 'goran',
  helpers: ['ivo'],
  due: '2026-07-08',
  type: 'other',
  days: ['Tue', 'Wed'],
  dept: 'clone',
  tags: ['mothers']
}, {
  id: 'T-7B2N',
  title: 'QP batch release — F25',
  status: 'review',
  pr: 'critical',
  weekIdx: 1,
  owner: 'elena',
  helpers: ['ana'],
  due: '2026-07-11',
  type: 'document',
  ref: 'PP-QA-102',
  days: ['Fri'],
  dept: 'qa',
  tags: ['release']
},
// ── Last week (weekIdx 0) — mostly closed out ──
{
  id: 'T-0A1B',
  title: 'Harvest logging — Batch F25',
  status: 'done',
  pr: 'high',
  weekIdx: 0,
  owner: 'ivo',
  helpers: ['goran'],
  type: 'lab',
  ref: 'SP-04',
  sessionHours: 5,
  days: ['Tue', 'Wed'],
  dept: 'flower',
  tags: ['harvest'],
  desc: 'Wet-weight logging and tag reconciliation for F25 at harvest.'
}, {
  id: 'T-0C2D',
  title: 'Nutrient stock audit — Veg',
  status: 'done',
  pr: 'medium',
  weekIdx: 0,
  owner: 'goran',
  helpers: [],
  type: 'other',
  sessionHours: 1.5,
  days: ['Mon'],
  dept: 'irr'
}, {
  id: 'T-0E3F',
  title: 'CoA compilation — Batch F24',
  status: 'done',
  pr: 'critical',
  weekIdx: 0,
  owner: 'elena',
  helpers: ['ana'],
  type: 'document',
  ref: 'PP-QA-098',
  days: ['Fri'],
  dept: 'qa',
  tags: ['release']
}, {
  id: 'T-0G4H',
  title: 'Deviation review — RH excursion',
  status: 'stuck',
  pr: 'high',
  weekIdx: 0,
  owner: 'ana',
  helpers: [],
  type: 'capa',
  ref: 'PP-QA-085',
  days: ['Thu'],
  dept: 'qa',
  blocker: 'Carried into this week — awaiting engineering root-cause.'
},
// ── Next week (weekIdx 2) — plan / upcoming ──
{
  id: 'T-2A5J',
  title: 'Method transfer — HPLC to QC-2',
  status: 'pending',
  pr: 'high',
  weekIdx: 2,
  owner: 'blagoj',
  helpers: ['elena'],
  due: '2026-07-15',
  type: 'validation',
  ref: 'PP-QC-020',
  days: ['Mon', 'Tue'],
  dept: 'qc',
  desc: 'Transfer validated HPLC potency method to the second QC bench; run comparative suitability.'
}, {
  id: 'T-2B6K',
  title: 'Stability pull — 3-month timepoint',
  status: 'pending',
  pr: 'medium',
  weekIdx: 2,
  owner: 'ana',
  helpers: [],
  due: '2026-07-16',
  type: 'lab',
  ref: 'SP-11',
  days: ['Wed'],
  dept: 'qc',
  tags: ['stability']
}, {
  id: 'T-2C7L',
  title: 'Cold-chain SOP rollout training',
  status: 'pending',
  pr: 'medium',
  weekIdx: 2,
  owner: 'sara',
  helpers: ['kire'],
  due: '2026-07-17',
  type: 'sop',
  ref: 'PP-LOG-004',
  days: ['Thu', 'Fri'],
  dept: 'whout'
}, {
  id: 'T-2D8M',
  title: 'Clone propagation — next cycle',
  status: 'pending',
  pr: 'low',
  weekIdx: 2,
  owner: 'goran',
  helpers: ['ivo'],
  due: '2026-07-16',
  type: 'other',
  days: ['Tue'],
  dept: 'clone',
  tags: ['mothers']
}];

// ── Back-compat augmentation: existing screens read legacy field names.
//    Give every task/person the aliases + derived fields the UI consumes.
const _todayISO = new Date().toISOString().slice(0, 10);
GF_TASKS.forEach(t => {
  const d = GF_DEPARTMENTS.find(x => x.id === t.dept) || GF_DEPARTMENTS[0];
  t.priority = t.pr;
  t.weekIdx = t.weekIdx == null ? 1 : t.weekIdx;
  t.color = d.color;
  t.day = (t.days || [])[0] || null;
  t.refCode = t.ref;
  t.hours = t.sessionHours;
  t.description = t.desc;
  t.overdue = !!(t.due && t.status !== 'done' && t.due < _todayISO);
  t.subtasks = t.subCount ? `${t.subDone || 0}/${t.subCount}` : null;
  t.people = [t.owner, ...(t.helpers || [])].map(id => {
    const p = GF_PERSON(id);
    return {
      name: p.name,
      color: p.color
    };
  });
  // notes already {d,n}; add {date,text} alias for legacy renderers
  t.notes = (t.notes || []).map(n => ({
    ...n,
    date: n.d,
    text: n.n
  }));
  // deps id-list → {label,met} for legacy renderers
  t._depObjs = (t.deps || []).map(id => {
    const dt = GF_TASKS.find(x => x.id === id);
    return dt ? {
      label: dt.title,
      met: dt.status === 'done'
    } : null;
  }).filter(Boolean);
});
GF_PEOPLE.forEach(p => {
  const r = GF_ROLES[p.role];
  p.roleToken = p.role;
  p.roleLabel = r ? r.en : p.role;
});
window.GF_DEPARTMENTS = GF_DEPARTMENTS;
window.GF_T = GF_T;
window.GF_TASKS = GF_TASKS;
window.GF_PEOPLE = GF_PEOPLE;
window.GF_PERSON = GF_PERSON;
window.GF_HANDOFF = GF_HANDOFF;
window.GF_TASK_TYPES = GF_TASK_TYPES;
window.GF_ROLES = GF_ROLES;
window.GF_ROLE_PERMS = GF_ROLE_PERMS;

// ── PopSelect — popup single-choice picker that replaces every native dropdown ──
// options: [{ value, label, color?, sub? }].  onChange(value).  title = popup heading.
function PopSelect({
  value,
  onChange,
  options,
  title,
  placeholder,
  disabled = false
}) {
  const [open, setOpen] = React.useState(false);
  const opts = options || [];
  const sel = opts.find(o => o.value === value);
  const label = sel ? sel.label : placeholder || 'Select…';
  React.useEffect(() => {
    if (!open) return;
    const onKey = e => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open]);
  const trigger = /*#__PURE__*/React.createElement("button", {
    type: "button",
    disabled: disabled,
    onClick: () => !disabled && setOpen(true),
    style: {
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 10,
      fontFamily: 'var(--font-app)',
      fontSize: 'var(--fs-14)',
      textAlign: 'left',
      color: sel ? 'var(--text-strong)' : 'var(--text-muted)',
      background: 'var(--surface-2)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-md)',
      padding: '10px 12px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.55 : 1,
      transition: 'border-color var(--dur-ui), box-shadow var(--dur-ui)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      overflow: 'hidden'
    }
  }, sel && sel.color && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      borderRadius: 3,
      background: sel.color,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, label)), /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "var(--text-muted)",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4"
  })));
  return /*#__PURE__*/React.createElement(React.Fragment, null, trigger, open && /*#__PURE__*/React.createElement("div", {
    onClick: () => setOpen(false),
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 700,
      background: 'var(--overlay)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
      animation: 'gf-overlay-in var(--dur-ui) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: '100%',
      maxWidth: 420,
      maxHeight: '72vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface-card)',
      color: 'var(--text-strong)',
      borderRadius: 'var(--r-2xl)',
      border: '1px solid var(--border-strong)',
      boxShadow: 'var(--sh-3)',
      overflow: 'hidden',
      animation: 'gf-modal-in var(--dur-panel) var(--ease-spring)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '15px 20px',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontFamily: 'var(--font-display)',
      fontSize: 'var(--fs-14)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '.08em'
    }
  }, title || 'Select'), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      left: 0,
      bottom: -1,
      height: 2,
      width: 56,
      background: 'var(--primary)',
      boxShadow: 'var(--sh-glow)'
    }
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setOpen(false),
    style: {
      appearance: 'none',
      border: 0,
      background: 'transparent',
      color: 'var(--text-muted)',
      cursor: 'pointer',
      fontSize: 17,
      lineHeight: 1,
      padding: 4
    }
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    style: {
      overflowY: 'auto',
      padding: 6
    }
  }, opts.map(o => {
    const active = o.value === value;
    return /*#__PURE__*/React.createElement("button", {
      key: String(o.value),
      type: "button",
      onClick: () => {
        onChange(o.value);
        setOpen(false);
      },
      style: {
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        textAlign: 'left',
        fontFamily: 'var(--font-app)',
        fontSize: 'var(--fs-14)',
        fontWeight: active ? 700 : 500,
        color: active ? 'var(--primary-fg)' : 'var(--text-strong)',
        background: active ? 'var(--primary-soft)' : 'transparent',
        border: '1px solid ' + (active ? 'var(--primary)' : 'transparent'),
        borderRadius: 'var(--r-md)',
        padding: '11px 13px',
        margin: '2px 0',
        cursor: 'pointer'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        overflow: 'hidden'
      }
    }, o.color && /*#__PURE__*/React.createElement("span", {
      style: {
        width: 11,
        height: 11,
        borderRadius: 3,
        background: o.color,
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, o.label), o.sub && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 500,
        color: 'var(--text-muted)'
      }
    }, o.sub))), active && /*#__PURE__*/React.createElement("svg", {
      width: "16",
      height: "16",
      viewBox: "0 0 16 16",
      fill: "none",
      stroke: "var(--primary)",
      strokeWidth: "2.4",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      style: {
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: "M3 8.5l3.5 3.5L13 4"
    })));
  })))));
}
window.PopSelect = PopSelect;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/growflow/data.js", error: String((e && e.message) || e) }); }

// ui_kits/growflow/screens.js
try { (() => {
// GrowFlow UI kit — Team, Timeline, Coordination, AI Report, Settings screens.
(function () {
  const {
    GF_DEPARTMENTS,
    GF_HANDOFF,
    GF_TASK_TYPES,
    GF_ROLES,
    GF_ROLE_PERMS,
    GF_T,
    GF_PEOPLE,
    GF_PERSON,
    GF_TASKS
  } = window;
  const DS2 = window.GrowFlowDesignSystem_7accb1;
  const {
    Avatar,
    AvatarStack,
    Badge,
    Button,
    IconButton,
    Switch,
    Segmented,
    Select,
    Field,
    KpiTile,
    BarRow,
    Leaf,
    PriorityTag
  } = DS2;
  const PopSelect = window.PopSelect;
  const I2 = (name, sz = 18) => {
    const n = window.lucide && lucide.icons[name];
    if (!n) return null;
    const kids = n.find(Array.isArray) || [];
    return React.createElement('svg', {
      width: sz,
      height: sz,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round',
      strokeLinejoin: 'round'
    }, kids.map(([t, a], i) => React.createElement(t, {
      key: i,
      ...a
    })));
  };
  function Panel2({
    title,
    right = null,
    children,
    style = {}
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
        boxShadow: 'var(--sh-1)',
        ...style
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-14)',
        fontWeight: 800
      }
    }, title), right), children);
  }
  function Team({
    lang,
    onOpenPerson,
    onAdd,
    canManage,
    currentUser,
    peopleVer
  }) {
    const t = GF_T[lang];
    const deptName = id => {
      const d = GF_DEPARTMENTS.find(x => x.id === id);
      return d ? lang === 'mk' ? d.mk : d.name : id;
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800
      }
    }, t.team), /*#__PURE__*/React.createElement(Badge, {
      tone: "neutral"
    }, GF_PEOPLE.length), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), canManage ? /*#__PURE__*/React.createElement(Button, {
      onClick: onAdd
    }, I2('Plus', 15), "\xA0", lang === 'mk' ? 'Додади член' : 'Add member') : /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, I2('Shield', 14), lang === 'mk' ? 'Само преглед' : 'View only')), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: 14
      }
    }, GF_PEOPLE.map(p => /*#__PURE__*/React.createElement("div", {
      key: p.name,
      onClick: () => onOpenPerson && onOpenPerson(p),
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
        boxShadow: 'var(--sh-1)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        cursor: 'pointer',
        transition: 'box-shadow var(--dur-ui), transform var(--dur-ui)'
      },
      onMouseEnter: e => {
        e.currentTarget.style.boxShadow = 'var(--sh-2)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      },
      onMouseLeave: e => {
        e.currentTarget.style.boxShadow = 'var(--sh-1)';
        e.currentTarget.style.transform = 'none';
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: p.name,
      size: 42,
      color: p.color
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 700,
        fontSize: 'var(--fs-14)',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, p.name, p.id === currentUser && /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 7,
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: 'var(--primary)',
        background: 'var(--primary-soft)',
        borderRadius: 999,
        padding: '2px 7px',
        verticalAlign: 'middle'
      }
    }, lang === 'mk' ? 'ВИЕ' : 'YOU')), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--text-body)',
        fontWeight: 600
      }
    }, GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.roleLabel))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 7
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 8,
        height: 8,
        borderRadius: 999,
        background: p.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-body)'
      }
    }, deptName(p.dept))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        background: 'var(--surface-2)',
        borderRadius: 'var(--r-sm)',
        padding: '8px 10px',
        textAlign: 'center'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 800,
        fontSize: 'var(--fs-17)'
      }
    }, p.active), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.03em'
      }
    }, t.working)), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        background: 'var(--green-100)',
        borderRadius: 'var(--r-sm)',
        padding: '8px 10px',
        textAlign: 'center'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 800,
        fontSize: 'var(--fs-17)',
        color: 'var(--green-700)'
      }
    }, p.done), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        color: 'var(--green-700)',
        textTransform: 'uppercase',
        letterSpacing: '.03em'
      }
    }, "Done")))))));
  }
  function Timeline({
    lang,
    tasks
  }) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    const daysMk = {
      Mon: 'Пон',
      Tue: 'Вто',
      Wed: 'Сре',
      Thu: 'Чет',
      Fri: 'Пет'
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflow: 'auto',
        height: '100%',
        padding: 24
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        marginBottom: 16
      }
    }, GF_T[lang].timeline), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        overflow: 'hidden',
        minWidth: 760
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '160px repeat(5, 1fr)',
        borderBottom: '1px solid var(--line)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '12px 16px',
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '.03em'
      }
    }, GF_T[lang].depts), days.map(d => /*#__PURE__*/React.createElement("div", {
      key: d,
      style: {
        padding: '12px 8px',
        textAlign: 'center',
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        borderLeft: '1px solid var(--line)'
      }
    }, lang === 'mk' ? daysMk[d] : d))), GF_DEPARTMENTS.map(d => /*#__PURE__*/React.createElement("div", {
      key: d.id,
      style: {
        display: 'grid',
        gridTemplateColumns: '160px repeat(5, 1fr)',
        borderBottom: '1px solid var(--line-2)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 'var(--fs-13)',
        fontWeight: 700
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 9,
        height: 9,
        borderRadius: 999,
        background: d.color,
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, lang === 'mk' ? d.mk : d.name)), days.map(day => {
      const items = tasks.filter(x => x.dept === d.id && x.day === day);
      return /*#__PURE__*/React.createElement("div", {
        key: day,
        style: {
          borderLeft: '1px solid var(--line-2)',
          padding: 6,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          minHeight: 52
        }
      }, items.map(x => /*#__PURE__*/React.createElement("div", {
        key: x.id,
        title: x.title,
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          padding: '4px 7px',
          borderRadius: 6,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          background: DS2.STATUS[x.status].bg,
          color: DS2.STATUS[x.status].fg
        }
      }, x.title)));
    })))));
  }
  function Coordination({
    lang,
    handoffs,
    onAdvance
  }) {
    const t = GF_T[lang];
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        marginBottom: 4
      }
    }, t.coord), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: '0 0 18px',
        fontSize: 'var(--fs-13)',
        color: 'var(--text-body)',
        fontWeight: 500
      }
    }, lang === 'mk' ? 'Предавање меѓу оддели — што чека кого. Кликни за да напредуваш статус.' : 'Cross-department handoffs — what\u2019s waiting on whom. Click a status to advance it.'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, handoffs.map((h, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        padding: '14px 16px',
        boxShadow: 'var(--sh-1)',
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-body)'
      }
    }, /*#__PURE__*/React.createElement("span", null, h.from), I2('ArrowRight', 15), /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-strong)'
      }
    }, h.to)), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 220,
        fontSize: 'var(--fs-13)',
        fontWeight: 600
      }
    }, h.item), /*#__PURE__*/React.createElement(Avatar, {
      name: h.by,
      size: 26
    }), /*#__PURE__*/React.createElement(DS2.StatusPill, {
      status: h.status,
      lang: lang,
      onClick: () => onAdvance(i)
    })))));
  }
  function AIReport({
    lang,
    tasks,
    onToast
  }) {
    const L = lang === 'mk';
    const STATUS_LABEL = window.STATUS_LABEL,
      STATUS_COLOR = window.STATUS_COLOR;
    const T = tasks || GF_TASKS;
    const statuses = ['done', 'working', 'review', 'stuck', 'postponed', 'pending'];
    const statusCount = s => T.filter(x => x.status === s).length;
    const total = T.length || 1;
    const donePct = Math.round(statusCount('done') / total * 100);
    // weekday activity (sum of session hours by first day)
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    const dayMk = {
      Mon: 'Пон',
      Tue: 'Вто',
      Wed: 'Сре',
      Thu: 'Чет',
      Fri: 'Пет'
    };
    const dayHours = days.map(d => T.filter(x => (x.days || [x.day]).includes(d)).reduce((s, x) => s + (x.sessionHours || 1.5), 0));
    const maxH = Math.max(...dayHours, 1);
    const busiest = days[dayHours.indexOf(maxH)];
    // dept breakdown
    const deptRows = GF_DEPARTMENTS.map(d => ({
      d,
      n: T.filter(x => x.dept === d.id).length
    })).filter(o => o.n > 0).sort((a, b) => b.n - a.n);
    const maxDept = Math.max(...deptRows.map(o => o.n), 1);
    const [mode, setMode] = React.useState('report');
    const [submitted, setSubmitted] = React.useState(false);
    const isPlan = mode === 'plan';
    const download = (filename, text, mime) => {
      const blob = new Blob([text], {
        type: mime + ';charset=utf-8'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (onToast) onToast('success', (L ? 'Извезено: ' : 'Exported ') + filename, 'Download');
    };
    const exportJSON = () => download('weekly-' + mode + '.json', JSON.stringify({
      generated: new Date().toISOString(),
      mode,
      summary: statuses.map(s => ({
        status: s,
        count: statusCount(s)
      })),
      tasks: T
    }, null, 2), 'application/json');
    const exportCSV = () => {
      const head = ['id', 'title', 'dept', 'owner', 'status', 'priority', 'due', 'ref', 'hours'];
      const rows = T.map(x => [x.id, x.title, x.dept, x.owner, x.status, x.pr || x.priority, x.due || '', x.ref || x.refCode || '', x.sessionHours || ''].map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
      download('weekly-' + mode + '.csv', '\uFEFF' + [head.join(','), ...rows].join('\r\n'), 'text/csv');
    };
    const exportMD = () => {
      const lines = ['# GrowFlow Weekly ' + (isPlan ? 'Plan' : 'Report'), '', '_Generated ' + new Date().toLocaleDateString() + ' — informational draft, not an official record_', '', '## Summary', ...statuses.map(s => '- **' + STATUS_LABEL(lang, s) + '**: ' + statusCount(s)), '', '## Tasks'];
      T.forEach(x => lines.push('- `' + x.id + '` ' + x.title + ' — ' + STATUS_LABEL(lang, x.status) + (x.ref ? ' (' + x.ref + ')' : '')));
      download('weekly-' + mode + '.md', lines.join('\n'), 'text/markdown');
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 820
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 16,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--violet-soft)',
        color: 'var(--violet-700)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('Sparkles', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800
      }
    }, isPlan ? L ? 'Неделен план' : 'Weekly Plan' : L ? 'Неделен извештај' : 'Weekly Report'), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(Segmented, {
      options: [{
        value: 'report',
        label: L ? 'Извештај' : 'Report'
      }, {
        value: 'plan',
        label: L ? 'План' : 'Plan'
      }],
      value: mode,
      onChange: v => {
        setMode(v);
        setSubmitted(false);
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 16,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, L ? 'Извези:' : 'Export:'), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: exportJSON
    }, I2('FileJson', 14), "\xA0JSON"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: exportCSV
    }, I2('Sheet', 14), "\xA0CSV"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: exportMD
    }, I2('FileText', 14), "\xA0Markdown"), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), submitted ? /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--st-done)',
        background: 'var(--st-done-soft)',
        borderRadius: 999,
        padding: '8px 14px'
      }
    }, I2('CheckCheck', 15), isPlan ? L ? 'Планот е поднесен' : 'Plan submitted' : L ? 'Извештајот е поднесен' : 'Report submitted') : /*#__PURE__*/React.createElement(Button, {
      onClick: () => {
        setSubmitted(true);
        if (onToast) onToast('success', isPlan ? L ? 'Планот е поднесен' : 'Plan submitted' : L ? 'Извештајот е поднесен' : 'Report submitted', 'CheckCheck');
      }
    }, I2('Send', 15), "\xA0", L ? 'Поднеси нацрт' : 'Submit draft')), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement(KpiTile, {
      value: donePct + '%',
      label: GF_T[lang].completion,
      tone: "green",
      icon: I2('TrendingUp', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: total,
      label: GF_T[lang].total,
      icon: I2('ListChecks', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: statusCount('stuck'),
      label: GF_T[lang].stuck,
      tone: "red",
      icon: I2('OctagonAlert', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: L ? dayMk[busiest] : busiest,
      label: GF_T[lang].busiest,
      tone: "violet",
      icon: I2('CalendarClock', 16)
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        padding: 18,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        marginBottom: 12
      }
    }, L ? 'Распределба по статус' : 'Status distribution'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        height: 16,
        borderRadius: 999,
        overflow: 'hidden',
        background: 'var(--surface-3)'
      }
    }, statuses.map(s => {
      const n = statusCount(s);
      return n ? /*#__PURE__*/React.createElement("div", {
        key: s,
        title: STATUS_LABEL(lang, s) + ': ' + n,
        style: {
          width: n / total * 100 + '%',
          background: STATUS_COLOR(s)
        }
      }) : null;
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 14,
        marginTop: 12
      }
    }, statuses.filter(statusCount).map(s => /*#__PURE__*/React.createElement("div", {
      key: s,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-body)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 9,
        height: 9,
        borderRadius: 999,
        background: STATUS_COLOR(s)
      }
    }), STATUS_LABEL(lang, s), " ", /*#__PURE__*/React.createElement("b", {
      style: {
        color: 'var(--text-strong)'
      }
    }, statusCount(s)))))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 14,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        padding: 18
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        marginBottom: 14
      }
    }, L ? 'Активност по ден' : 'Activity by day'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'flex-end',
        gap: 10,
        height: 120
      }
    }, days.map((d, i) => /*#__PURE__*/React.createElement("div", {
      key: d,
      style: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, dayHours[i].toFixed(0), "h"), /*#__PURE__*/React.createElement("div", {
      style: {
        width: '100%',
        height: dayHours[i] / maxH * 88 + 8,
        background: d === busiest ? 'var(--primary)' : 'var(--primary-soft)',
        borderRadius: '6px 6px 0 0',
        transition: 'height var(--dur-ui)'
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-body)'
      }
    }, L ? dayMk[d] : d))))), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        padding: 18
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        marginBottom: 14
      }
    }, L ? 'По оддел' : 'By department'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 9
      }
    }, deptRows.slice(0, 6).map(({
      d,
      n
    }) => /*#__PURE__*/React.createElement("div", {
      key: d.id,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 9
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 8,
        height: 8,
        borderRadius: 999,
        background: d.color,
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        width: 110,
        flexShrink: 0,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, L ? d.mk : d.name), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        height: 7,
        borderRadius: 999,
        background: 'var(--surface-3)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: n / maxDept * 100 + '%',
        height: '100%',
        background: d.color,
        borderRadius: 999
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-11)',
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        width: 16,
        textAlign: 'right'
      }
    }, n)))))), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'linear-gradient(135deg, var(--violet-soft), var(--surface))',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        padding: 20
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--violet-700)'
      }
    }, I2('Sparkles', 16)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 800
      }
    }, L ? 'AI увиди' : 'AI insights')), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: '0 0 14px',
        fontSize: 'var(--fs-14)',
        lineHeight: 1.6,
        color: 'var(--text-strong)'
      }
    }, L ? `Тимот заврши ${donePct}% од задачите оваа недела. Главниот ризик е блокадата во QC — примерокот чека вердикт за QC вода и е задоцнет.` : `The team completed ${donePct}% of tasks this week. The main risk is the QC blocker — post-curing sampling is waiting on a QC water verdict and is now overdue.`), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        marginBottom: 6
      }
    }, L ? 'Препораки' : 'Recommendations'), [L ? 'Забрзај го вердиктот на QC водата за F27' : 'Expedite the QC water verdict for batch F27', L ? 'Прераспредели 2 задачи од Blagoj кон Ana' : 'Rebalance 2 tasks from Blagoj to Ana', L ? 'Планирај го QP прегледот за F25 за петок' : 'Schedule the F25 QP review for Friday'].map((r, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        gap: 8,
        alignItems: 'center',
        padding: '7px 0',
        borderTop: i > 0 ? '1px dashed var(--line)' : 'none',
        fontSize: 'var(--fs-13)',
        fontWeight: 600
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--violet-700)'
      }
    }, I2('ArrowRight', 14)), r))));
  }
  function Settings({
    lang,
    setLang,
    theme,
    setTheme,
    notifs,
    onToggleNotif,
    aiBackend,
    setAiBackend,
    currentUser,
    setCurrentUser,
    myPerms
  }) {
    const t = GF_T[lang];
    const L = lang === 'mk';
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 620,
        display: 'flex',
        flexDirection: 'column',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        marginBottom: 2
      }
    }, t.settings), /*#__PURE__*/React.createElement(Panel2, {
      title: lang === 'mk' ? 'Претставување' : 'Appearance'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 700,
        fontSize: 'var(--fs-13)'
      }
    }, lang === 'mk' ? 'Контролна соба (темна тема)' : 'Control-room theme'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)'
      }
    }, lang === 'mk' ? 'Темна површина за ноќни смени' : 'Dark surface for night shifts')), /*#__PURE__*/React.createElement(Switch, {
      checked: theme === 'dark',
      onChange: v => setTheme(v ? 'dark' : 'light')
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 700,
        fontSize: 'var(--fs-13)'
      }
    }, lang === 'mk' ? 'Јазик' : 'Language'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)'
      }
    }, "English / \u041C\u0430\u043A\u0435\u0434\u043E\u043D\u0441\u043A\u0438")), /*#__PURE__*/React.createElement(Segmented, {
      options: [{
        value: 'en',
        label: 'EN'
      }, {
        value: 'mk',
        label: 'МК'
      }],
      value: lang,
      onChange: setLang
    }))), /*#__PURE__*/React.createElement(Panel2, {
      title: lang === 'mk' ? 'Известувања' : 'Notifications'
    }, Object.keys(notifs).map((key, i) => /*#__PURE__*/React.createElement("div", {
      key: key,
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 0',
        borderTop: i > 0 ? '1px solid var(--line-2)' : 'none'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600
      }
    }, lang === 'mk' ? {
      stuck: 'Блокирани задачи',
      report: 'Неделен AI извештај',
      handoff: 'Предавања меѓу оддели'
    }[key] : {
      stuck: 'Stuck tasks',
      report: 'Weekly AI report',
      handoff: 'Cross-department handoffs'
    }[key]), /*#__PURE__*/React.createElement(Switch, {
      checked: notifs[key],
      onChange: () => onToggleNotif(key)
    })))), /*#__PURE__*/React.createElement(Panel2, {
      title: lang === 'mk' ? 'Асистент' : 'Assistant'
    }, /*#__PURE__*/React.createElement(Field, {
      label: lang === 'mk' ? 'AI позадина' : 'AI backend'
    }, /*#__PURE__*/React.createElement(PopSelect, {
      value: aiBackend,
      onChange: setAiBackend,
      title: lang === 'mk' ? 'AI позадина' : 'AI backend',
      options: [{
        value: 'claude',
        label: 'Claude'
      }, {
        value: 'gpt4',
        label: 'GPT-4'
      }, {
        value: 'local',
        label: lang === 'mk' ? 'Локално (офлајн)' : 'Local (offline)'
      }]
    }))), /*#__PURE__*/React.createElement(Panel2, {
      title: L ? 'Улога и дозволи' : 'Role & permissions'
    }, /*#__PURE__*/React.createElement(Field, {
      label: L ? 'Најавен како' : 'Signed in as'
    }, /*#__PURE__*/React.createElement(PopSelect, {
      value: currentUser,
      onChange: setCurrentUser,
      title: L ? 'Најавен како' : 'Signed in as',
      options: GF_PEOPLE.map(p => ({
        value: p.id,
        label: p.name,
        sub: GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.role,
        color: p.color
      }))
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        margin: '4px 0 8px'
      }
    }, L ? 'Дозволи за оваа улога' : 'Permissions for this role'), myPerms && [[L ? 'Создавање задачи' : 'Create tasks', myPerms.create], [L ? 'Уреди сите задачи' : 'Edit any task', myPerms.editAny], [L ? 'Избриши сите задачи' : 'Delete any task', myPerms.deleteAny], [L ? 'Промени статус на сите' : 'Change any status', myPerms.status === 'any'], [L ? 'Промени статус (само свои)' : 'Change status (own only)', myPerms.status === 'own'], [L ? 'Преглед на тим' : 'View team', myPerms.team]].map(([label, on]) => /*#__PURE__*/React.createElement("div", {
      key: label,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '6px 0',
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: on ? 'var(--text-strong)' : 'var(--text-faint)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: on ? 'var(--st-done)' : 'var(--text-faint)',
        display: 'inline-flex'
      }
    }, I2(on ? 'Check' : 'Minus', 15)), label))));
  }
  function AuditTrail({
    lang
  }) {
    const L = lang === 'mk';
    const actions = {
      create: {
        en: 'created task',
        mk: 'создаде задача',
        icon: 'Plus',
        color: 'var(--st-done)'
      },
      status: {
        en: 'changed status',
        mk: 'смени статус',
        icon: 'RefreshCw',
        color: 'var(--st-working)'
      },
      assign: {
        en: 'assigned',
        mk: 'додели',
        icon: 'UserPlus',
        color: 'var(--st-review)'
      },
      comment: {
        en: 'commented on',
        mk: 'коментираше на',
        icon: 'MessageSquare',
        color: '#7A5BE0'
      },
      release: {
        en: 'released batch',
        mk: 'ослободи серија',
        icon: 'ShieldCheck',
        color: 'var(--pr-critical)'
      },
      edit: {
        en: 'edited',
        mk: 'уреди',
        icon: 'Pencil',
        color: 'var(--text-muted)'
      }
    };
    const log = [{
      who: 'elena',
      act: 'release',
      obj: 'Batch F25',
      t: '14:02',
      d: L ? 'Денес' : 'Today'
    }, {
      who: 'blagoj',
      act: 'status',
      obj: 'T-4KZ9 → Working',
      t: '13:41',
      d: L ? 'Денес' : 'Today'
    }, {
      who: 'ana',
      act: 'comment',
      obj: 'T-1H7C',
      t: '11:20',
      d: L ? 'Денес' : 'Today'
    }, {
      who: 'ivo',
      act: 'status',
      obj: 'T-2M1P → Stuck',
      t: '09:58',
      d: L ? 'Денес' : 'Today'
    }, {
      who: 'marko',
      act: 'assign',
      obj: 'Sara M → T-8Q4A',
      t: '17:30',
      d: L ? 'Вчера' : 'Yesterday'
    }, {
      who: 'goran',
      act: 'create',
      obj: 'T-3T7L Mother-plant check',
      t: '16:04',
      d: L ? 'Вчера' : 'Yesterday'
    }, {
      who: 'sara',
      act: 'edit',
      obj: 'T-8Q4A transport SOP',
      t: '15:12',
      d: L ? 'Вчера' : 'Yesterday'
    }, {
      who: 'blagoj',
      act: 'create',
      obj: 'T-4KZ9 HPLC validation',
      t: '08:30',
      d: L ? 'Вчера' : 'Yesterday'
    }];
    let lastDay = null;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 720
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 18
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800
      }
    }, L ? 'Дневник на активност' : 'Audit trail'), /*#__PURE__*/React.createElement(Badge, {
      tone: "neutral"
    }, log.length)), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'relative'
      }
    }, log.map((e, i) => {
      const a = actions[e.act];
      const p = GF_PERSON(e.who);
      const showDay = e.d !== lastDay;
      lastDay = e.d;
      return /*#__PURE__*/React.createElement(React.Fragment, {
        key: i
      }, showDay && /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 800,
          letterSpacing: '.04em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          margin: (i ? '18px' : '0') + ' 0 10px'
        }
      }, e.d), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 12,
          alignItems: 'flex-start',
          padding: '8px 0'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 32,
          height: 32,
          borderRadius: 999,
          background: 'var(--surface-2)',
          border: '1px solid var(--line)',
          color: a.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0
        }
      }, I2(a.icon, 15)), /*#__PURE__*/React.createElement("div", {
        style: {
          flex: 1,
          minWidth: 0
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-13)',
          color: 'var(--text-strong)',
          lineHeight: 1.5
        }
      }, /*#__PURE__*/React.createElement("b", null, p.name), " ", /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--text-body)'
        }
      }, a[lang]), " ", /*#__PURE__*/React.createElement("b", {
        style: {
          color: a.color
        }
      }, e.obj))), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-11)',
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: 'var(--text-muted)',
          flexShrink: 0
        }
      }, e.t)));
    })));
  }
  function ImportView({
    lang,
    onToast
  }) {
    const L = lang === 'mk';
    const [rows, setRows] = React.useState([{
      title: 'Calibrate RH sensor — Flower room 3',
      dept: 'flower',
      type: 'other',
      pri: 'high',
      ok: true
    }, {
      title: 'CoA compile — Batch F25',
      dept: 'qa',
      type: 'document',
      pri: 'critical',
      ok: true
    }, {
      title: 'Restock nutrient A/B — Veg',
      dept: 'irr',
      type: 'other',
      pri: 'medium',
      ok: true
    }, {
      title: '',
      dept: 'prod',
      type: 'admin',
      pri: 'low',
      ok: false
    }, {
      title: 'Line clearance — Packaging',
      dept: 'prod',
      type: 'sop',
      pri: 'medium',
      ok: true
    }]);
    const valid = rows.filter(r => r.ok).length;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 820
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800
      }
    }, L ? 'Увоз на задачи' : 'Import tasks')), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: '0 0 16px',
        fontSize: 'var(--fs-13)',
        color: 'var(--text-body)',
        fontWeight: 500
      }
    }, L ? 'Залепи CSV или пушти датотека — редовите се распознаваат автоматски.' : 'Paste CSV or drop a file — rows are parsed and validated automatically.'), /*#__PURE__*/React.createElement("div", {
      style: {
        border: '2px dashed var(--line)',
        borderRadius: 'var(--r-lg)',
        padding: '28px 20px',
        textAlign: 'center',
        background: 'var(--surface-2)',
        marginBottom: 18,
        cursor: 'pointer'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--primary)',
        display: 'inline-flex',
        marginBottom: 8
      }
    }, I2('Upload', 26)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-14)',
        fontWeight: 700
      }
    }, L ? 'Пушти CSV тука' : 'Drop a CSV here'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)',
        fontWeight: 600,
        marginTop: 3
      }
    }, L ? 'или кликни за да прелистиш' : 'or click to browse — title, dept, type, priority')), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '24px 1fr 130px 100px 90px',
        gap: 10,
        padding: '10px 14px',
        borderBottom: '1px solid var(--line)',
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)'
      }
    }, /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null, L ? 'Наслов' : 'Title'), /*#__PURE__*/React.createElement("span", null, L ? 'Оддел' : 'Dept'), /*#__PURE__*/React.createElement("span", null, L ? 'Тип' : 'Type'), /*#__PURE__*/React.createElement("span", null, L ? 'Приоритет' : 'Priority')), rows.map((r, i) => {
      const d = GF_DEPARTMENTS.find(x => x.id === r.dept) || {};
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          display: 'grid',
          gridTemplateColumns: '24px 1fr 130px 100px 90px',
          gap: 10,
          padding: '11px 14px',
          borderBottom: i < rows.length - 1 ? '1px solid var(--line-2)' : 'none',
          alignItems: 'center',
          background: r.ok ? 'transparent' : 'var(--st-stuck-soft)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          color: r.ok ? 'var(--st-done)' : 'var(--st-stuck)',
          display: 'inline-flex'
        }
      }, I2(r.ok ? 'CircleCheck' : 'CircleAlert', 16)), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 600,
          color: r.ok ? 'var(--text-strong)' : 'var(--st-stuck)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap'
        }
      }, r.title || (L ? '⚠ Недостига наслов' : '⚠ Missing title')), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 'var(--fs-12)',
          fontWeight: 600
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 8,
          height: 8,
          borderRadius: 999,
          background: d.color
        }
      }), L ? d.mk : d.name), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 700,
          color: 'var(--text-body)'
        }
      }, GF_TASK_TYPES[r.type] ? GF_TASK_TYPES[r.type][lang] : r.type), /*#__PURE__*/React.createElement(PriorityTag, {
        priority: r.pri
      }));
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginTop: 16
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 600,
        color: 'var(--text-body)'
      }
    }, valid, "/", rows.length, " ", L ? 'валидни редови' : 'valid rows'), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => setRows(rs => rs.filter(r => r.ok))
    }, L ? 'Отстрани неважечки' : 'Drop invalid'), /*#__PURE__*/React.createElement(Button, {
      onClick: () => onToast && onToast('success', `${valid} ${L ? 'задачи увезени' : 'tasks imported'}`, 'Check')
    }, L ? `Увези ${valid}` : `Import ${valid}`)));
  }

  // ═══════════════════════════ Executive Analytics ═══════════════════════════
  function Analytics({
    lang
  }) {
    const L = lang === 'mk';
    const eyebrow = {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--text-muted)',
      marginBottom: 12
    };
    const card = {
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-1)',
      padding: 18
    };
    const T = GF_TASKS;
    const done = arr => arr.filter(x => x.status === 'done').length;
    // per-department completion
    const deptRows = GF_DEPARTMENTS.map(d => {
      const dt = T.filter(x => x.dept === d.id);
      const heads = GF_PEOPLE.filter(p => p.dept === d.id).length;
      return {
        d,
        n: dt.length,
        done: done(dt),
        heads
      };
    }).filter(o => o.n > 0).sort((a, b) => b.n - a.n);
    // per-person workload
    const people = GF_PEOPLE.map(p => {
      const owned = T.filter(x => x.owner === p.id);
      return {
        p,
        load: owned.length,
        done: done(owned)
      };
    }).filter(o => o.load > 0).sort((a, b) => b.load - a.load);
    const maxLoad = Math.max(...people.map(o => o.load), 1);
    const total = T.length || 1;
    const donePct = Math.round(done(T) / total * 100);
    // report submission tracking (mock per-dept state)
    const subs = ['done', 'done', 'draft', 'due', 'done', 'due'];
    const subMeta = {
      done: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Submitted',
        mk: 'Поднесено'
      },
      draft: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'Draft',
        mk: 'Нацрт'
      },
      due: {
        c: 'var(--text-muted)',
        bg: 'var(--surface-3)',
        en: 'Not started',
        mk: 'Не започнато'
      }
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 960
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--blue-soft)',
        color: 'var(--blue)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('ChartPie', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        lineHeight: 1.15,
        whiteSpace: 'nowrap'
      }
    }, L ? 'Извршна аналитика' : 'Executive Analytics'), /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 'auto',
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        color: 'var(--text-muted)',
        whiteSpace: 'nowrap'
      }
    }, L ? 'Оваа работна недела · Пет–Чет' : 'This work-week · Fri–Thu')), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement(KpiTile, {
      value: donePct + '%',
      label: L ? 'Завршеност' : 'Completion',
      tone: "green",
      icon: I2('TrendingUp', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: deptRows.length,
      label: L ? 'Активни оддели' : 'Active depts',
      tone: "blue",
      icon: I2('Building2', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: GF_PEOPLE.length,
      label: L ? 'Вкупно луѓе' : 'Headcount',
      icon: I2('Users', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: subs.filter(s => s === 'done').length + '/' + subs.length,
      label: L ? 'Извештаи поднесени' : 'Reports in',
      tone: "violet",
      icon: I2('FileCheck2', 16)
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1.1fr 1fr',
        gap: 14,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Завршеност по оддел' : 'Completion by department'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }
    }, deptRows.map(({
      d,
      n,
      done,
      heads
    }) => {
      const pct = Math.round(done / n * 100);
      return /*#__PURE__*/React.createElement("div", {
        key: d.id
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 5
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 8,
          height: 8,
          borderRadius: 999,
          background: d.color,
          flexShrink: 0
        }
      }), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-12)',
          fontWeight: 700,
          flex: 1
        }
      }, L ? d.mk : d.name), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 600,
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 3
        }
      }, I2('User', 11), heads), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-11)',
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: 'var(--text-strong)',
          width: 34,
          textAlign: 'right'
        }
      }, pct, "%")), /*#__PURE__*/React.createElement("div", {
        style: {
          height: 8,
          borderRadius: 999,
          background: 'var(--surface-3)',
          overflow: 'hidden'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: pct + '%',
          height: '100%',
          background: d.color,
          borderRadius: 999,
          transition: 'width var(--dur-ui)'
        }
      })));
    }))), /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Оптоварување по личност' : 'Workload by person'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, people.slice(0, 7).map(({
      p,
      load,
      done
    }) => /*#__PURE__*/React.createElement("div", {
      key: p.id,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: p.name,
      size: 28,
      color: p.color
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        width: 96,
        flexShrink: 0,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, p.name), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        height: 7,
        borderRadius: 999,
        background: 'var(--surface-3)',
        overflow: 'hidden',
        position: 'relative'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: load / maxLoad * 100 + '%',
        height: '100%',
        background: p.color,
        borderRadius: 999
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-11)',
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        width: 40,
        textAlign: 'right'
      }
    }, done, "/", load)))))), /*#__PURE__*/React.createElement("div", {
      style: {
        ...card,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Следење на неделни извештаи' : 'Weekly report submission'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10
      }
    }, deptRows.slice(0, 6).map(({
      d
    }, i) => {
      const st = subMeta[subs[i]];
      return /*#__PURE__*/React.createElement("div", {
        key: d.id,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          padding: '10px 12px',
          border: '1px solid var(--line)',
          borderRadius: 'var(--r-md)',
          background: 'var(--surface-2)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 8,
          height: 8,
          borderRadius: 999,
          background: d.color,
          flexShrink: 0
        }
      }), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-12)',
          fontWeight: 600,
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap'
        }
      }, L ? d.mk : d.name), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          color: st.c,
          background: st.bg,
          padding: '3px 8px',
          borderRadius: 999
        }
      }, L ? st.mk : st.en));
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'linear-gradient(135deg, var(--blue-soft), var(--surface))',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--sh-1)',
        padding: 20
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--violet-700)'
      }
    }, I2('Sparkles', 16)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-13)',
        fontWeight: 800
      }
    }, L ? 'AI извршно резиме' : 'AI executive summary'), /*#__PURE__*/React.createElement(Badge, {
      tone: "neutral"
    }, L ? 'Информативно' : 'Informational')), /*#__PURE__*/React.createElement("p", {
      style: {
        margin: 0,
        fontSize: 'var(--fs-14)',
        lineHeight: 1.6,
        color: 'var(--text-strong)'
      }
    }, L ? `Производството е на ${donePct}% завршеност оваа недела. QA и Flower носат најголемо оптоварување; двата оддела сè уште имаат неподнесени извештаи. Главен ризик: блокирано земање мостри на F27 што чека вердикт за QC вода.` : `Production sits at ${donePct}% completion this week. QA and Flower carry the heaviest load; both still have reports outstanding. Top risk: F27 sampling is blocked pending a QC water verdict.`)));
  }

  // ═══════════════════════════ Access Management ═══════════════════════════
  function Access({
    lang,
    onToast
  }) {
    const L = lang === 'mk';
    const eyebrow = {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--text-muted)',
      marginBottom: 12
    };
    const card = {
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-1)',
      padding: 18
    };
    // account state per person: active | firstlogin | locked
    const seed = {
      elena: 'active',
      ana: 'active',
      marko: 'firstlogin',
      ivo: 'active',
      sara: 'locked',
      goran: 'firstlogin',
      blagoj: 'active',
      kire: 'active'
    };
    const [rows, setRows] = React.useState(() => GF_PEOPLE.map(p => ({
      p,
      state: seed[p.id] || 'active'
    })));
    const [otp, setOtp] = React.useState(null); // {name, code}
    const stMeta = {
      active: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Active',
        mk: 'Активен',
        icon: 'CircleCheck'
      },
      firstlogin: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'First-login pending',
        mk: 'Чека прв влез',
        icon: 'KeyRound'
      },
      locked: {
        c: 'var(--red)',
        bg: 'var(--red-soft)',
        en: 'Locked',
        mk: 'Заклучен',
        icon: 'Lock'
      }
    };
    const genCode = () => Array.from({
      length: 3
    }, () => Math.random().toString(36).slice(2, 6).toUpperCase()).join('-');
    const provision = r => {
      const code = genCode();
      setOtp({
        name: r.p.name,
        code,
        kind: 'reset'
      });
      setRows(rs => rs.map(x => x.p.id === r.p.id ? {
        ...x,
        state: 'firstlogin'
      } : x));
      onToast && onToast('info', (L ? 'Издадена привремена лозинка за ' : 'Temp password issued for ') + r.p.name, 'KeyRound');
    };
    const unlock = r => {
      setRows(rs => rs.map(x => x.p.id === r.p.id ? {
        ...x,
        state: 'active'
      } : x));
      onToast && onToast('success', r.p.name + (L ? ' е отклучен' : ' unlocked'), 'LockOpen');
    };
    const roleColor = {
      admin: 'var(--red)',
      ceo: 'var(--violet-700)',
      executive: 'var(--violet-700)',
      qp: 'var(--blue)',
      qa: 'var(--blue)',
      hod: 'var(--green-600)',
      operator: 'var(--text-muted)',
      viewer: 'var(--text-muted)'
    };
    const counts = {
      active: rows.filter(r => r.state === 'active').length,
      firstlogin: rows.filter(r => r.state === 'firstlogin').length,
      locked: rows.filter(r => r.state === 'locked').length
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 960
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--red-soft)',
        color: 'var(--red)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('ShieldCheck', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        lineHeight: 1.15,
        whiteSpace: 'nowrap'
      }
    }, L ? 'Пристап и сметки' : 'Access & Accounts'), /*#__PURE__*/React.createElement(Badge, {
      tone: "red"
    }, L ? 'Само админ' : 'Admin only')), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        color: 'var(--text-body)',
        marginBottom: 16,
        maxWidth: 620,
        lineHeight: 1.55
      }
    }, L ? 'Нема самопријавување — сметките ги обезбедува админ со еднократна привремена лозинка. Корисникот мора да ја смени лозинката при првиот влез.' : 'No self-signup — accounts are provisioned by an admin with a one-time temporary password. Users must change it on first login.'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement(KpiTile, {
      value: counts.active,
      label: L ? 'Активни' : 'Active',
      tone: "green",
      icon: I2('CircleCheck', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: counts.firstlogin,
      label: L ? 'Чекаат прв влез' : 'First-login pending',
      tone: "amber",
      icon: I2('KeyRound', 16)
    }), /*#__PURE__*/React.createElement(KpiTile, {
      value: counts.locked,
      label: L ? 'Заклучени' : 'Locked',
      tone: "red",
      icon: I2('Lock', 16)
    })), otp && /*#__PURE__*/React.createElement("div", {
      style: {
        ...card,
        border: '1px solid var(--amber)',
        background: 'var(--amber-soft)',
        marginBottom: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--amber)'
      }
    }, I2('KeyRound', 22)), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, L ? 'Еднократна привремена лозинка за ' : 'One-time temporary password for ', otp.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        color: 'var(--text-body)',
        fontWeight: 600
      }
    }, L ? 'Прикажана само еднаш — копирајте и предајте безбедно.' : 'Shown once — copy and hand over securely.')), /*#__PURE__*/React.createElement("code", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-16)',
        fontWeight: 700,
        letterSpacing: '.06em',
        background: 'var(--surface)',
        border: '1px dashed var(--amber)',
        borderRadius: 'var(--r-sm)',
        padding: '8px 14px',
        color: 'var(--text-strong)'
      }
    }, otp.code), /*#__PURE__*/React.createElement(IconButton, {
      icon: I2('X', 16),
      onClick: () => setOtp(null)
    })), /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Директориум на корисници' : 'User directory'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column'
      }
    }, rows.map((r, i) => {
      const st = stMeta[r.state];
      const roleL = GF_ROLES[r.p.role] ? GF_ROLES[r.p.role][lang] : r.p.roleLabel;
      return /*#__PURE__*/React.createElement("div", {
        key: r.p.id,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '11px 4px',
          borderTop: i ? '1px solid var(--line)' : 'none'
        }
      }, /*#__PURE__*/React.createElement(Avatar, {
        name: r.p.name,
        size: 34,
        color: r.p.color
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          minWidth: 0,
          flex: 1
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 700
        }
      }, r.p.name), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 600,
          color: roleColor[r.p.role] || 'var(--text-muted)'
        }
      }, roleL)), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 600,
          color: 'var(--text-muted)',
          width: 120,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap'
        }
      }, (() => {
        const d = GF_DEPARTMENTS.find(x => x.id === r.p.dept);
        return d ? L ? d.mk : d.name : L ? 'Меѓу-оддел' : 'Cross-dept';
      })()), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          color: st.c,
          background: st.bg,
          padding: '4px 9px',
          borderRadius: 999,
          width: 148,
          justifyContent: 'center'
        }
      }, I2(st.icon, 12), L ? st.mk : st.en), /*#__PURE__*/React.createElement("div", {
        style: {
          width: 120,
          display: 'flex',
          justifyContent: 'flex-end'
        }
      }, r.state === 'locked' ? /*#__PURE__*/React.createElement(Button, {
        size: "sm",
        variant: "ghost",
        onClick: () => unlock(r)
      }, L ? 'Отклучи' : 'Unlock') : /*#__PURE__*/React.createElement(Button, {
        size: "sm",
        variant: "ghost",
        onClick: () => provision(r)
      }, L ? 'Ресетирај' : 'Reset')));
    }))));
  }

  // ═══════════════════════════ Governance / Change control ═══════════════════════════
  function Governance({
    lang,
    onToast
  }) {
    const L = lang === 'mk';
    const eyebrow = {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--text-muted)',
      marginBottom: 12
    };
    const card = {
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-1)',
      padding: 18
    };
    // Field registry: core columns + long-tail JSON attributes
    const coreFields = [{
      k: 'title',
      t: 'text',
      en: 'Task title',
      mk: 'Наслов'
    }, {
      k: 'status',
      t: 'enum',
      en: 'Status',
      mk: 'Статус'
    }, {
      k: 'priority',
      t: 'enum',
      en: 'Priority',
      mk: 'Приоритет'
    }, {
      k: 'owner',
      t: 'ref',
      en: 'Accountable owner',
      mk: 'Одговорен носител'
    }, {
      k: 'dept',
      t: 'ref',
      en: 'Department',
      mk: 'Оддел'
    }, {
      k: 'due',
      t: 'date',
      en: 'Due date',
      mk: 'Рок'
    }];
    const extFields = [{
      k: 'batch',
      t: 'json',
      en: 'Batch / lot',
      mk: 'Серија / лот'
    }, {
      k: 'room',
      t: 'json',
      en: 'Room / location',
      mk: 'Соба / локација'
    }, {
      k: 'sopRef',
      t: 'json',
      en: 'SOP pointer',
      mk: 'СОП покажувач'
    }];
    const typeMeta = {
      text: 'var(--text-muted)',
      enum: 'var(--violet-700)',
      ref: 'var(--blue)',
      date: 'var(--green-600)',
      json: 'var(--amber)'
    };
    const [props, setProps] = React.useState([{
      id: 1,
      title: L ? 'Додај поле „Проценета траба (часови)“' : 'Add "Estimated effort (hours)" field',
      by: 'schema advisor',
      kind: L ? 'Ново поле' : 'New field',
      state: 'pending',
      rationale: L ? 'Три оддели рачно ги следат часовите во белешки.' : 'Three departments track hours manually in notes.'
    }, {
      id: 2,
      title: L ? 'Дозволи статус „Блокирано однадвор“' : 'Allow "Blocked-external" status',
      by: 'compliance',
      kind: L ? 'Промена на работек' : 'Workflow change',
      state: 'approved',
      rationale: L ? 'Ги раздвојува внатрешните блокади од оние кај добавувачите.' : 'Separates internal blockers from supplier-side ones.'
    }, {
      id: 3,
      title: L ? 'Спои „soba“ и „location“ во едно поле' : 'Merge "soba" and "location" into one field',
      by: 'analytics',
      kind: L ? 'Миграција' : 'Migration',
      state: 'applied',
      rationale: L ? 'Дупликат атрибути од две-јазичен внес.' : 'Duplicate attributes from bilingual entry.'
    }, {
      id: 4,
      title: L ? 'Задолжителна причина при откажување' : 'Require reason when declining assignment',
      by: 'weekly coordinator',
      kind: L ? 'Валидација' : 'Validation',
      state: 'rejected',
      rationale: L ? 'Веќе покриено со коментар-нишка.' : 'Already covered by the comment thread.'
    }]);
    const stMeta = {
      pending: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'Pending',
        mk: 'Чека'
      },
      approved: {
        c: 'var(--blue)',
        bg: 'var(--blue-soft)',
        en: 'Approved',
        mk: 'Одобрено'
      },
      applied: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Applied',
        mk: 'Применето'
      },
      rejected: {
        c: 'var(--red)',
        bg: 'var(--red-soft)',
        en: 'Rejected',
        mk: 'Одбиено'
      }
    };
    const act = (id, to) => {
      setProps(ps => ps.map(p => p.id === id ? {
        ...p,
        state: to
      } : p));
      onToast && onToast(to === 'rejected' ? 'error' : 'success', (L ? 'Предлог ' : 'Proposal ') + (to === 'approved' ? L ? 'одобрен' : 'approved' : L ? 'одбиен' : 'rejected'), to === 'rejected' ? 'X' : 'Check');
    };
    const FieldChip = ({
      f
    }) => /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '9px 11px',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        background: 'var(--surface-2)'
      }
    }, /*#__PURE__*/React.createElement("code", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, f.k), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        flex: 1,
        color: 'var(--text-body)'
      }
    }, L ? f.mk : f.en), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-9)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        color: typeMeta[f.t],
        border: '1px solid currentColor',
        borderRadius: 999,
        padding: '2px 7px'
      }
    }, f.t));
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 960
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--violet-soft)',
        color: 'var(--violet-700)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('GitPullRequestArrow', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        lineHeight: 1.15,
        whiteSpace: 'nowrap'
      }
    }, L ? 'Управување и контрола на промени' : 'Governance & Change Control')), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1.3fr',
        gap: 14,
        alignItems: 'start'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Регистар на полиња' : 'Field registry'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        margin: '2px 0 8px'
      }
    }, L ? 'Основни колони' : 'Core columns'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        marginBottom: 14
      }
    }, coreFields.map(f => /*#__PURE__*/React.createElement(FieldChip, {
      key: f.k,
      f: f
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        margin: '2px 0 8px'
      }
    }, L ? 'Долгорепни JSON атрибути' : 'Long-tail JSON attributes'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }
    }, extFields.map(f => /*#__PURE__*/React.createElement(FieldChip, {
      key: f.k,
      f: f
    })))), /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'AI-предложени промени' : 'AI-proposed changes'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }
    }, props.map(p => {
      const st = stMeta[p.state];
      return /*#__PURE__*/React.createElement("div", {
        key: p.id,
        style: {
          border: '1px solid var(--line)',
          borderRadius: 'var(--r-md)',
          padding: 13,
          background: 'var(--surface-2)'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          marginBottom: 6
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--violet-700)',
          marginTop: 1
        }
      }, I2('Sparkles', 14)), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 700,
          flex: 1,
          lineHeight: 1.35
        }
      }, p.title), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          color: st.c,
          background: st.bg,
          padding: '3px 8px',
          borderRadius: 999,
          flexShrink: 0
        }
      }, L ? st.mk : st.en)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-12)',
          color: 'var(--text-body)',
          lineHeight: 1.5,
          marginBottom: 9,
          paddingLeft: 22
        }
      }, p.rationale), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          paddingLeft: 22
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '.04em'
        }
      }, p.kind), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          color: 'var(--text-muted)'
        }
      }, "\xB7 ", p.by), p.state === 'pending' && /*#__PURE__*/React.createElement("div", {
        style: {
          marginLeft: 'auto',
          display: 'flex',
          gap: 6
        }
      }, /*#__PURE__*/React.createElement(Button, {
        size: "sm",
        variant: "ghost",
        onClick: () => act(p.id, 'rejected')
      }, L ? 'Одбиј' : 'Reject'), /*#__PURE__*/React.createElement(Button, {
        size: "sm",
        onClick: () => act(p.id, 'approved')
      }, L ? 'Одобри' : 'Approve')), p.state === 'approved' && /*#__PURE__*/React.createElement("div", {
        style: {
          marginLeft: 'auto'
        }
      }, /*#__PURE__*/React.createElement(Button, {
        size: "sm",
        onClick: () => act(p.id, 'applied')
      }, L ? 'Примени' : 'Apply'))));
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 12,
        fontSize: 'var(--fs-11)',
        color: 'var(--text-muted)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        lineHeight: 1.5
      }
    }, I2('Info', 13), L ? 'Секоја промена бара човечко одобрување пред примена — ниедна не се применува автоматски.' : 'Every change requires human approval before it is applied — nothing is auto-applied.'))));
  }

  // ═══════════════════════════ Weekly Planning (draft → submit → approve) ═══════════════════════════
  function Planning({
    lang,
    onToast
  }) {
    const L = lang === 'mk';
    const eyebrow = {
      fontSize: 'var(--fs-11)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--text-muted)',
      marginBottom: 12
    };
    const card = {
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-1)',
      padding: 18
    };
    const stMeta = {
      draft: {
        c: 'var(--text-muted)',
        bg: 'var(--surface-2)',
        en: 'Draft',
        mk: 'Нацрт',
        icon: 'PencilLine'
      },
      submitted: {
        c: 'var(--blue)',
        bg: 'var(--blue-soft)',
        en: 'Submitted',
        mk: 'Поднесено',
        icon: 'Send'
      },
      approved: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Approved',
        mk: 'Одобрено',
        icon: 'CircleCheck'
      },
      changes: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'Changes asked',
        mk: 'Бара промени',
        icon: 'Undo2'
      }
    };
    const seed = [{
      dep: 'qc',
      state: 'submitted',
      items: [{
        t: L ? 'HPLC валидација — F27' : 'HPLC validation — F27',
        pr: 'critical',
        d: L ? 'Чет' : 'Thu'
      }, {
        t: L ? 'Пост-сушење мостри — F27' : 'Post-cure sampling — F27',
        pr: 'high',
        d: L ? 'Пон' : 'Mon'
      }, {
        t: L ? 'Калибрација на pH метар' : 'pH meter calibration',
        pr: 'medium',
        d: L ? 'Сре' : 'Wed'
      }]
    }, {
      dep: 'flower',
      state: 'draft',
      items: [{
        t: L ? 'Жетва блок B — недела 9' : 'Harvest block B — week 9',
        pr: 'high',
        d: L ? 'Вто' : 'Tue'
      }, {
        t: L ? 'IPM скенирање' : 'IPM scouting',
        pr: 'medium',
        d: L ? 'Пет' : 'Fri'
      }]
    }, {
      dep: 'qa',
      state: 'approved',
      items: [{
        t: L ? 'QP преглед — F25 ослободување' : 'QP review — F25 release',
        pr: 'critical',
        d: L ? 'Пет' : 'Fri'
      }, {
        t: L ? 'CAPA затворање — RH сензор' : 'CAPA closure — RH sensor',
        pr: 'high',
        d: L ? 'Чет' : 'Thu'
      }]
    }, {
      dep: 'prod',
      state: 'changes',
      items: [{
        t: L ? 'Пакување серија F24' : 'Packaging run F24',
        pr: 'medium',
        d: L ? 'Сре' : 'Wed'
      }]
    }];
    const [plans, setPlans] = React.useState(seed);
    const [sel, setSel] = React.useState('qc');
    const cur = plans.find(p => p.dep === sel) || plans[0];
    const depName = id => {
      const d = GF_DEPARTMENTS.find(x => x.id === id);
      return d ? L ? d.mk : d.name : id;
    };
    const depColor = id => {
      const d = GF_DEPARTMENTS.find(x => x.id === id);
      return d ? d.color : 'var(--primary)';
    };
    const set = (dep, state) => setPlans(ps => ps.map(p => p.dep === dep ? {
      ...p,
      state
    } : p));
    const priColor = {
      critical: 'var(--red)',
      high: 'var(--orange)',
      medium: 'var(--amber)',
      low: 'var(--text-muted)'
    };
    const priLabel = {
      critical: L ? 'Критичен' : 'Critical',
      high: L ? 'Висок' : 'High',
      medium: L ? 'Среден' : 'Medium',
      low: L ? 'Низок' : 'Low'
    };
    function submit() {
      set(cur.dep, 'submitted');
      onToast && onToast('success', (L ? 'План поднесен — ' : 'Plan submitted — ') + depName(cur.dep), 'Send');
    }
    function approve() {
      set(cur.dep, 'approved');
      onToast && onToast('success', (L ? 'План одобрен — ' : 'Plan approved — ') + depName(cur.dep), 'CircleCheck');
    }
    function askChanges() {
      set(cur.dep, 'changes');
      onToast && onToast('info', (L ? 'Побарани промени — ' : 'Changes requested — ') + depName(cur.dep), 'Undo2');
    }
    const submittedCount = plans.filter(p => p.state === 'submitted' || p.state === 'approved').length;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 1000
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--primary-soft)',
        color: 'var(--primary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('CalendarRange', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        lineHeight: 1.15,
        whiteSpace: 'nowrap'
      }
    }, L ? 'Неделно планирање' : 'Weekly Planning')), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-13)',
        color: 'var(--text-muted)',
        fontWeight: 600,
        marginBottom: 18
      }
    }, L ? `Недела 09 · ${submittedCount}/${plans.length} планови поднесени` : `Week 09 · ${submittedCount}/${plans.length} plans submitted`), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '260px 1fr',
        gap: 14,
        alignItems: 'start'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8
      }
    }, plans.map(p => {
      const st = stMeta[p.state];
      return /*#__PURE__*/React.createElement("button", {
        key: p.dep,
        onClick: () => setSel(p.dep),
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 11,
          padding: '12px 13px',
          borderRadius: 'var(--r-md)',
          border: `1px solid ${sel === p.dep ? 'var(--primary)' : 'var(--line)'}`,
          background: sel === p.dep ? 'color-mix(in srgb, var(--primary) 7%, var(--surface))' : 'var(--surface)',
          cursor: 'pointer',
          fontFamily: 'inherit',
          textAlign: 'left',
          boxShadow: 'var(--sh-1)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 10,
          height: 10,
          borderRadius: 999,
          background: depColor(p.dep),
          flexShrink: 0
        }
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          flex: 1,
          minWidth: 0
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-13)',
          fontWeight: 700,
          color: 'var(--text-strong)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }
      }, depName(p.dep)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-11)',
          fontWeight: 600,
          color: 'var(--text-muted)'
        }
      }, p.items.length, " ", L ? 'ставки' : 'items')), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 'var(--fs-10)',
          fontWeight: 800,
          color: st.c,
          background: st.bg,
          padding: '3px 8px',
          borderRadius: 999
        }
      }, I2(st.icon, 11), L ? st.mk : st.en));
    })), /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 12,
        height: 12,
        borderRadius: 999,
        background: depColor(cur.dep)
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-18)',
        fontWeight: 800,
        flex: 1
      }
    }, depName(cur.dep)), /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 'var(--fs-11)',
        fontWeight: 800,
        color: stMeta[cur.state].c,
        background: stMeta[cur.state].bg,
        padding: '5px 11px',
        borderRadius: 999
      }
    }, I2(stMeta[cur.state].icon, 13), L ? stMeta[cur.state].mk : stMeta[cur.state].en)), /*#__PURE__*/React.createElement("div", {
      style: eyebrow
    }, L ? 'Обврски за неделата' : 'Commitments for the week'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8
      }
    }, cur.items.map((it, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        padding: '11px 13px',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        background: 'var(--surface-2)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 7,
        height: 7,
        borderRadius: 999,
        background: priColor[it.pr],
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-13)',
        fontWeight: 700,
        color: 'var(--text-strong)'
      }
    }, it.t), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-10)',
        fontWeight: 800,
        color: priColor[it.pr],
        textTransform: 'uppercase',
        letterSpacing: '.03em'
      }
    }, priLabel[it.pr]), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        width: 34,
        textAlign: 'right'
      }
    }, it.d)))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 9,
        marginTop: 16,
        paddingTop: 15,
        borderTop: '1px solid var(--line)',
        alignItems: 'center'
      }
    }, cur.state === 'draft' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)',
        fontWeight: 600
      }
    }, L ? 'Нацрт — само ти го гледаш ова.' : 'Draft — only you can see this.'), /*#__PURE__*/React.createElement(Button, {
      onClick: submit
    }, I2('Send', 15), L ? 'Поднеси план' : 'Submit plan')), cur.state === 'submitted' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-12)',
        color: 'var(--text-muted)',
        fontWeight: 600
      }
    }, L ? 'Чека преглед од координатор.' : 'Awaiting coordinator review.'), /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      onClick: askChanges
    }, I2('Undo2', 15), L ? 'Побарај промени' : 'Ask changes'), /*#__PURE__*/React.createElement(Button, {
      onClick: approve
    }, I2('CircleCheck', 15), L ? 'Одобри' : 'Approve')), cur.state === 'approved' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-13)',
        color: 'var(--green-600)',
        fontWeight: 700,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7
      }
    }, I2('CircleCheck', 16), L ? 'Одобрено — заклучено за неделата.' : 'Approved — locked for the week.'), /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      onClick: () => set(cur.dep, 'draft')
    }, I2('RotateCcw', 15), L ? 'Отклучи' : 'Reopen')), cur.state === 'changes' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        fontSize: 'var(--fs-12)',
        color: 'var(--amber)',
        fontWeight: 700
      }
    }, L ? 'Координаторот побара промени.' : 'Coordinator requested changes.'), /*#__PURE__*/React.createElement(Button, {
      onClick: submit
    }, I2('Send', 15), L ? 'Поднеси повторно' : 'Resubmit'))))));
  }

  // ═══════════════════════════ QC Lab mode (sampling gates + disposition) ═══════════════════════════
  function QCLab({
    lang,
    onToast
  }) {
    const L = lang === 'mk';
    const card = {
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-1)',
      padding: 18
    };
    const gateDefs = [{
      k: 'potency',
      en: 'Potency (HPLC)',
      mk: 'Јачина (HPLC)'
    }, {
      k: 'moisture',
      en: 'Moisture',
      mk: 'Влага'
    }, {
      k: 'microbial',
      en: 'Microbial',
      mk: 'Микробиолошки'
    }, {
      k: 'foreign',
      en: 'Foreign matter',
      mk: 'Туѓи материи'
    }];
    const seed = [{
      id: 'F27',
      name: L ? 'Серија F27 · Сушено цвеќе' : 'Batch F27 · Dried flower',
      room: 'Cure-3',
      gates: {
        potency: 'pass',
        moisture: 'pass',
        microbial: 'test',
        foreign: 'idle'
      }
    }, {
      id: 'F26',
      name: L ? 'Серија F26 · Тримано' : 'Batch F26 · Trimmed',
      room: 'Cure-1',
      gates: {
        potency: 'pass',
        moisture: 'pass',
        microbial: 'pass',
        foreign: 'pass'
      }
    }, {
      id: 'F28',
      name: L ? 'Серија F28 · Свежо' : 'Batch F28 · Fresh',
      room: 'Dry-2',
      gates: {
        potency: 'fail',
        moisture: 'pass',
        microbial: 'idle',
        foreign: 'idle'
      }
    }];
    const [batches, setBatches] = React.useState(seed);
    const [sel, setSel] = React.useState('F27');
    const cur = batches.find(b => b.id === sel) || batches[0];
    const gMeta = {
      pass: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Pass',
        mk: 'Помина',
        icon: 'Check'
      },
      fail: {
        c: 'var(--red)',
        bg: 'var(--red-soft)',
        en: 'Fail',
        mk: 'Падна',
        icon: 'X'
      },
      test: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'Testing',
        mk: 'Се тестира',
        icon: 'FlaskConical'
      },
      idle: {
        c: 'var(--text-muted)',
        bg: 'var(--surface-2)',
        en: 'Not started',
        mk: 'Не започнато',
        icon: 'Circle'
      }
    };
    const setGate = (bid, gk, val) => setBatches(bs => bs.map(b => b.id === bid ? {
      ...b,
      gates: {
        ...b.gates,
        [gk]: val
      }
    } : b));
    const gateVals = b => gateDefs.map(g => b.gates[g.k]);
    const allPass = b => gateVals(b).every(v => v === 'pass');
    const anyFail = b => gateVals(b).some(v => v === 'fail');
    const disposition = b => anyFail(b) ? 'reject' : allPass(b) ? 'release' : 'hold';
    const dispMeta = {
      release: {
        c: 'var(--green-600)',
        bg: 'var(--green-100)',
        en: 'Ready to release',
        mk: 'Спремно за ослободување',
        icon: 'PackageCheck'
      },
      hold: {
        c: 'var(--amber)',
        bg: 'var(--amber-soft)',
        en: 'On hold',
        mk: 'На чекање',
        icon: 'PauseCircle'
      },
      reject: {
        c: 'var(--red)',
        bg: 'var(--red-soft)',
        en: 'Quarantine',
        mk: 'Карантин',
        icon: 'OctagonAlert'
      }
    };
    function record(gk, val) {
      setGate(cur.id, gk, val);
      onToast && onToast(val === 'fail' ? 'error' : 'success', (L ? 'Порта ажурирана: ' : 'Gate recorded: ') + (L ? gateDefs.find(g => g.k === gk).mk : gateDefs.find(g => g.k === gk).en), val === 'fail' ? 'X' : 'Check');
    }
    const disp = disposition(cur);
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowY: 'auto',
        height: '100%',
        padding: 24,
        maxWidth: 1000
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 18
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 999,
        background: 'var(--primary-soft)',
        color: 'var(--primary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, I2('FlaskConical', 18)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-22)',
        fontWeight: 800,
        lineHeight: 1.15,
        whiteSpace: 'nowrap'
      }
    }, L ? 'QC лабораторија' : 'QC Lab'), /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 8,
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, batches.length, " ", L ? 'серии во ред' : 'batches queued')), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '280px 1fr',
        gap: 14,
        alignItems: 'start'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8
      }
    }, batches.map(b => {
      const d = dispMeta[disposition(b)];
      const passed = gateVals(b).filter(v => v === 'pass').length;
      return /*#__PURE__*/React.createElement("button", {
        key: b.id,
        onClick: () => setSel(b.id),
        style: {
          textAlign: 'left',
          padding: '13px 14px',
          borderRadius: 'var(--r-md)',
          border: `1px solid ${sel === b.id ? 'var(--primary)' : 'var(--line)'}`,
          background: sel === b.id ? 'color-mix(in srgb, var(--primary) 7%, var(--surface))' : 'var(--surface)',
          cursor: 'pointer',
          fontFamily: 'inherit',
          boxShadow: 'var(--sh-1)'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 7
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--fs-12)',
          fontWeight: 800,
          color: 'var(--text-strong)'
        }
      }, b.id), /*#__PURE__*/React.createElement("span", {
        style: {
          marginLeft: 'auto',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 'var(--fs-10)',
          fontWeight: 800,
          color: d.c,
          background: d.bg,
          padding: '3px 8px',
          borderRadius: 999
        }
      }, I2(d.icon, 11), L ? d.mk : d.en)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-12)',
          fontWeight: 600,
          color: 'var(--text-body)',
          marginBottom: 8
        }
      }, b.name), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 3
        }
      }, gateVals(b).map((v, i) => /*#__PURE__*/React.createElement("span", {
        key: i,
        style: {
          flex: 1,
          height: 4,
          borderRadius: 999,
          background: gMeta[v].c,
          opacity: v === 'idle' ? 0.3 : 1
        }
      }))), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 700,
          color: 'var(--text-muted)',
          marginTop: 5
        }
      }, passed, "/", gateDefs.length, " ", L ? 'порти поминати' : 'gates passed'));
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 14
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: card
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-15)',
        fontWeight: 800
      }
    }, cur.id), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-15)',
        fontWeight: 700,
        flex: 1
      }
    }, cur.name), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        color: 'var(--text-muted)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5
      }
    }, I2('MapPin', 13), cur.room)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)',
        margin: '12px 0 10px'
      }
    }, L ? 'Порти за помин/пад' : 'Pass / fail gates'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 9
      }
    }, gateDefs.map(g => {
      const v = cur.gates[g.k];
      const m = gMeta[v];
      return /*#__PURE__*/React.createElement("div", {
        key: g.k,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '11px 13px',
          border: '1px solid var(--line)',
          borderRadius: 'var(--r-md)',
          background: 'var(--surface-2)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          flex: 1,
          fontSize: 'var(--fs-13)',
          fontWeight: 700,
          color: 'var(--text-strong)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          color: m.c,
          display: 'inline-flex'
        }
      }, I2(m.icon, 15)), L ? g.mk : g.en), /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 'var(--fs-10)',
          fontWeight: 800,
          color: m.c,
          background: m.bg,
          padding: '3px 9px',
          borderRadius: 999,
          textTransform: 'uppercase',
          letterSpacing: '.03em'
        }
      }, L ? m.mk : m.en), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 5
        }
      }, /*#__PURE__*/React.createElement("button", {
        onClick: () => record(g.k, 'pass'),
        title: L ? 'Помина' : 'Pass',
        style: {
          width: 30,
          height: 30,
          borderRadius: 'var(--r-sm)',
          border: `1px solid ${v === 'pass' ? 'var(--green-600)' : 'var(--line)'}`,
          background: v === 'pass' ? 'var(--green-600)' : 'var(--surface)',
          color: v === 'pass' ? '#fff' : 'var(--text-muted)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center'
        }
      }, I2('Check', 15)), /*#__PURE__*/React.createElement("button", {
        onClick: () => record(g.k, 'fail'),
        title: L ? 'Падна' : 'Fail',
        style: {
          width: 30,
          height: 30,
          borderRadius: 'var(--r-sm)',
          border: `1px solid ${v === 'fail' ? 'var(--red)' : 'var(--line)'}`,
          background: v === 'fail' ? 'var(--red)' : 'var(--surface)',
          color: v === 'fail' ? '#fff' : 'var(--text-muted)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center'
        }
      }, I2('X', 15))));
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        ...card,
        borderColor: dispMeta[disp].c,
        display: 'flex',
        alignItems: 'center',
        gap: 13
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 42,
        height: 42,
        borderRadius: 999,
        background: dispMeta[disp].bg,
        color: dispMeta[disp].c,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }
    }, I2(dispMeta[disp].icon, 21)), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-11)',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        color: 'var(--text-muted)'
      }
    }, L ? 'Диспозиција' : 'Disposition'), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 'var(--fs-17)',
        fontWeight: 800,
        color: dispMeta[disp].c
      }
    }, L ? dispMeta[disp].mk : dispMeta[disp].en)), disp === 'release' && /*#__PURE__*/React.createElement(Button, {
      onClick: () => onToast && onToast('success', (L ? 'Серијата ослободена: ' : 'Batch released: ') + cur.id, 'PackageCheck')
    }, I2('PackageCheck', 15), L ? 'Ослободи серија' : 'Release batch'), disp === 'reject' && /*#__PURE__*/React.createElement(Button, {
      variant: "danger",
      onClick: () => onToast && onToast('error', (L ? 'Серијата во карантин: ' : 'Batch quarantined: ') + cur.id, 'OctagonAlert')
    }, I2('OctagonAlert', 15), L ? 'Карантин' : 'Quarantine'), disp === 'hold' && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--fs-12)',
        fontWeight: 700,
        color: 'var(--text-muted)'
      }
    }, L ? 'Заврши ги сите порти' : 'Complete all gates')))));
  }
  window.GFScreens = {
    Team,
    Timeline,
    Coordination,
    AIReport,
    Settings,
    AuditTrail,
    ImportView,
    Analytics,
    Access,
    Governance,
    Planning,
    QCLab
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/growflow/screens.js", error: String((e && e.message) || e) }); }

// ui_kits/growflow/tweaks-panel.js
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)

/* BEGIN USAGE */
// tweaks-panel.jsx
// Reusable Tweaks shell + form-control helpers.
// Exports (to window): useTweaks, TweaksPanel, TweakSection, TweakRow, TweakSlider,
//   TweakToggle, TweakRadio, TweakSelect, TweakText, TweakNumber, TweakColor, TweakButton.
//
// Owns the host protocol (listens for __activate_edit_mode / __deactivate_edit_mode,
// posts __edit_mode_available / __edit_mode_set_keys / __edit_mode_dismissed) so
// individual prototypes don't re-roll it. Ships a consistent set of controls so you
// don't hand-draw <input type="range">, segmented radios, steppers, etc.
//
// Usage (in an HTML file that loads React + Babel):
//
//   const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
//     "primaryColor": "#D97757",
//     "palette": ["#D97757", "#29261b", "#f6f4ef"],
//     "fontSize": 16,
//     "density": "regular",
//     "dark": false
//   }/*EDITMODE-END*/;
//
//   function App() {
//     const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
//     return (
//       <div style={{ fontSize: t.fontSize, color: t.primaryColor }}>
//         Hello
//         <TweaksPanel>
//           <TweakSection label="Typography" />
//           <TweakSlider label="Font size" value={t.fontSize} min={10} max={32} unit="px"
//                        onChange={(v) => setTweak('fontSize', v)} />
//           <TweakRadio  label="Density" value={t.density}
//                        options={['compact', 'regular', 'comfy']}
//                        onChange={(v) => setTweak('density', v)} />
//           <TweakSection label="Theme" />
//           <TweakColor  label="Primary" value={t.primaryColor}
//                        options={['#D97757', '#2A6FDB', '#1F8A5B', '#7A5AE0']}
//                        onChange={(v) => setTweak('primaryColor', v)} />
//           <TweakColor  label="Palette" value={t.palette}
//                        options={[['#D97757', '#29261b', '#f6f4ef'],
//                                  ['#475569', '#0f172a', '#f1f5f9']]}
//                        onChange={(v) => setTweak('palette', v)} />
//           <TweakToggle label="Dark mode" value={t.dark}
//                        onChange={(v) => setTweak('dark', v)} />
//         </TweaksPanel>
//       </div>
//     );
//   }
//
// TweakRadio is the segmented control for 2–3 short options (auto-falls-back to
// TweakSelect past ~16/~10 chars per label); reach for TweakSelect directly when
// options are many or long. For color tweaks always curate 3-4 options rather than
// a free picker; an option can also be a whole 2–5 color palette (the stored value
// is the array). The Tweak* controls are a floor, not a ceiling — build custom
// controls inside the panel if a tweak calls for UI they don't cover.
/* END USAGE */
// ─────────────────────────────────────────────────────────────────────────────

const __TWEAKS_STYLE = `
  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:280px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom right;
    background:rgba(250,249,247,.78);color:#29261b;
    -webkit-backdrop-filter:blur(24px) saturate(160%);backdrop-filter:blur(24px) saturate(160%);
    border:.5px solid rgba(255,255,255,.6);border-radius:14px;
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 12px 40px rgba(0,0,0,.18);
    font:11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:10px 8px 10px 14px;cursor:move;user-select:none}
  .twk-hd b{font-size:12px;font-weight:600;letter-spacing:.01em}
  .twk-x{appearance:none;border:0;background:transparent;color:rgba(41,38,27,.55);
    width:22px;height:22px;border-radius:6px;cursor:default;font-size:13px;line-height:1}
  .twk-x:hover{background:rgba(0,0,0,.06);color:#29261b}
  .twk-body{padding:2px 14px 14px;display:flex;flex-direction:column;gap:10px;
    overflow-y:auto;overflow-x:hidden;min-height:0;
    scrollbar-width:thin;scrollbar-color:rgba(0,0,0,.15) transparent}
  .twk-body::-webkit-scrollbar{width:8px}
  .twk-body::-webkit-scrollbar-track{background:transparent;margin:2px}
  .twk-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.15);border-radius:4px;
    border:2px solid transparent;background-clip:content-box}
  .twk-body::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.25);
    border:2px solid transparent;background-clip:content-box}
  .twk-row{display:flex;flex-direction:column;gap:5px}
  .twk-row-h{flex-direction:row;align-items:center;justify-content:space-between;gap:10px}
  .twk-lbl{display:flex;justify-content:space-between;align-items:baseline;
    color:rgba(41,38,27,.72)}
  .twk-lbl>span:first-child{font-weight:500}
  .twk-val{color:rgba(41,38,27,.5);font-variant-numeric:tabular-nums}

  .twk-sect{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:rgba(41,38,27,.45);padding:10px 0 0}
  .twk-sect:first-child{padding-top:0}

  .twk-field{appearance:none;box-sizing:border-box;width:100%;min-width:0;height:26px;padding:0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;
    background:rgba(255,255,255,.6);color:inherit;font:inherit;outline:none}
  .twk-field:focus{border-color:rgba(0,0,0,.25);background:rgba(255,255,255,.85)}
  select.twk-field{padding-right:22px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='rgba(0,0,0,.5)' d='M0 0h10L5 6z'/></svg>");
    background-repeat:no-repeat;background-position:right 8px center}

  .twk-slider{appearance:none;-webkit-appearance:none;width:100%;height:4px;margin:6px 0;
    border-radius:999px;background:rgba(0,0,0,.12);outline:none}
  .twk-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:14px;height:14px;border-radius:50%;background:#fff;
    border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}
  .twk-slider::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
    background:#fff;border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}

  .twk-seg{position:relative;display:flex;padding:2px;border-radius:8px;
    background:rgba(0,0,0,.06);user-select:none}
  .twk-seg-thumb{position:absolute;top:2px;bottom:2px;border-radius:6px;
    background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.12);
    transition:left .15s cubic-bezier(.3,.7,.4,1),width .15s}
  .twk-seg.dragging .twk-seg-thumb{transition:none}
  .twk-seg button{appearance:none;position:relative;z-index:1;flex:1;border:0;
    background:transparent;color:inherit;font:inherit;font-weight:500;min-height:22px;
    border-radius:6px;cursor:default;padding:4px 6px;line-height:1.2;
    overflow-wrap:anywhere}

  .twk-toggle{position:relative;width:32px;height:18px;border:0;border-radius:999px;
    background:rgba(0,0,0,.15);transition:background .15s;cursor:default;padding:0}
  .twk-toggle[data-on="1"]{background:#34c759}
  .twk-toggle i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;
    background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
  .twk-toggle[data-on="1"] i{transform:translateX(14px)}

  .twk-num{display:flex;align-items:center;box-sizing:border-box;min-width:0;height:26px;padding:0 0 0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;background:rgba(255,255,255,.6)}
  .twk-num-lbl{font-weight:500;color:rgba(41,38,27,.6);cursor:ew-resize;
    user-select:none;padding-right:8px}
  .twk-num input{flex:1;min-width:0;height:100%;border:0;background:transparent;
    font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:0 8px 0 0;
    outline:none;color:inherit;-moz-appearance:textfield}
  .twk-num input::-webkit-inner-spin-button,.twk-num input::-webkit-outer-spin-button{
    -webkit-appearance:none;margin:0}
  .twk-num-unit{padding-right:8px;color:rgba(41,38,27,.45)}

  .twk-btn{appearance:none;height:26px;padding:0 12px;border:0;border-radius:7px;
    background:rgba(0,0,0,.78);color:#fff;font:inherit;font-weight:500;cursor:default}
  .twk-btn:hover{background:rgba(0,0,0,.88)}
  .twk-btn.secondary{background:rgba(0,0,0,.06);color:inherit}
  .twk-btn.secondary:hover{background:rgba(0,0,0,.1)}

  .twk-swatch{appearance:none;-webkit-appearance:none;width:56px;height:22px;
    border:.5px solid rgba(0,0,0,.1);border-radius:6px;padding:0;cursor:default;
    background:transparent;flex-shrink:0}
  .twk-swatch::-webkit-color-swatch-wrapper{padding:0}
  .twk-swatch::-webkit-color-swatch{border:0;border-radius:5.5px}
  .twk-swatch::-moz-color-swatch{border:0;border-radius:5.5px}

  .twk-chips{display:flex;gap:6px}
  .twk-chip{position:relative;appearance:none;flex:1;min-width:0;height:46px;
    padding:0;border:0;border-radius:6px;overflow:hidden;cursor:default;
    box-shadow:0 0 0 .5px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.06);
    transition:transform .12s cubic-bezier(.3,.7,.4,1),box-shadow .12s}
  .twk-chip:hover{transform:translateY(-1px);
    box-shadow:0 0 0 .5px rgba(0,0,0,.18),0 4px 10px rgba(0,0,0,.12)}
  .twk-chip[data-on="1"]{box-shadow:0 0 0 1.5px rgba(0,0,0,.85),
    0 2px 6px rgba(0,0,0,.15)}
  .twk-chip>span{position:absolute;top:0;bottom:0;right:0;width:34%;
    display:flex;flex-direction:column;box-shadow:-1px 0 0 rgba(0,0,0,.1)}
  .twk-chip>span>i{flex:1;box-shadow:0 -1px 0 rgba(0,0,0,.1)}
  .twk-chip>span>i:first-child{box-shadow:none}
  .twk-chip svg{position:absolute;top:6px;left:6px;width:13px;height:13px;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))}
`;

// ── useTweaks ───────────────────────────────────────────────────────────────
// Single source of truth for tweak values. setTweak persists via the host
// (__edit_mode_set_keys → host rewrites the EDITMODE block on disk).
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  // Accepts either setTweak('key', value) or setTweak({ key: value, ... }) so a
  // useState-style call doesn't write a "[object Object]" key into the persisted
  // JSON block.
  const setTweak = React.useCallback((keyOrEdits, val) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null ? keyOrEdits : {
      [keyOrEdits]: val
    };
    setValues(prev => ({
      ...prev,
      ...edits
    }));
    window.parent.postMessage({
      type: '__edit_mode_set_keys',
      edits
    }, '*');
    // Same-window signal so in-page listeners (deck-stage rail thumbnails)
    // can react — the parent message only reaches the host, not peers.
    window.dispatchEvent(new CustomEvent('tweakchange', {
      detail: edits
    }));
  }, []);
  return [values, setTweak];
}

// ── TweaksPanel ─────────────────────────────────────────────────────────────
// Floating shell. Registers the protocol listener BEFORE announcing
// availability — if the announce ran first, the host's activate could land
// before our handler exists and the toolbar toggle would silently no-op.
// The close button posts __edit_mode_dismissed so the host's toolbar toggle
// flips off in lockstep; the host echoes __deactivate_edit_mode back which
// is what actually hides the panel.
function TweaksPanel({
  title = 'Tweaks',
  children
}) {
  const [open, setOpen] = React.useState(false);
  const dragRef = React.useRef(null);
  const offsetRef = React.useRef({
    x: 16,
    y: 16
  });
  const PAD = 16;
  const clampToViewport = React.useCallback(() => {
    const panel = dragRef.current;
    if (!panel) return;
    const w = panel.offsetWidth,
      h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y))
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);
  React.useEffect(() => {
    if (!open) return;
    clampToViewport();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', clampToViewport);
      return () => window.removeEventListener('resize', clampToViewport);
    }
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);
  React.useEffect(() => {
    const onMsg = e => {
      const t = e?.data?.type;
      if (t === '__activate_edit_mode') setOpen(true);else if (t === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({
      type: '__edit_mode_available'
    }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);
  const dismiss = () => {
    setOpen(false);
    window.parent.postMessage({
      type: '__edit_mode_dismissed'
    }, '*');
  };
  const onDragStart = e => {
    const panel = dragRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX,
      sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = ev => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy)
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };
  if (!open) return null;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("style", null, __TWEAKS_STYLE), /*#__PURE__*/React.createElement("div", {
    ref: dragRef,
    className: "twk-panel",
    "data-omelette-chrome": "",
    style: {
      right: offsetRef.current.x,
      bottom: offsetRef.current.y
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-hd",
    onMouseDown: onDragStart
  }, /*#__PURE__*/React.createElement("b", null, title), /*#__PURE__*/React.createElement("button", {
    className: "twk-x",
    "aria-label": "Close tweaks",
    onMouseDown: e => e.stopPropagation(),
    onClick: dismiss
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    className: "twk-body"
  }, children)));
}

// ── Layout helpers ──────────────────────────────────────────────────────────

function TweakSection({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "twk-sect"
  }, label), children);
}
function TweakRow({
  label,
  value,
  children,
  inline = false
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: inline ? 'twk-row twk-row-h' : 'twk-row'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label), value != null && /*#__PURE__*/React.createElement("span", {
    className: "twk-val"
  }, value)), children);
}

// ── Controls ────────────────────────────────────────────────────────────────

function TweakSlider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label,
    value: `${value}${unit}`
  }, /*#__PURE__*/React.createElement("input", {
    type: "range",
    className: "twk-slider",
    min: min,
    max: max,
    step: step,
    value: value,
    onChange: e => onChange(Number(e.target.value))
  }));
}
function TweakToggle({
  label,
  value,
  onChange
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-row twk-row-h"
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "twk-toggle",
    "data-on": value ? '1' : '0',
    role: "switch",
    "aria-checked": !!value,
    onClick: () => onChange(!value)
  }, /*#__PURE__*/React.createElement("i", null)));
}
function TweakRadio({
  label,
  value,
  options,
  onChange
}) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);
  // The active value is read by pointer-move handlers attached for the lifetime
  // of a drag — ref it so a stale closure doesn't fire onChange for every move.
  const valueRef = React.useRef(value);
  valueRef.current = value;

  // Segments wrap mid-word once per-segment width runs out. The track is
  // ~248px (280 panel − 28 body pad − 4 seg pad), each button loses 12px
  // to its own padding, and 11.5px system-ui averages ~6.3px/char — so 2
  // options fit ~16 chars each, 3 fit ~10. Past that (or >3 options), fall
  // back to a dropdown rather than wrap.
  const labelLen = o => String(typeof o === 'object' ? o.label : o).length;
  const maxLen = options.reduce((m, o) => Math.max(m, labelLen(o)), 0);
  const fitsAsSegments = maxLen <= ({
    2: 16,
    3: 10
  }[options.length] ?? 0);
  if (!fitsAsSegments) {
    // <select> emits strings — map back to the original option value so the
    // fallback stays type-preserving (numbers, booleans) like the segment path.
    const resolve = s => {
      const m = options.find(o => String(typeof o === 'object' ? o.value : o) === s);
      return m === undefined ? s : typeof m === 'object' ? m.value : m;
    };
    return /*#__PURE__*/React.createElement(TweakSelect, {
      label: label,
      value: value,
      options: options,
      onChange: s => onChange(resolve(s))
    });
  }
  const opts = options.map(o => typeof o === 'object' ? o : {
    value: o,
    label: o
  });
  const idx = Math.max(0, opts.findIndex(o => o.value === value));
  const n = opts.length;
  const segAt = clientX => {
    const r = trackRef.current.getBoundingClientRect();
    const inner = r.width - 4;
    const i = Math.floor((clientX - r.left - 2) / inner * n);
    return opts[Math.max(0, Math.min(n - 1, i))].value;
  };
  const onPointerDown = e => {
    setDragging(true);
    const v0 = segAt(e.clientX);
    if (v0 !== valueRef.current) onChange(v0);
    const move = ev => {
      if (!trackRef.current) return;
      const v = segAt(ev.clientX);
      if (v !== valueRef.current) onChange(v);
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    ref: trackRef,
    role: "radiogroup",
    onPointerDown: onPointerDown,
    className: dragging ? 'twk-seg dragging' : 'twk-seg'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-seg-thumb",
    style: {
      left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
      width: `calc((100% - 4px) / ${n})`
    }
  }), opts.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    type: "button",
    role: "radio",
    "aria-checked": o.value === value
  }, o.label))));
}
function TweakSelect({
  label,
  value,
  options,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("select", {
    className: "twk-field",
    value: value,
    onChange: e => onChange(e.target.value)
  }, options.map(o => {
    const v = typeof o === 'object' ? o.value : o;
    const l = typeof o === 'object' ? o.label : o;
    return /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, l);
  })));
}
function TweakText({
  label,
  value,
  placeholder,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("input", {
    className: "twk-field",
    type: "text",
    value: value,
    placeholder: placeholder,
    onChange: e => onChange(e.target.value)
  }));
}
function TweakNumber({
  label,
  value,
  min,
  max,
  step = 1,
  unit = '',
  onChange
}) {
  const clamp = n => {
    if (min != null && n < min) return min;
    if (max != null && n > max) return max;
    return n;
  };
  const startRef = React.useRef({
    x: 0,
    val: 0
  });
  const onScrubStart = e => {
    e.preventDefault();
    startRef.current = {
      x: e.clientX,
      val: value
    };
    const decimals = (String(step).split('.')[1] || '').length;
    const move = ev => {
      const dx = ev.clientX - startRef.current.x;
      const raw = startRef.current.val + dx * step;
      const snapped = Math.round(raw / step) * step;
      onChange(clamp(Number(snapped.toFixed(decimals))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-num"
  }, /*#__PURE__*/React.createElement("span", {
    className: "twk-num-lbl",
    onPointerDown: onScrubStart
  }, label), /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: value,
    min: min,
    max: max,
    step: step,
    onChange: e => onChange(clamp(Number(e.target.value)))
  }), unit && /*#__PURE__*/React.createElement("span", {
    className: "twk-num-unit"
  }, unit));
}

// Relative-luminance contrast pick — checkmarks drawn over a swatch need to
// read on both #111 and #fafafa without per-option configuration. Hex input
// only (#rgb / #rrggbb); named or rgb()/hsl() colors fall through to "light".
function __twkIsLight(hex) {
  const h = String(hex).replace('#', '');
  const x = h.length === 3 ? h.replace(/./g, c => c + c) : h.padEnd(6, '0');
  const n = parseInt(x.slice(0, 6), 16);
  if (Number.isNaN(n)) return true;
  const r = n >> 16 & 255,
    g = n >> 8 & 255,
    b = n & 255;
  return r * 299 + g * 587 + b * 114 > 148000;
}
const __TwkCheck = ({
  light
}) => /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 14 14",
  "aria-hidden": "true"
}, /*#__PURE__*/React.createElement("path", {
  d: "M3 7.2 5.8 10 11 4.2",
  fill: "none",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  stroke: light ? 'rgba(0,0,0,.78)' : '#fff'
}));

// TweakColor — curated color/palette picker. Each option is either a single
// hex string or an array of 1-5 hex strings; the card adapts — a lone color
// renders solid, a palette renders colors[0] as the hero (left ~2/3) with the
// rest stacked in a sharp column on the right. onChange emits the
// option in the shape it was passed (string stays string, array stays array).
// Without options it falls back to the native color input for back-compat.
function TweakColor({
  label,
  value,
  options,
  onChange
}) {
  if (!options || !options.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "twk-row twk-row-h"
    }, /*#__PURE__*/React.createElement("div", {
      className: "twk-lbl"
    }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("input", {
      type: "color",
      className: "twk-swatch",
      value: value,
      onChange: e => onChange(e.target.value)
    }));
  }
  // Native <input type=color> emits lowercase hex per the HTML spec, so
  // compare case-insensitively. String() guards JSON.stringify(undefined),
  // which returns the primitive undefined (no .toLowerCase).
  const key = o => String(JSON.stringify(o)).toLowerCase();
  const cur = key(value);
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-chips",
    role: "radiogroup"
  }, options.map((o, i) => {
    const colors = Array.isArray(o) ? o : [o];
    const [hero, ...rest] = colors;
    const sup = rest.slice(0, 4);
    const on = key(o) === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: i,
      type: "button",
      className: "twk-chip",
      role: "radio",
      "aria-checked": on,
      "data-on": on ? '1' : '0',
      "aria-label": colors.join(', '),
      title: colors.join(' · '),
      style: {
        background: hero
      },
      onClick: () => onChange(o)
    }, sup.length > 0 && /*#__PURE__*/React.createElement("span", null, sup.map((c, j) => /*#__PURE__*/React.createElement("i", {
      key: j,
      style: {
        background: c
      }
    }))), on && /*#__PURE__*/React.createElement(__TwkCheck, {
      light: __twkIsLight(hero)
    }));
  })));
}
function TweakButton({
  label,
  onClick,
  secondary = false
}) {
  return /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: secondary ? 'twk-btn secondary' : 'twk-btn',
    onClick: onClick
  }, label);
}
Object.assign(window, {
  useTweaks,
  TweaksPanel,
  TweakSection,
  TweakRow,
  TweakSlider,
  TweakToggle,
  TweakRadio,
  TweakSelect,
  TweakText,
  TweakNumber,
  TweakColor,
  TweakButton
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/growflow/tweaks-panel.js", error: String((e && e.message) || e) }); }

// uploads/files/LeafMark.jsx
try { (() => {
const {
  useMemo
} = React;
const DEFAULT_DEPTH = 26;
function getLayerVars(i, depth) {
  const t = depth <= 1 ? 0 : i / (depth - 1);
  const brightness = i === 0 ? 1.18 : Math.max(0.2, 0.8 - t * 0.6);
  const saturation = i === 0 ? 1.5 : Math.max(0.55, 1.12 - t * 0.55);
  const contrast = i === 0 ? 1.04 : 1.04 + t * 0.22;
  const sepia = i === 0 ? 0 : 0.08 + t * 0.28;
  const opacity = i === 0 ? 1 : 0.98 - t * 0.06;
  return {
    "--i": i,
    "--layer-brightness": brightness.toFixed(3),
    "--layer-saturation": saturation.toFixed(3),
    "--layer-contrast": contrast.toFixed(3),
    "--layer-sepia": sepia.toFixed(3),
    "--layer-opacity": opacity.toFixed(3)
  };
}

/**
 * LeafMark
 * Fake-3D logo object built from stacked SVG planes.
 *
 * Props:
 * - src: path to PP_Leaf.svg or any transparent leaf asset
 * - depth: number of planes, default 26
 * - size: CSS size for Y axis / object box, default "min(54vmin, 420px)"
 * - depthRatio: total Z thickness relative to leaf height, default 0.17
 * Static only: no spin, no wobble, no click burst, no settle animation.
 */
function LeafMark({
  src = "/PP_Leaf.svg",
  alt = "3D leaf logo",
  depth = DEFAULT_DEPTH,
  size = "min(54vmin, 420px)",
  depthRatio = 0.17,
  className = ""
}) {
  const layers = useMemo(() => {
    return Array.from({
      length: depth
    }, (_, n) => depth - 1 - n);
  }, [depth]);
  return /*#__PURE__*/React.createElement("div", {
    className: `gf-splash-stage is-static ${className}`.trim(),
    style: {
      "--leaf-size": size,
      "--leaf-depth-count": depth,
      "--leaf-depth-ratio": depthRatio
    },
    "aria-label": alt
  }, /*#__PURE__*/React.createElement("div", {
    className: "gf-splash-shadow"
  }), /*#__PURE__*/React.createElement("div", {
    className: "gf-splash-wobble"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gf-splash-spin"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gf-splash-leafmark"
  }, layers.map(i => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "gf-splash-layer",
    "data-front": i === 0 ? "true" : undefined,
    style: getLayerVars(i, depth)
  }, /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: i === 0 ? alt : "",
    "aria-hidden": i === 0 ? undefined : true,
    draggable: false,
    decoding: "async"
  })))))));
}
Object.assign(__ds_scope, { LeafMark, __ds_default_uploads_files_LeafMark_5f33n5: LeafMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "uploads/files/LeafMark.jsx", error: String((e && e.message) || e) }); }

// uploads/files/leaf-3d-object-package/leaf-3d-export/leaf-mark.js
try { (() => {
/*
  Vanilla LeafMark 3D object initializer.
  Usage:
    <div data-leafmark data-src="../PP_Leaf.svg"></div>
    <script src="leaf-mark.js"></script>
*/

const DEFAULT_DEPTH = 26;
function layerStyle(i, depth) {
  const t = depth <= 1 ? 0 : i / (depth - 1);
  const brightness = i === 0 ? 1.18 : Math.max(0.2, 0.8 - t * 0.6);
  const saturation = i === 0 ? 1.5 : Math.max(0.55, 1.12 - t * 0.55);
  const contrast = i === 0 ? 1.04 : 1.04 + t * 0.22;
  const sepia = i === 0 ? 0 : 0.08 + t * 0.28;
  const opacity = i === 0 ? 1 : 0.98 - t * 0.06;
  return {
    "--i": i,
    "--layer-brightness": brightness.toFixed(3),
    "--layer-saturation": saturation.toFixed(3),
    "--layer-contrast": contrast.toFixed(3),
    "--layer-sepia": sepia.toFixed(3),
    "--layer-opacity": opacity.toFixed(3)
  };
}
function applyStyleVars(el, vars) {
  Object.entries(vars).forEach(([key, value]) => el.style.setProperty(key, value));
}
function createLeafMark(target, options = {}) {
  const src = options.src || target.dataset.src || "../PP_Leaf.svg";
  const depth = Number(options.depth || target.dataset.depth || DEFAULT_DEPTH);
  const size = options.size || target.dataset.size || "min(54vmin, 420px)";
  const depthRatio = options.depthRatio || target.dataset.depthRatio || "0.17";
  const alt = options.alt || target.dataset.alt || "3D leaf logo";
  target.classList.add("gf-splash-stage", "is-static");
  target.style.setProperty("--leaf-size", size);
  target.style.setProperty("--leaf-depth-count", depth);
  target.style.setProperty("--leaf-depth-ratio", depthRatio);
  target.setAttribute("aria-label", alt);
  target.innerHTML = "";
  const shadow = document.createElement("div");
  shadow.className = "gf-splash-shadow";
  const wobble = document.createElement("div");
  wobble.className = "gf-splash-wobble";
  const spin = document.createElement("div");
  spin.className = "gf-splash-spin";
  const leaf = document.createElement("div");
  leaf.className = "gf-splash-leafmark";
  for (let i = depth - 1; i >= 0; i -= 1) {
    const layer = document.createElement("div");
    layer.className = "gf-splash-layer";
    if (i === 0) layer.dataset.front = "true";
    applyStyleVars(layer, layerStyle(i, depth));
    const img = document.createElement("img");
    img.src = src;
    img.alt = i === 0 ? alt : "";
    img.decoding = "async";
    img.draggable = false;
    if (i !== 0) img.setAttribute("aria-hidden", "true");
    layer.appendChild(img);
    leaf.appendChild(layer);
  }
  spin.appendChild(leaf);
  wobble.appendChild(spin);
  target.appendChild(shadow);
  target.appendChild(wobble);
  return {
    root: target,
    depth,
    src
  };
}

// Auto-init all declarative instances when used directly in a browser.
if (typeof window !== "undefined") {
  window.createLeafMark = createLeafMark;
  window.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-leafmark]").forEach(node => {
      if (!node.dataset.leafmarkReady) {
        createLeafMark(node);
        node.dataset.leafmarkReady = "true";
      }
    });
  });
}
Object.assign(__ds_scope, { createLeafMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "uploads/files/leaf-3d-object-package/leaf-3d-export/leaf-mark.js", error: String((e && e.message) || e) }); }

__ds_ns.Leaf = __ds_scope.Leaf;

__ds_ns.GrowFlowLockup = __ds_scope.GrowFlowLockup;

__ds_ns.Warbird = __ds_scope.Warbird;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.AvatarStack = __ds_scope.AvatarStack;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Chip = __ds_scope.Chip;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.KpiTile = __ds_scope.KpiTile;

__ds_ns.BarRow = __ds_scope.BarRow;

__ds_ns.Modal = __ds_scope.Modal;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Segmented = __ds_scope.Segmented;

__ds_ns.Field = __ds_scope.Field;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Textarea = __ds_scope.Textarea;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.NavItem = __ds_scope.NavItem;

__ds_ns.DeptRow = __ds_scope.DeptRow;

__ds_ns.DayPill = __ds_scope.DayPill;

__ds_ns.STATUS = __ds_scope.STATUS;

__ds_ns.StatusPill = __ds_scope.StatusPill;

__ds_ns.PriorityTag = __ds_scope.PriorityTag;

__ds_ns.DueBadge = __ds_scope.DueBadge;

__ds_ns.TypeChip = __ds_scope.TypeChip;

__ds_ns.RefCode = __ds_scope.RefCode;

__ds_ns.TaskCard = __ds_scope.TaskCard;

__ds_ns.LeafMark = __ds_scope.LeafMark;

})();
