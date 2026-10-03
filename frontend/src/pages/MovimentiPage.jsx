import { API } from "../lib/apiBase";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  ArrowSquareIn,
  ArrowSquareOut,
  ArrowsClockwise,
  MagnifyingGlass,
  Barcode,
  CaretLeft,
  CaretRight,
  CalendarBlank,
} from "@phosphor-icons/react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { fetchServerToday } from "../lib/tz";


const CACHE_TTL_MS = 60 * 1000; // 60s — refresh forced by button

const MONTH_NAMES_IT = [
  "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
  "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
];

const currentMonthKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

const parseKey = (key) => {
  const [y, m] = key.split("-").map((n) => parseInt(n, 10));
  return { year: y, month: m };
};

const formatMonthLabel = (key) => {
  const { year, month } = parseKey(key);
  return `${MONTH_NAMES_IT[month - 1]} ${year}`;
};

const shiftMonth = (key, delta) => {
  const { year, month } = parseKey(key);
  const total = year * 12 + (month - 1) + delta;
  const y = Math.floor(total / 12);
  const m = (total % 12) + 1;
  return `${y}-${String(m).padStart(2, "0")}`;
};

/**
 * MovimentiPage — F6 (ottimizzazione)
 * Carica UN mese alla volta da Notion (filtro server-side via /api/movimenti?month=YYYY-MM).
 * Cache per-mese in memoria (TTL 60s). Il tasto Aggiorna forza un refetch live del mese
 * selezionato. I dati operativi sono salvati nel database locale del gestionale.
 */
