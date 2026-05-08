import { useEffect, useState } from "react";
import {
  Palette,
  Image as ImageIcon,
  Key,
  Webhook,
  Trash2,
  Plus,
  RotateCw,
  Copy,
  Check,
  Send,
  Upload,
} from "lucide-react";
import {
  brandKitsApi,
  assetsApi,
  apiKeysApi,
  webhooksApi,
} from "../utils/api.js";

const TABS = [
  { id: "brand", label: "Brand Kits", icon: Palette },
  { id: "assets", label: "Asset Library", icon: ImageIcon },
  { id: "keys", label: "API Keys", icon: Key },
  { id: "hooks", label: "Webhooks", icon: Webhook },
];

export default function Settings() {
  const [tab, setTab] = useState("brand");

  return (
    <section className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-nexus-muted mt-1">
          Manage brand kits, assets, API keys and webhooks for your workspace.
        </p>
      </header>

      <div className="flex gap-2 border-b border-nexus-border mb-8 overflow-x-auto">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm border-b-2 transition whitespace-nowrap ${
              tab === id
                ? "border-nexus-accent text-nexus-text"
                : "border-transparent text-nexus-muted hover:text-nexus-text"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "brand" && <BrandKitsPanel />}
      {tab === "assets" && <AssetsPanel />}
      {tab === "keys" && <ApiKeysPanel />}
      {tab === "hooks" && <WebhooksPanel />}
    </section>
  );
}

