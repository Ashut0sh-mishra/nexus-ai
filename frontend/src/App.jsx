import { Routes, Route, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Home from "./pages/Home.jsx";
import Generator from "./pages/Generator.jsx";
import Editor from "./pages/Editor.jsx";
import Presenter from "./pages/Presenter.jsx";
import SharedSlide from "./pages/SharedSlide.jsx";
import Settings from "./pages/Settings.jsx";
import Gallery from "./pages/Gallery.jsx";

export default function App() {
  const { pathname } = useLocation();
  const isImmersive = pathname.startsWith("/present/");

  return (
    <div className="min-h-screen flex flex-col">
      {!isImmersive && <Navbar />}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/generate/:taskId" element={<Generator />} />
          <Route path="/editor/:taskId" element={<Editor />} />
          <Route path="/present/:taskId" element={<Presenter />} />
          <Route path="/share/:token" element={<SharedSlide />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </main>
      {!isImmersive && <Footer />}
    </div>
  );
}
