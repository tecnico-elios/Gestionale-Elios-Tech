const fs = require("fs");
const path = require("path");

const file = path.join(__dirname, "..", "src", "components", "AppLayout.jsx");
let src = fs.readFileSync(file, "utf8");

if (src.includes("data-r55-page-header")) {
  console.log("[R55 header] gia applicato.");
  process.exit(0);
}

const oldPageInTopbar = `            <div className="hidden xl:flex items-center gap-2 ml-3 pl-4 border-l border-white/10 min-w-0">\n              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.12)]" />\n              <span className="text-xs text-slate-300 truncate">{currentTitle}</span>\n            </div>`;

const newPageInTopbar = `            <div className="r55-topbar-page" data-r55-page-header>\n              <div className="r55-topbar-page-icon"><CurrentPageIcon size={20} weight="duotone" /></div>\n              <div className="r55-topbar-page-copy">\n                <div className="r55-topbar-page-meta"><span className="r55-local-dot" />{pageMeta.eyebrow}</div>\n                <div className="r55-topbar-page-row">\n                  <span className="r55-topbar-page-title">{currentTitle}</span>\n                  <span className="r55-topbar-page-description">{pageMeta.description}</span>\n                </div>\n              </div>\n            </div>`;

if (!src.includes(oldPageInTopbar)) {
  throw new Error("R55: blocco pagina nella topbar non trovato");
}
src = src.replace(oldPageInTopbar, newPageInTopbar);

src = src.replace(
  '<header className="et-topbar">',
  '<header className={`et-topbar r55-topbar r55-section-${currentSection}`}>',
);

const bannerStart = '          <section className="r52-page-banner" aria-label={`Sezione ${currentTitle}`}>\n';
const hostStart = '          <div className={`et-page-host r52-page-host r52-route-${routeToken}`} data-r52-route={routeToken}>\n';
const start = src.indexOf(bannerStart);
const host = src.indexOf(hostStart, start);
if (start === -1 || host === -1) {
  throw new Error("R55: banner pagina o contenitore pagina non trovato");
}
src = src.slice(0, start) + src.slice(host);

fs.writeFileSync(file, src, "utf8");
console.log("[R55 header] testata pagina unificata nella barra superiore.");
