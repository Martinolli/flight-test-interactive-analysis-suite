import { useCallback, useRef, useState } from 'react';

/**
 * Returns a ref to attach to the chart container div and a download function.
 *
 * Strategy:
 *  1. If the container holds an <svg> element (Recharts), serialise it directly
 *     to PNG via a Canvas — this is instant and lossless.
 *  2. Fall back to html2canvas for non-SVG containers (e.g. Plotly, tables).
 *
 * Usage:
 *   const { chartRef, downloadChart, downloading } = useChartDownload();
 *   <div ref={chartRef}> ... chart ... </div>
 *   <button onClick={() => downloadChart('Ground_Speed_FlightTest1')}>Download</button>
 */
export function useChartDownload() {
  const chartRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);

  const downloadChart = useCallback(async (filename: string) => {
    if (!chartRef.current) return;
    setDownloading(true);
    try {
      const svgEl = chartRef.current.querySelector('svg');
      if (svgEl) {
        await downloadSvgAsPng(svgEl, filename);
      } else {
        await downloadViaHtml2Canvas(chartRef.current, filename);
      }
    } catch (err) {
      console.error('Chart download failed:', err);
    } finally {
      setDownloading(false);
    }
  }, []);

  return { chartRef, downloadChart, downloading };
}

// ── SVG → PNG (primary path for Recharts) ───────────────────────────────────

async function downloadSvgAsPng(svgEl: SVGElement, filename: string): Promise<void> {
  // Clone so we can mutate freely without affecting the live DOM
  const clone = svgEl.cloneNode(true) as SVGElement;

  // Ensure explicit pixel dimensions (ResponsiveContainer uses 100% by default)
  const rect = svgEl.getBoundingClientRect();
  const W = Math.round(rect.width)  || 800;
  const H = Math.round(rect.height) || 400;
  clone.setAttribute('width',  String(W));
  clone.setAttribute('height', String(H));
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

  // Inline all computed styles for text/axis elements so the export looks right
  inlineStyles(svgEl, clone);

  // Serialise to a data URL
  const serialiser = new XMLSerializer();
  const svgStr = serialiser.serializeToString(clone);
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const svgUrl  = URL.createObjectURL(svgBlob);

  // Draw onto a canvas at 2× for crisp export
  const scale  = 2;
  const canvas = document.createElement('canvas');
  canvas.width  = W * scale;
  canvas.height = H * scale;
  const ctx = canvas.getContext('2d')!;
  ctx.scale(scale, scale);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);

  await new Promise<void>((resolve, reject) => {
    const img = new Image();
    img.onload = () => { ctx.drawImage(img, 0, 0); resolve(); };
    img.onerror = reject;
    img.src = svgUrl;
  });

  URL.revokeObjectURL(svgUrl);

  // Trigger download
  const link = document.createElement('a');
  link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.png`;
  link.href = canvas.toDataURL('image/png');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Copy a small set of computed styles that Recharts relies on for correct
 * rendering when the SVG is detached from the document.
 */
function inlineStyles(source: Element, target: Element): void {
  const PROPS = ['fill', 'stroke', 'font-size', 'font-family', 'font-weight'];
  const srcStyle = window.getComputedStyle(source);
  const tgtEl    = target as SVGElement;

  PROPS.forEach((prop) => {
    const val = srcStyle.getPropertyValue(prop);
    if (val) tgtEl.style.setProperty(prop, val);
  });

  const srcChildren = source.children;
  const tgtChildren = target.children;
  for (let i = 0; i < srcChildren.length; i++) {
    if (tgtChildren[i]) inlineStyles(srcChildren[i], tgtChildren[i]);
  }
}

// ── html2canvas fallback (for non-SVG containers) ───────────────────────────

async function downloadViaHtml2Canvas(el: HTMLElement, filename: string): Promise<void> {
  const html2canvas = (await import('html2canvas')).default;
  const canvas = await html2canvas(el, {
    backgroundColor: '#ffffff',
    scale: 2,
    useCORS: true,
    logging: false,
  });
  const link = document.createElement('a');
  link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.png`;
  link.href = canvas.toDataURL('image/png');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
