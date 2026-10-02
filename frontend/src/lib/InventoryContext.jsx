import { API } from "./apiBase";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import axios from "axios";

/**
 * InventoryContext — snapshot condiviso dell'inventario locale Elios Tech.
 *
 * PRINCIPI:
 *  - Il database locale del Gestionale è la fonte operativa. Notion non è richiesto.
 *  - Il catalogo prodotti è unico; le giacenze vengono lette per deposito dal backend.
 *  - La cache serve solo a rendere immediate ricerca e scansione e viene aggiornata su richiesta.
 *  - Ogni movimento viene comunque validato dal backend prima di modificare le giacenze.
 */


const AUTO_REFRESH_MS = 10 * 60 * 1000; // 10 minutes

const InventoryContext = createContext(null);

export function InventoryProvider({ children }) {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshedAt, setRefreshedAt] = useState(null);
  const inflight = useRef(null);

  const refresh = useCallback(async () => {
    if (inflight.current) return inflight.current;
    setLoading(true);
    setError(null);
    const p = (async () => {
      try {
        const { data } = await axios.get(`${API}/inventory`);
        setItems(data.items || []);
        setCategories(data.categories || []);
        // Usa l'orologio del client: evita drift del clock del container/server
        // e riflette il momento reale in cui la sincronizzazione è avvenuta sul dispositivo.
        setRefreshedAt(new Date());
      } catch (e) {
        setError(
          e?.response?.data?.detail ||
            e?.message ||
            "Impossibile leggere il magazzino"
        );
      } finally {
        setLoading(false);
        inflight.current = null;
      }
    })();
    inflight.current = p;
    return p;
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const id = setInterval(refresh, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Build O(1) indices whenever items change.
  const indices = useMemo(() => {
    const bySku = new Map();
    const byId = new Map();
    for (const it of items) {
      byId.set(it.id, it);
      const c = (it.code || "").trim().toLowerCase();
      if (c) bySku.set(c, it);
    }
    return { bySku, byId };
  }, [items]);

  const lookupLocalBySku = useCallback(
    (code) => {
      const key = (code || "").trim().toLowerCase();
      if (!key) return null;
      return indices.bySku.get(key) || null;
    },
    [indices]
  );

  const getById = useCallback((id) => indices.byId.get(id) || null, [indices]);

  /**
   * Substring search over local cache. Fast — no Notion call.
   * Prioritises: exact SKU match > SKU-starts-with > name-starts-with > substring.
   * Returns up to `limit` results.
   */
  const searchLocal = useCallback(
    (query, limit = 8, opts = {}) => {
      const q = (query || "").trim().toLowerCase();
      if (!q || q.length < 1) return [];
      const partial = opts.partial !== false; // default true (retro-compat)
      const exact = [];
      const startsCode = [];
      const startsName = [];
      const substr = [];
      for (const it of items) {
        const code = (it.code || "").toLowerCase();
        const name = (it.name || "").toLowerCase();
        const cat = (it.category || "").toLowerCase();
        if (code === q) exact.push(it);
        else if (code && code.startsWith(q)) startsCode.push(it);
        else if (name.startsWith(q)) startsName.push(it);
        else if (partial && (name.includes(q) || code.includes(q) || cat.includes(q)))
          substr.push(it);
      }
      return [...exact, ...startsCode, ...startsName, ...substr].slice(0, limit);
    },
    [items]
  );

  const value = useMemo(
    () => ({
      items,
      categories,
      loading,
      error,
      refreshedAt,
      refresh,
      lookupLocalBySku,
      getById,
      searchLocal,
    }),
    [items, categories, loading, error, refreshedAt, refresh, lookupLocalBySku, getById, searchLocal]
  );

  return (
    <InventoryContext.Provider value={value}>
      {children}
    </InventoryContext.Provider>
  );
}

export function useInventoryCtx() {
  const ctx = useContext(InventoryContext);
  if (!ctx) {
    throw new Error("useInventoryCtx must be used inside <InventoryProvider>");
  }
  return ctx;
}