// ─── Brand kits ─────────────────────────────────────────────────────────
function BrandKitsPanel() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    name: "",
    palette: "#6366f1,#8b5cf6,#ec4899",
    fonts: "Inter,Inter",
    industry: "",
    audience: "",
    tone: "",
    is_default: false,
  });

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await brandKitsApi.list();
      setItems(data || []);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    refresh();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    const payload = {
      name: form.name.trim(),
      palette: form.palette
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      fonts: form.fonts
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      industry: form.industry || null,
      audience: form.audience || null,
      tone: form.tone || null,
      is_default: form.is_default,
    };
    if (!payload.name) return;
    await brandKitsApi.create(payload);
    setForm({ ...form, name: "" });
    refresh();
  };

  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <form onSubmit={submit} className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold">New brand kit</h3>
        <Field label="Name">
          <input
            className="input"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Acme Corp"
            required
          />
        </Field>
        <Field label="Palette (comma-separated hex)">
          <input
            className="input"
            value={form.palette}
            onChange={(e) => setForm({ ...form, palette: e.target.value })}
          />
        </Field>
        <Field label="Fonts (heading,body)">
          <input
            className="input"
            value={form.fonts}
            onChange={(e) => setForm({ ...form, fonts: e.target.value })}
          />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Industry">
            <input
              className="input"
              value={form.industry}
              onChange={(e) => setForm({ ...form, industry: e.target.value })}
            />
          </Field>
          <Field label="Audience">
            <input
              className="input"
              value={form.audience}
              onChange={(e) => setForm({ ...form, audience: e.target.value })}
            />
          </Field>
          <Field label="Tone">
            <input
              className="input"
              value={form.tone}
              onChange={(e) => setForm({ ...form, tone: e.target.value })}
            />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-nexus-muted">
          <input
            type="checkbox"
            checked={form.is_default}
            onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
          />
          Set as default
        </label>
        <button type="submit" className="btn-primary inline-flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create
        </button>
      </form>

      <div className="space-y-3">
        {loading ? (
          <p className="text-nexus-muted">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-nexus-muted">No brand kits yet.</p>
        ) : (
          items.map((k) => (
            <div key={k.id} className="card p-5 flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-semibold">{k.name}</h4>
                  {k.is_default && (
                    <span className="text-xs px-2 py-0.5 rounded bg-nexus-accent/20 text-nexus-accent">
                      default
                    </span>
                  )}
                </div>
                <div className="flex gap-1 mt-2">
                  {(k.palette || []).slice(0, 8).map((c, i) => (
                    <span
                      key={i}
                      className="h-6 w-6 rounded border border-nexus-border"
                      style={{ background: c }}
                      title={c}
                    />
                  ))}
                </div>
                <p className="text-xs text-nexus-muted mt-2">
                  {[k.industry, k.audience, k.tone].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>
              <button
                onClick={async () => {
                  await brandKitsApi.remove(k.id);
                  refresh();
                }}
                className="text-nexus-muted hover:text-red-400"
                aria-label="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Assets ────────────────────────────────────────────────────────────
function AssetsPanel() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const data = await assetsApi.list();
    setItems(data || []);
  };
  useEffect(() => {
    refresh();
  }, []);

  const onFiles = async (files) => {
    if (!files || !files.length) return;
    setBusy(true);
    try {
      for (const f of files) await assetsApi.upload(f);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <label className="card p-8 border-dashed border-2 border-nexus-border block text-center cursor-pointer hover:border-nexus-borderHi transition">
        <Upload className="h-6 w-6 mx-auto mb-2 text-nexus-muted" />
        <p className="text-sm text-nexus-muted">
          {busy ? "Uploading..." : "Drop files or click to upload (png, jpg, svg, webp — 10 MB max)"}
        </p>
        <input
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(e) => onFiles(e.target.files)}
        />
      </label>

      {items.length === 0 ? (
        <p className="text-nexus-muted">No assets yet.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {items.map((a) => (
            <div
              key={a.id}
              className="card p-2 group relative overflow-hidden"
            >
              <img
                src={a.file_url}
                alt={a.name}
                className="w-full h-32 object-cover rounded"
              />
              <p className="text-xs truncate mt-2 text-nexus-muted">{a.name}</p>
              <button
                onClick={async () => {
                  await assetsApi.remove(a.id);
                  refresh();
                }}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 bg-red-500/80 text-white rounded p-1.5 transition"
                aria-label="Delete"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── API keys ──────────────────────────────────────────────────────────
function ApiKeysPanel() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [secret, setSecret] = useState(null);
  const [copied, setCopied] = useState(false);

  const refresh = async () => setItems((await apiKeysApi.list()) || []);
  useEffect(() => {
    refresh();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const res = await apiKeysApi.create({ name: name.trim() });
    setSecret(res.secret);
    setName("");
    refresh();
  };

  return (
    <div className="space-y-6">
      {secret && (
        <div className="card p-5 border-amber-500/40 bg-amber-500/5">
          <p className="text-sm text-amber-300 mb-2 font-semibold">
            Copy this secret now — it won't be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-nexus-bg px-3 py-2 rounded text-sm font-mono break-all">
              {secret}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(secret);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="btn-secondary !py-2 !px-3"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
            <button onClick={() => setSecret(null)} className="btn-secondary !py-2 !px-3">
              Done
            </button>
          </div>
        </div>
      )}

      <form onSubmit={create} className="card p-5 flex gap-3 items-end">
        <Field label="Key name" className="flex-1">
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Production"
          />
        </Field>
        <button type="submit" className="btn-primary inline-flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create key
        </button>
      </form>

      {items.length === 0 ? (
        <p className="text-nexus-muted">No API keys yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map((k) => (
            <div key={k.id} className="card p-4 flex items-center justify-between">
              <div>
                <div className="font-medium">{k.name}</div>
                <code className="text-xs text-nexus-muted font-mono">
                  {k.key_prefix}••••••••
                </code>
                {k.revoked_at && (
                  <span className="ml-2 text-xs text-red-400">revoked</span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    const r = await apiKeysApi.rotate(k.id);
                    setSecret(r.secret);
                    refresh();
                  }}
                  disabled={!!k.revoked_at}
                  className="btn-secondary !py-2 !px-3 inline-flex items-center gap-1"
                >
                  <RotateCw className="h-3 w-3" /> Rotate
                </button>
                <button
                  onClick={async () => {
                    await apiKeysApi.revoke(k.id);
                    refresh();
                  }}
                  disabled={!!k.revoked_at}
                  className="btn-secondary !py-2 !px-3 text-red-400 hover:text-red-300"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Webhooks ──────────────────────────────────────────────────────────
const ALL_EVENTS = ["deck.created", "deck.completed", "deck.failed", "slide.updated"];

function WebhooksPanel() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({
    url: "",
    events: ["deck.completed"],
  });
  const [secret, setSecret] = useState(null);

  const refresh = async () => setItems((await webhooksApi.list()) || []);
  useEffect(() => {
    refresh();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!form.url.trim()) return;
    const res = await webhooksApi.create(form);
    if (res.secret) setSecret(res.secret);
    setForm({ url: "", events: ["deck.completed"] });
    refresh();
  };

  const toggleEvent = (ev) => {
    setForm((f) => ({
      ...f,
      events: f.events.includes(ev)
        ? f.events.filter((x) => x !== ev)
        : [...f.events, ev],
    }));
  };

  return (
    <div className="space-y-6">
      {secret && (
        <div className="card p-5 border-amber-500/40 bg-amber-500/5">
          <p className="text-sm text-amber-300 mb-2 font-semibold">
            Webhook signing secret — store now (X-Nexus-Signature: sha256=...).
          </p>
          <code className="block bg-nexus-bg px-3 py-2 rounded text-sm font-mono break-all">
            {secret}
          </code>
          <button onClick={() => setSecret(null)} className="btn-secondary mt-3 !py-2 !px-3">
            Done
          </button>
        </div>
      )}

      <form onSubmit={create} className="card p-5 space-y-4">
        <Field label="Endpoint URL">
          <input
            type="url"
            className="input"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            placeholder="https://example.com/hooks/nexus"
            required
          />
        </Field>
        <div>
          <label className="block text-xs uppercase tracking-wide text-nexus-muted mb-2">
            Events
          </label>
          <div className="flex flex-wrap gap-2">
            {ALL_EVENTS.map((ev) => (
              <button
                key={ev}
                type="button"
                onClick={() => toggleEvent(ev)}
                className={`text-xs px-3 py-1.5 rounded-full border transition ${
                  form.events.includes(ev)
                    ? "border-nexus-accent text-nexus-accent bg-nexus-accent/10"
                    : "border-nexus-border text-nexus-muted hover:text-nexus-text"
                }`}
              >
                {ev}
              </button>
            ))}
          </div>
        </div>
        <button type="submit" className="btn-primary inline-flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create webhook
        </button>
      </form>

      {items.length === 0 ? (
        <p className="text-nexus-muted">No webhooks yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map((w) => (
            <div key={w.id} className="card p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <code className="block text-sm font-mono truncate">{w.url}</code>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(w.events || []).map((e) => (
                      <span
                        key={e}
                        className="text-xs px-2 py-0.5 rounded bg-nexus-surface text-nexus-muted"
                      >
                        {e}
                      </span>
                    ))}
                  </div>
                  {w.last_status && (
                    <p className="text-xs text-nexus-muted mt-1">
                      last: {w.last_status}
                      {w.failure_count ? ` · ${w.failure_count} failures` : ""}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={async () => {
                      const r = await webhooksApi.test(w.id);
                      alert(`Test: ${r.status || "sent"}`);
                      refresh();
                    }}
                    className="btn-secondary !py-2 !px-3 inline-flex items-center gap-1"
                  >
                    <Send className="h-3 w-3" /> Test
                  </button>
                  <button
                    onClick={async () => {
                      await webhooksApi.remove(w.id);
                      refresh();
                    }}
                    className="btn-secondary !py-2 !px-3 text-red-400 hover:text-red-300"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Shared ────────────────────────────────────────────────────────────
function Field({ label, children, className = "" }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-xs uppercase tracking-wide text-nexus-muted mb-1.5">
        {label}
      </span>
      {children}
    </label>
  );
}
