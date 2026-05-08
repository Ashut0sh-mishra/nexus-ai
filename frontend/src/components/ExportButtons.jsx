import { useState } from "react";
import toast from "react-hot-toast";
import { Download, FileDown, Link2, Loader2 } from "lucide-react";
import { useExport } from "../hooks/useExport.js";
import ShareModal from "./ShareModal.jsx";

export default function ExportButtons({ taskId, theme }) {
  const { exportPptx, exportPdf, createShare } = useExport();
  const [busy, setBusy] = useState(null);
  const [shareUrl, setShareUrl] = useState(null);
  const [shareOpen, setShareOpen] = useState(false);

  const handle = async (kind) => {
    setBusy(kind);
    try {
      if (kind === "pptx") {
        const { download_url } = await exportPptx(taskId, theme);
        window.open(download_url, "_blank", "noopener");
        toast.success("PPTX ready.");
      } else if (kind === "pdf") {
        const { download_url } = await exportPdf(taskId, theme);
        window.open(download_url, "_blank", "noopener");
        toast.success("PDF ready.");
      } else if (kind === "share") {
        const { share_url } = await createShare(taskId);
        setShareUrl(share_url);
        setShareOpen(true);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Export failed.");
    } finally {
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
