export default function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      {/* Backdrop blur bar */}
      <div className="border-b border-white/5 bg-[#060b18]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg glow-purple-sm">
              <svg
                className="h-4 w-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
                />
              </svg>
            </div>
            <span className="text-xl font-bold tracking-widest text-white">
              NEXUS
            </span>
          </div>

          {/* Nav links + CTA */}
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-slate-400 hover:text-white transition-colors duration-200">
              Features
            </a>
            <a href="#hero" className="text-sm text-slate-400 hover:text-white transition-colors duration-200">
              How it works
            </a>
            <a href="#features" className="text-sm text-slate-400 hover:text-white transition-colors duration-200">
              Pricing
            </a>
          </nav>

          {/* Get Started button */}
          <button className="relative inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-lg transition-all duration-200 hover:from-violet-500 hover:to-indigo-500 hover:shadow-violet-500/30 hover:shadow-xl active:scale-95 glow-purple-sm">
            Get Started
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </button>

        </div>
      </div>
    </header>
  )
}
