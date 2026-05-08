import { useRef, useState } from "react";
import {
  FileText,
  FileSpreadsheet,
  FileJson,
  FileType2,
  Upload,
  Loader2,
  X,
  AlertCircle,
} from "lucide-react";
import { api } from "../utils/api.js";

const ACCEPT = ".csv,.xlsx,.xls,.json,.pdf,.docx,.pptx,.txt,.md";
const MAX_FILES = 5;

const ICONS = {
  csv: FileSpreadsheet,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  json: FileJson,
  pdf: FileText,
  docx: FileText,
  pptx: FileText,
  txt: FileType2,
  md: FileType2,
};

function fmtSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * Drag-and-drop / click-to-pick uploader. Streams each file to POST /api/upload
 * and emits the resulting metadata via `onChange(files)`. Surfaces parser
 * warnings per-file and shows a structured-data badge when the parser
 * extracted tabular content.
 */
export default function FileUpload({ files = [], onChange, disabled = false }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  function pick() {
    if (disabled || busy) return;
    inputRef.current?.click();
  }

  async function uploadOne(file) {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post("/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120_000,
    });
    return data;
  }

  async function handleFiles(list) {
    setError("");
    if (!list || list.length === 0) return;
    const remaining = Math.max(0, MAX_FILES - files.length);
    const picked = Array.from(list).slice(0, remaining);
    if (picked.length === 0) {
      setError(`Up to ${MAX_FILES} files.`);
      return;
    }
    setBusy(true);
    const next = [...files];
    for (const f of picked) {
      try {
        const meta = await uploadOne(f);
        next.push(meta);
        onChange?.(next.slice());
      } catch (err) {
        setError(
          err?.response?.data?.detail ||
            `Failed to upload ${f.name}.`,
        );
      }
    }
    setBusy(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    if (disabled || busy) return;
    handleFiles(e.dataTransfer?.files);
  }

  function remove(fileId) {
    onChange?.(files.filter((f) => f.file_id !== fileId));
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={pick}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !busy) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        disabled={disabled || busy}
        className={`flex w-full items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-2 text-xs transition ${
          dragOver
            ? "border-accent-purple bg-accent-purple/10 text-accent-purple"
            : "border-nexus-border bg-nexus-card/40 text-nexus-muted hover:border-nexus-borderHi hover:text-nexus-text"
        } disabled:opacity-50`}
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Upload className="h-3.5 w-3.5" />
        )}
        <span>
          {busy
            ? "Uploading…"
            : "Attach files for context (CSV, XLSX, PDF, DOCX, PPTX, JSON, TXT, MD)"}
        </span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {error && (
        <div className="flex items-center gap-1.5 rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
          <AlertCircle className="h-3 w-3" />
          {error}
        </div>
      )}

      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((f) => {
            const Icon = ICONS[f.file_type] || FileText;
            return (
              <li
                key={f.file_id}
                className="flex items-center gap-2 rounded-md border border-nexus-border bg-nexus-card/60 px-2 py-1.5 text-xs"
              >
                <Icon className="h-3.5 w-3.5 shrink-0 text-nexus-muted" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-nexus-text">{f.filename}</div>
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-nexus-dim">
                    <span>{f.file_type}</span>
                    <span>·</span>
                    <span>{fmtSize(f.file_size)}</span>
                    {f.has_structured_data && (
                      <>
                        <span>·</span>
                        <span className="text-accent-teal">structured</span>
                      </>
                    )}
                    {f.error && (
                      <>
                        <span>·</span>
                        <span className="text-amber-400" title={f.error}>
                          parser warning
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove(f.file_id)}
                  aria-label="Remove file"
                  className="text-nexus-muted hover:text-red-400"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