export default function MovimentiPage() {
  const [monthKey, setMonthKey] = useState(currentMonthKey());
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [warehouseFilter, setWarehouseFilter] = useState("all");
  const [maxShown, setMaxShown] = useState(500);
  const cacheRef = useRef(new Map()); // key: 'YYYY-MM' -> { items, at }

  // Load Admin settings once — movimenti.max_shown + auto_open_current_month
  useEffect(() => {
    (async () => {
      try {
        // F8: derivo il mese corrente dall'ora del server nel tz configurato.
        const serverDate = await fetchServerToday();
        const serverMonth = serverDate ? serverDate.slice(0, 7) : currentMonthKey();
        const { data } = await axios.get(`${API}/settings`);
        const limit = parseInt(data?.movimenti?.max_shown ?? 500, 10);
        if (limit > 0) setMaxShown(limit);
        const autoOpen = data?.movimenti?.auto_open_current_month !== false;
        if (autoOpen) setMonthKey(serverMonth);
      } catch {}
    })();
  }, []);

  const load = useCallback(
    async (key, { force = false } = {}) => {
      const cached = cacheRef.current.get(key);
      if (!force && cached && Date.now() - cached.at < CACHE_TTL_MS) {
        setItems(cached.items);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const { data } = await axios.get(`${API}/movimenti`, {
          params: { month: key, limit: maxShown, ...(warehouseFilter !== "all" ? { warehouse_id: warehouseFilter } : {}) },
        });
        const rows = data.items || [];
        cacheRef.current.set(key, { items: rows, at: Date.now() });
        setItems(rows);
      } catch (e) {
        setError(
          e?.response?.data?.detail || e?.message || "Errore lettura movimenti"
        );
      } finally {
        setLoading(false);
      }
    },
    [maxShown, warehouseFilter]
  );

  useEffect(() => {
    load(monthKey);
  }, [monthKey, load]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    return items.filter((it) => {
      if (typeFilter !== "all" && it.type !== typeFilter) return false;
      if (!query) return true;
      return (
        (it.product || "").toLowerCase().includes(query) ||
        (it.serial_or_code || "").toLowerCase().includes(query) ||
        (it.cliente || "").toLowerCase().includes(query) ||
        (it.taken_by || "").toLowerCase().includes(query)
      );
    });
  }, [items, q, typeFilter]);

  const isCurrentMonth = monthKey === currentMonthKey();
  const showClient = typeFilter !== "arrivo";

  return (
    <div
      className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-4"
      data-testid="movimenti-page"
    >
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <div className="et-eyebrow">Cronologia · Gestionale</div>
          <h1 className="et-page-heading text-3xl sm:text-4xl mt-1">
            Movimenti
          </h1>

        </div>
        <button
          type="button"
          onClick={() => load(monthKey, { force: true })}
          disabled={loading}
          className="h-10 px-4 rounded-md text-sm flex items-center gap-2 et-btn-primary disabled:opacity-60"
          data-testid="movimenti-refresh"
        >
          <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} />
          Aggiorna
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="et-card p-3"><div className="text-[10px] uppercase font-bold text-slate-400">Movimenti</div><div className="text-2xl font-black text-slate-900 mt-1">{items.length}</div></div>
        <div className="et-card p-3"><div className="text-[10px] uppercase font-bold text-emerald-600">Entrate</div><div className="text-2xl font-black text-emerald-700 mt-1">{items.filter(x=>x.type === "arrivo").length}</div></div>
        <div className="et-card p-3"><div className="text-[10px] uppercase font-bold text-blue-600">Uscite</div><div className="text-2xl font-black text-blue-700 mt-1">{items.filter(x=>x.type === "spedizione").length}</div></div>
        <div className="et-card p-3"><div className="text-[10px] uppercase font-bold text-slate-400">Periodo</div><div className="text-base font-black text-slate-900 mt-2">{formatMonthLabel(monthKey)}</div></div>
      </div>

      {/* Month selector */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setMonthKey((k) => shiftMonth(k, -1))}
          className="h-10 w-10 inline-flex items-center justify-center border border-slate-200 rounded-md bg-white text-slate-600 hover:text-slate-900 hover:border-slate-300"
          data-testid="month-prev"
          aria-label="Mese precedente"
        >
          <CaretLeft size={16} weight="bold" />
        </button>
        <label
          className="h-10 inline-flex items-center gap-2 px-3 border border-slate-200 rounded-md bg-white cursor-pointer"
          data-testid="month-picker-wrapper"
        >
          <CalendarBlank size={16} className="text-slate-500" />
          <span
            className="text-sm font-semibold text-slate-900 min-w-[140px]"
            data-testid="month-label"
          >
            {formatMonthLabel(monthKey)}
          </span>
          <input
            type="month"
            value={monthKey}
            onChange={(e) => setMonthKey(e.target.value || currentMonthKey())}
            className="absolute opacity-0 w-0 h-0 p-0 m-0"
            data-testid="month-picker"
          />
        </label>
        <button
          type="button"
          onClick={() => setMonthKey((k) => shiftMonth(k, 1))}
          disabled={isCurrentMonth}
          className="h-10 w-10 inline-flex items-center justify-center border border-slate-200 rounded-md bg-white text-slate-600 hover:text-slate-900 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed"
          data-testid="month-next"
          aria-label="Mese successivo"
        >
          <CaretRight size={16} weight="bold" />
        </button>
        {!isCurrentMonth && (
          <button
            type="button"
            onClick={() => setMonthKey(currentMonthKey())}
            className="h-10 px-3 text-sm text-slate-600 hover:text-slate-900 underline"
            data-testid="month-current"
          >
            Torna a {formatMonthLabel(currentMonthKey())}
          </button>
        )}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <MagnifyingGlass
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={typeFilter === "arrivo" ? "Cerca per prodotto o seriale…" : "Cerca per prodotto, seriale, cliente…"}
            className="pl-10 h-10"
            data-testid="movimenti-search"
          />
        </div>
        <select
          value={warehouseFilter}
          onChange={(e) => { setWarehouseFilter(e.target.value); cacheRef.current.clear(); }}
          className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
          aria-label="Filtra per magazzino"
        >
          <option value="all">Tutti i magazzini</option>
          <option value="elios-tech">Magazzino Elios Tech</option>
          <option value="verona">Magazzino Verona</option>
        </select>
        <div className="flex gap-1 bg-white border border-slate-200 rounded-md p-1">
          {[
            { id: "all", label: "Tutti", testid: "filter-all" },
            { id: "arrivo", label: "📥 Arrivi", testid: "filter-arrivi" },
            { id: "spedizione", label: "📤 Spedizioni", testid: "filter-spedizioni" },
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setTypeFilter(f.id)}
              className={`h-8 px-3 text-sm rounded font-medium transition-colors ${
                typeFilter === f.id
                  ? "bg-[#1A456B] text-white shadow-sm"
                  : "text-slate-600 hover:bg-amber-50 hover:text-slate-900"
              }`}
              data-testid={f.testid}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="border border-red-200 bg-red-50 text-red-700 p-4 rounded-md text-sm">
          {error}
        </div>
      )}

      {loading && !items.length ? (
        <div className="text-slate-500 py-12 text-center text-sm">
          Caricamento movimenti di {formatMonthLabel(monthKey)}…
        </div>
      ) : (
        <div className="et-card-elevated rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="movimenti-table">
              <thead className="bg-[#1A456B] border-b border-[#163B5C] text-white">
                <tr>
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase">Data</th>
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase">Tipo</th>
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase">Magazzino</th>
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase">Prodotto</th>
                  <th className="text-right px-3 py-2 font-semibold text-white/90 text-xs uppercase">Q.tà</th>
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase">Seriale / Codice</th>
                  {showClient && <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase hidden md:table-cell">Cliente</th>}
                  <th className="text-left px-3 py-2 font-semibold text-white/90 text-xs uppercase hidden md:table-cell">Operatore</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={showClient ? 8 : 7} className="text-center py-10 text-slate-400 text-sm">
                      Nessun movimento in {formatMonthLabel(monthKey)}.
                    </td>
                  </tr>
                ) : (
                  filtered.map((m, idx) => (
                    <tr
                      key={m.id || idx}
                      className="hover:bg-[#1A456B]/[0.035] transition-colors"
                      data-testid={`mov-row-${idx}`}
                    >
                      <td className="px-3 py-2 font-mono-tight text-xs text-slate-600 whitespace-nowrap">
                        {m.date || "—"}
                      </td>
                      <td className="px-3 py-2">
                        {m.type === "arrivo" ? (
                          <Badge className="bg-emerald-600 hover:bg-emerald-700">
                            <ArrowSquareIn size={12} weight="bold" className="mr-1" /> Arrivo
                          </Badge>
                        ) : (
                          <Badge className="bg-blue-600 hover:bg-blue-700">
                            <ArrowSquareOut size={12} weight="bold" className="mr-1" /> Uscita
                          </Badge>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600 whitespace-nowrap">{m.warehouse_name || (m.warehouse_id === "verona" ? "Magazzino Verona" : "Magazzino Elios Tech")}</td>
                      <td className="px-3 py-2 font-medium text-slate-900">{m.product || "—"}</td>
                      <td className="px-3 py-2 text-right font-mono-tight font-semibold text-slate-900">
                        {m.quantity ?? "—"}{" "}
                        <span className="text-slate-400 text-xs font-normal">{m.unit}</span>
                      </td>
                      <td className="px-3 py-2 font-mono-tight text-xs text-slate-700">
                        {m.serial_or_code ? (
                          <span className="inline-flex items-center gap-1">
                            <Barcode size={12} className="text-slate-400" />
                            {m.serial_or_code}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      {showClient && <td className="px-3 py-2 text-slate-600 hidden md:table-cell">
                        {m.type === "spedizione" ? (m.cliente || "—") : "—"}
                      </td>}
                      <td className="px-3 py-2 text-slate-600 hidden md:table-cell">
                        {m.taken_by || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
