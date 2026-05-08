import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import Hero from "../components/Hero.jsx";
import Capabilities from "../components/Capabilities.jsx";
import Features from "../components/Features.jsx";
import Templates from "../components/Templates.jsx";

export default function Home() {
  const { hash } = useLocation();
  // When arriving on Home with a hash (e.g. /#features after clicking
  // Features from /settings), scroll the matching section into view once
  // the page has mounted and laid out.
  useEffect(() => {
    if (!hash) {
      window.scrollTo({ top: 0, behavior: "auto" });
      return;
    }
    const id = hash.replace(/^#/, "");
    // Defer one frame so the section components have mounted.
    const t = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
    return () => clearTimeout(t);
  }, [hash]);

  return (
    <>
      <Hero />
      <Capabilities />
      <Templates />
      <Features />
    </>
  );
}
