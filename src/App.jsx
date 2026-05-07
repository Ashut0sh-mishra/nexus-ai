import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Features from './components/Features'

function App() {
  return (
    <div className="min-h-screen bg-[#060b18] text-white">
      <Navbar />
      <main>
        <Hero />
        <Features />
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 px-6 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-2 text-center sm:flex-row sm:justify-between">
          <span className="text-sm font-bold tracking-widest text-slate-500">NEXUS</span>
          <p className="text-xs text-slate-600">© 2026 Nexus. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

export default App
