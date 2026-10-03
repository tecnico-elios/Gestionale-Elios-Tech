import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Cloud, MapPin, WarningCircle } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";

function isoToday() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
function daysFromToday(date) {
  if (!date) return null;
  const a = new Date(`${isoToday()}T12:00:00`);
  const b = new Date(`${date}T12:00:00`);
  if (Number.isNaN(b.getTime())) return null;
  return Math.round((b - a) / 86400000);
}
function siteAddress(site = {}, fallback = "") {
  if (fallback) return fallback;
  if (!site) return "";
  return [[site.indirizzo, site.civico].filter(Boolean).join(" "), site.cap, site.comune, site.provincia].filter(Boolean).join(", ");
}
function weatherText(code) {
  const c = Number(code);
  if (c === 0) return "Sereno";
  if ([1,2].includes(c)) return "Poco nuvoloso";
  if (c === 3) return "Nuvoloso";
  if ([45,48].includes(c)) return "Nebbia";
  if ([51,53,55,56,57].includes(c)) return "Pioviggine";
  if ([61,63,65,66,67,80,81,82].includes(c)) return "Pioggia";
  if ([71,73,75,77,85,86].includes(c)) return "Neve";
  if ([95,96,99].includes(c)) return "Temporali";
  return "Previsioni";
}

export default function InstallationWeather({ date, site, address = "", comune = "", provincia = "", cap = "", compact = false, className = "" }) {
  const [state, setState] = useState("idle");
  const [weather, setWeather] = useState(null);
  const [errorText, setErrorText] = useState("");
  const place = useMemo(() => siteAddress(site, address), [site, address]);
  const city = site?.comune || comune || "";
  const province = site?.provincia || provincia || "";
  const postal = site?.cap || cap || "";
  const delta = daysFromToday(date);

  useEffect(() => {
    let active = true;
    setWeather(null); setErrorText("");
    if (!date) { setState("no-date"); return () => { active = false; }; }
    if (!city && !place) { setState("no-place"); return () => { active = false; }; }
    if (delta === null || delta < 0) { setState("past"); return () => { active = false; }; }
    if (delta > 15) { setState("range"); return () => { active = false; }; }

    const run = async () => {
      setState("loading");
      try {
        const res = await axios.get(`${API}/weather-installation`, { params: { date, comune: city, provincia: province, cap: postal, address: place } });
        if (!active) return;
        if (res.data?.state === "range") { setState("range"); return; }
        if (res.data?.state === "past") { setState("past"); return; }
        if (res.data?.state !== "ok") throw new Error("Risposta meteo non valida");
        setWeather(res.data); setState("ok");
      } catch (e) {
        if (!active) return;
        const msg = e?.response?.data?.detail || e?.message || "Errore meteo";
        setErrorText(String(msg)); setState("error");
      }
    };
    run();
    return () => { active = false; };
  }, [date, place, city, province, postal, delta]);

  const shell = compact ? `rounded-lg border px-3 py-2 text-xs ${className}` : `rounded-xl border p-4 ${className}`;
  if (state === "no-date") return <div className={`${shell} border-slate-200 bg-slate-50 text-slate-600`}><b>Meteo:</b> seleziona la data dell’installazione.</div>;
  if (state === "no-place") return <div className={`${shell} border-amber-200 bg-amber-50 text-amber-900`}><b>Meteo:</b> manca il Comune della sede.</div>;
  if (state === "past") return <div className={`${shell} border-slate-200 bg-slate-50 text-slate-500`}><b>Meteo:</b> installazione già trascorsa.</div>;
  if (state === "range") return <div className={`${shell} border-blue-200 bg-blue-50 text-blue-900`}><div className="flex gap-2 items-start"><Cloud size={compact ? 16 : 20}/><div><b>Previsioni non ancora disponibili</b>{!compact && <div className="mt-1 text-sm">Saranno mostrate automaticamente quando l’installazione entrerà nei prossimi 16 giorni.</div>}</div></div></div>;
  if (state === "loading") return <div className={`${shell} border-blue-200 bg-blue-50 text-blue-900`}><b>Meteo:</b> aggiornamento previsioni…</div>;
  if (state === "error") return <div className={`${shell} border-amber-200 bg-amber-50 text-amber-900`}><div className="flex gap-2 items-start"><WarningCircle size={compact ? 16 : 20}/><div><b>Meteo non disponibile</b>{!compact && <div className="mt-1 text-sm">{errorText || "Impossibile recuperare le previsioni."}</div>}</div></div></div>;
  if (state !== "ok" || !weather) return null;
  const warning = Number(weather.rain || 0) >= 50 || Number(weather.wind || 0) >= 40 || [95,96,99].includes(Number(weather.code));
  return <div className={`${shell} ${warning ? "border-amber-300 bg-amber-50 text-amber-950" : "border-emerald-200 bg-emerald-50 text-emerald-950"}`}>
    <div className="flex items-start gap-2"><Cloud size={compact ? 17 : 22} weight="fill" className="shrink-0 mt-0.5"/><div className="min-w-0">
      <div className={compact ? "font-bold" : "font-black text-base"}>Meteo installazione · {weatherText(weather.code)}</div>
      <div className={compact ? "mt-0.5" : "mt-1 text-sm"}>{weather.min}–{weather.max} °C · pioggia {weather.rain ?? 0}% · vento max {weather.wind ?? 0} km/h</div>
      {!compact && weather.location && <div className="mt-1 text-xs opacity-75 flex items-center gap-1"><MapPin size={13}/>{weather.location}</div>}
      {warning && <div className={compact ? "mt-1 font-bold" : "mt-2 text-sm font-bold"}>⚠ Condizioni da verificare prima dell’intervento</div>}
    </div></div>
  </div>;
}
