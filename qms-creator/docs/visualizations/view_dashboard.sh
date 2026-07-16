#!/bin/bash
echo "========================================"
echo "  QMS DASHBOARD VIEWER"
echo "========================================"
echo ""
echo "Choose a dashboard to open:"
echo ""
echo "1. Mermaid Dashboard (Modern diagrams)"
echo "2. D3.js Interactive Dashboard (Advanced)"
echo "3. Open both"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
  1)
    echo "Opening Mermaid dashboard..."
    xdg-open "docs/visualizations/dashboard.html" 2>/dev/null || open "docs/visualizations/dashboard.html" 2>/dev/null || echo "Please open: docs/visualizations/dashboard.html"
    ;;
  2)
    echo "Opening D3.js interactive dashboard..."
    xdg-open "docs/visualizations/interactive_dashboard.html" 2>/dev/null || open "docs/visualizations/interactive_dashboard.html" 2>/dev/null || echo "Please open: docs/visualizations/interactive_dashboard.html"
    ;;
  3)
    echo "Opening both dashboards..."
    xdg-open "docs/visualizations/dashboard.html" 2>/dev/null || open "docs/visualizations/dashboard.html" 2>/dev/null &
    xdg-open "docs/visualizations/interactive_dashboard.html" 2>/dev/null || open "docs/visualizations/interactive_dashboard.html" 2>/dev/null &
    ;;
  *)
    echo "Invalid choice"
    ;;
esac

echo ""
echo "Dashboard(s) opened in your browser!"
