import { useState } from "react";
import toast from "react-hot-toast";
import { Download, FileDown, Link2, Loader2 } from "lucide-react";
import { useExport } from "../hooks/useExport.js";
import { backendUrl } from "../utils/api.js";
import ShareModal from "./ShareModal.jsx";

export default function ExportButtons({ taskId, theme }) {
  const { exportPptx, exportPdf, createShare } = useExport();
  const [busy, setBusy] = useState(null);
  const [shareUrl, setShareUrl] = useState(null);
  const [shareOpen, setShareOpen] = useState(false);

  const handle = async (kind) => {
    setBusy(kind);
    // Phase 6AL-Export: surface a soft warning if the export takes longer
    // than 4s so the user knows the spinner is real progress, not a hang.
    // First-time PPTX exports fetch 4-6 Pollinations images in parallel
    // and can legitimately take 10-20s.
    let slowToastId = null;
    if (kind === "pptx" || kind === "pdf") {
      slowToastId = setTimeout(() => {
        slowToastId = toast.loading(
          kind === "pptx"
            ? "Assembling slides and images…"
            : "Rendering PDF…",
          { id: `export-slow-${kind}` }
        );
      }, 4000);
    }
    const triggerDownload = (url, filename) => {
      // Use a hidden anchor so the browser treats this as a real
      // download instead of a navigation, avoiding the "new tab that
      // immediately closes" flash some browsers show for window.open.
      const a = document.createElement("a");
      a.href = url;
      a.rel = "noopener";
      a.target = "_blank";
      if (filename) a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    };
    try {
      if (kind === "pptx") {
        const { download_url } = await exportPptx(taskId, theme);
        triggerDownload(backendUrl(download_url), `${taskId}.pptx`);
        toast.success("PPTX ready.", { id: `export-slow-${kind}` });
      } else if (kind === "pdf") {
        const { download_url } = await exportPdf(taskId, theme);
        triggerDownload(backendUrl(download_url), `${taskId}.pdf`);
        toast.success("PDF ready.", { id: `export-slow-${kind}` });
      } else if (kind === "share") {
        const { share_url } = await createShare(taskId);
        setShareUrl(share_url);
        setShareOpen(true);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Export failed.", {
        id: `export-slow-${kind}`,
      });
    } finally {
      if (typeof slowToastId === "number") clearTimeout(slowToastId);
      setBusy(null);
    }
  };

  const Btn = ({ kind, icon: Icon, children }) => (
    <button
      onClick={() => handle(kind)}
      disabled={busy !== null}
      className="btn-ghost"
    >
      {busy === kind ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Icon className="h-4 w-4" />
      )}
      {children}
    </button>
  );

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Btn kind="pptx" icon={Download}>
          Download PPTX
        </Btn>
        <Btn kind="pdf" icon={FileDown}>
          Download PDF
        </Btn>
        <Btn kind="share" icon={Link2}>
          Share link
        </Btn>
      </div>
      <ShareModal
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        url={shareUrl}
      />
    </>
  );
}
