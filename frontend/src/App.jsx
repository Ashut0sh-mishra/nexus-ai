import { Routes, Route, useLocation, matchPath } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Home from "./pages/Home.jsx";
import Generator from "./pages/Generator.jsx";
import DeckWorkspace from "./pages/DeckWorkspace.jsx";
import Presenter from "./pages/Presenter.jsx";
import SharedSlide from "./pages/SharedSlide.jsx";
import Gallery from "./pages/Gallery.jsx";

// Phase 6M: app routes hide the marketing Footer so the generated-deck
// experience reads as a real product workspace, not a passive landing page.
const APP_ROUTE_PATTERNS = [
  "/generate/:taskId",
  "/deck/:taskId",
  "/present/:taskId",
  "/gallery",
];

function AppChrome() {
  const { pathname } = useLocation();
  const isAppRoute = APP_ROUTE_PATTERNS.some((p) => matchPath(p, pathname));
  // Presenter is fullscreen — hide both navbar and footer there.
  const isPresenter = !!matchPath("/present/:taskId", pathname);
  return (
    <>
      {!isPresenter && <Navbar />}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/generate/:taskId" element={<Generator />} />
          <Route path="/deck/:taskId" element={<DeckWorkspace />} />
          <Route path="/present/:taskId" element={<Presenter />} />
          <Route path="/share/:token" element={<SharedSlide />} />
          {/* Phase 6AF: visual-regression smoke gallery. Renders one of every
              canonical layout side-by-side so the Playwright snapshot suite
              has a deterministic surface to diff against. */}
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </main>
      {!isAppRoute && <Footer />}
    </>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <AppChrome />
    </div>
  );
}
