import { useState, type CSSProperties, type ReactNode } from "react";

export interface Column<T> {
  key: keyof T & string;
  header: string;
  render?: (value: T[keyof T], row: T) => ReactNode;
  width?: string | number;
}

export interface DataTableProps<T extends { id: string | number }> {
  columns: Column<T>[];
  rows: T[];
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T extends { id: string | number }>({ columns, rows, emptyMessage = "No records.", onRowClick }: DataTableProps<T>) {
  return (
    <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ ...thStyle, width: c.width }}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={columns.length} style={{ padding: "32px 12px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>{emptyMessage}</td></tr>
          ) : (
            rows.map((row) => <Row key={row.id} row={row} columns={columns} onRowClick={onRowClick} />)
          )}
        </tbody>
      </table>
    </div>
  );
}

function Row<T extends { id: string | number }>({ row, columns, onRowClick }: { row: T; columns: Column<T>[]; onRowClick?: (row: T) => void }) {
  const [hover, setHover] = useState(false);
  return (
    <tr
      onClick={() => onRowClick?.(row)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ cursor: onRowClick ? "pointer" : "default", background: hover ? "var(--zebra)" : "transparent" }}
    >
      {columns.map((c) => (
        <td key={c.key} style={tdStyle}>
          {c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}
        </td>
      ))}
    </tr>
  );
}

const thStyle: CSSProperties = { padding: "8px 12px", textAlign: "left", background: "var(--zebra-head)", borderBottom: "1px solid var(--border-strong)", color: "var(--text-tertiary)", fontSize: 11, fontWeight: 600, letterSpacing: "0.03em", whiteSpace: "nowrap" };
const tdStyle: CSSProperties = { padding: "9px 12px", borderBottom: "1px solid var(--border-subtle)", verticalAlign: "middle" };
