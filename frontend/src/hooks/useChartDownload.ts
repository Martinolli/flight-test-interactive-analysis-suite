import { useCallback, useRef, useState } from 'react';

/**
 * Returns a ref to attach to the chart container div and a download function.
 * The download function captures the container as a PNG via html2canvas.
 *
 * Usage:
 *   const { chartRef, downloadChart, downloading } = useChartDownload();
 *   <div ref={chartRef}> ... chart ... </div>
 *   <button onClick={() => downloadChart('Ground_Speed_FlightTest1')}>Download</button>
 */
export function useChartDownload() {
  const chartRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);

  const downloadChart = useCallback(
    async (filename: string) => {
      if (!chartRef.current) return;
      setDownloading(true);
      try {
        // Dynamically import to keep initial bundle small
        const html2canvas = (await import('html2canvas')).default;
        const canvas = await html2canvas(chartRef.current, {
          backgroundColor: '#ffffff',
          scale: 2, // 2× resolution for crisp export
          useCORS: true,
          logging: false,
        });
        const link = document.createElement('a');
        link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.png`;
        link.href = canvas.toDataURL('image/png');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (err) {
        console.error('Chart download failed:', err);
      } finally {
        setDownloading(false);
      }
    },
    []
  );

  return { chartRef, downloadChart, downloading };
}
