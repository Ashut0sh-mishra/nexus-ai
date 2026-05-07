import { useState } from 'react'

export default function Hero() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGenerate = () => {
    if (!prompt.trim()) return
    setLoading(true)
    // Placeholder: will hook into API later
    setTimeout(() => setLoading(false), 2000)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleGenerate()
    }
  }

  return (
    <section
      id="hero"
      className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-24 pb-16"
    >
      {/* Background glow blobs */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-violet-700/20 blur-[120px] animate-pulse-slow" />
        <div className="absolute top-1/3 -left-32 h-[400px] w-[400px] rounded-full bg-indigo-800/15 blur-[100px]" />
        <div className="absolute bottom-0 right-0 h-[350px] w-[350px] rounded-full bg-purple-900/20 blur-[100px]" />
        {/* Subtle grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)',
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      {/* Badge */}
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-medium text-violet-300 backdrop-blur-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
        Powered by AI · Now in Beta
      </div>

      {/* Main heading */}
      <h1 className="text-center text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl lg:text-7xl max-w-4xl">
        <span className="text-gradient">Turn Any Idea</span>
        <br />
        <span className="text-white">Into a Stunning</span>
        <br />
        <span className="text-white">Presentation</span>
      </h1>

      {/* Subtitle */}
      <p className="mt-6 max-w-xl text-center text-lg text-slate-400 leading-relaxed">
        AI-powered slide generator — describe your topic and watch Nexus craft beautiful,
        professional slides in seconds.
      </p>

      {/* Prompt input */}
      <div className="mt-10 w-full max-w-2xl">
        <div className="relative rounded-2xl border border-white/10 bg-slate-900/60 p-1.5 shadow-2xl backdrop-blur-sm transition-all duration-300 focus-within:border-violet-500/50 focus-within:glow-purple">
          <div className="flex items-end gap-2">
            <textarea
              className="w-full resize-none rounded-xl bg-transparent px-4 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none leading-relaxed"
              rows={2}
              placeholder="e.g. A 10-slide pitch deck on the future of renewable energy for investors..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || loading}
              className="mb-1 mr-1 flex-shrink-0 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition-all duration-200 hover:from-violet-500 hover:to-indigo-500 hover:shadow-violet-500/40 hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
            >
              {loading ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                  </svg>
                  Generate
                </>
              )}
            </button>
          </div>
        </div>
        <p className="mt-2.5 text-center text-xs text-slate-600">
          Press <kbd className="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-slate-400 font-mono">Enter</kbd> to generate &middot; <kbd className="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-slate-400 font-mono">Shift+Enter</kbd> for new line
        </p>
      </div>

      {/* Social proof strip */}
      <div className="mt-12 flex items-center gap-6 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <svg className="h-4 w-4 text-violet-400" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
          4.9 / 5 rating
        </span>
        <span className="h-3 w-px bg-slate-700" />
        <span>10,000+ presentations created</span>
        <span className="h-3 w-px bg-slate-700" />
        <span>No credit card required</span>
      </div>
    </section>
  )
}
