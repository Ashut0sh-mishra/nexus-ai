const features = [
  {
    id: 'research',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
      </svg>
    ),
    accent: 'from-violet-500 to-purple-600',
    accentBg: 'bg-violet-500/10',
    accentBorder: 'border-violet-500/20',
    accentText: 'text-violet-400',
    tag: 'Research',
    title: 'Smart Research',
    description:
      'Nexus scours the web and synthesises the most relevant facts, data, and insights for your topic — so your slides are always backed by solid knowledge.',
    bullets: ['Auto-sourced statistics', 'Competitor & trend analysis', 'Key facts highlighted'],
  },
  {
    id: 'design',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
      </svg>
    ),
    accent: 'from-pink-500 to-rose-600',
    accentBg: 'bg-pink-500/10',
    accentBorder: 'border-pink-500/20',
    accentText: 'text-pink-400',
    tag: 'Design',
    title: 'Pixel-Perfect Design',
    description:
      'Choose from dozens of premium templates. Every layout, colour palette, and typography pairing is crafted to look professional out of the box.',
    bullets: ['50+ pro templates', 'Brand kit support', 'Dark & light modes'],
  },
  {
    id: 'export',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
      </svg>
    ),
    accent: 'from-emerald-500 to-teal-600',
    accentBg: 'bg-emerald-500/10',
    accentBorder: 'border-emerald-500/20',
    accentText: 'text-emerald-400',
    tag: 'Export',
    title: 'One-Click Export',
    description:
      'Download your presentation as a polished PDF, PowerPoint, or share a live link instantly. Your audience can view it on any device, no software needed.',
    bullets: ['PDF, PPTX, Google Slides', 'Shareable live links', 'Offline-ready downloads'],
  },
]

export default function Features() {
  return (
    <section id="features" className="relative px-6 pb-28 pt-8">
      {/* Section header */}
      <div className="mx-auto mb-14 max-w-2xl text-center">
        <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-violet-400">
          Why Nexus?
        </p>
        <h2 className="text-3xl font-bold text-white sm:text-4xl">
          Everything you need,{' '}
          <span className="text-gradient">nothing you don't</span>
        </h2>
        <p className="mt-4 text-slate-400">
          Three core pillars power every presentation Nexus creates.
        </p>
      </div>

      {/* Cards grid */}
      <div className="mx-auto grid max-w-6xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((feature) => (
          <article
            key={feature.id}
            className="group relative card-glass rounded-2xl p-7 transition-all duration-300 hover:-translate-y-1 hover:border-violet-500/30 hover:shadow-xl hover:shadow-violet-900/20"
          >
            {/* Top accent line */}
            <div className={`absolute inset-x-0 top-0 h-px rounded-t-2xl bg-gradient-to-r ${feature.accent} opacity-60`} />

            {/* Icon badge */}
            <div className={`mb-5 inline-flex items-center justify-center rounded-xl border ${feature.accentBorder} ${feature.accentBg} p-3 ${feature.accentText} transition-transform duration-300 group-hover:scale-110`}>
              {feature.icon}
            </div>

            {/* Tag */}
            <span className={`mb-2 inline-block rounded-full border ${feature.accentBorder} ${feature.accentBg} px-2.5 py-0.5 text-xs font-medium ${feature.accentText}`}>
              {feature.tag}
            </span>

            {/* Title */}
            <h3 className="mt-1 text-lg font-semibold text-white">
              {feature.title}
            </h3>

            {/* Description */}
            <p className="mt-2 text-sm text-slate-400 leading-relaxed">
              {feature.description}
            </p>

            {/* Bullet list */}
            <ul className="mt-5 space-y-2">
              {feature.bullets.map((bullet) => (
                <li key={bullet} className="flex items-center gap-2.5 text-xs text-slate-400">
                  <svg
                    className={`h-3.5 w-3.5 flex-shrink-0 ${feature.accentText}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  {bullet}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}
