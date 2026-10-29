from pathlib import Path

# ---------------- backend/server.py ----------------
p = Path('backend/server.py')
text = p.read_text(encoding='utf-8')

old_sig = '@api_router.get("/weather-installation", dependencies=[Depends(dep_current_user)])\nasync def weather_installation(date: str, comune: str = "", provincia: str = "", cap: str = "", address: str = ""):'
new_sig = '''@api_router.get("/address-search", dependencies=[Depends(dep_current_user)])
async def address_search(q: str):
    """Autocomplete indirizzi italiani tramite Photon/OSM. Restituisce coordinate da riusare per Maps e meteo."""
    query = " ".join((q or "").strip().split())
    if len(query) < 4:
        return {"items": []}

    timeout = httpx.Timeout(6.0, connect=4.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(
                "https://photon.komoot.io/api/",
                params={"q": query, "limit": 6, "lang": "it"},
                headers={"User-Agent": "Gestionale-Elios-Tech/1.0 address-autocomplete"},
            )
            r.raise_for_status()
            features = (r.json() or {}).get("features") or []
    except httpx.TimeoutException:
        raise HTTPException(504, "Ricerca indirizzo non raggiungibile: timeout")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Ricerca indirizzo non raggiungibile: {type(e).__name__}")

    items = []
    seen = set()
    for feature in features:
        props = feature.get("properties") or {}
        coords = ((feature.get("geometry") or {}).get("coordinates") or [])
        if len(coords) < 2:
            continue
        countrycode = str(props.get("countrycode") or "").upper()
        if countrycode and countrycode != "IT":
            continue

        street = props.get("street") or props.get("name") or ""
        housenumber = props.get("housenumber") or ""
        postcode = props.get("postcode") or ""
        city = props.get("city") or props.get("town") or props.get("village") or props.get("municipality") or ""
        province = props.get("county") or props.get("state") or ""
        country = props.get("country") or "Italia"

        first = " ".join([str(street).strip(), str(housenumber).strip()]).strip()
        locality = " ".join([str(postcode).strip(), str(city).strip()]).strip()
        parts = [x for x in [first, locality, str(province).strip(), str(country).strip()] if x]
        # evita ripetizioni tipo "Piacenza, Piacenza"
        clean_parts = []
        for part in parts:
            if not clean_parts or part.casefold() != clean_parts[-1].casefold():
                clean_parts.append(part)
        label = ", ".join(clean_parts) or str(props.get("name") or query)

        lat = float(coords[1]); lon = float(coords[0])
        key = (round(lat, 6), round(lon, 6), label.casefold())
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "label": label,
            "latitude": lat,
            "longitude": lon,
            "comune": city,
            "provincia": province,
            "cap": postcode,
            "country": country,
        })
    return {"items": items[:6]}


@api_router.get("/weather-installation", dependencies=[Depends(dep_current_user)])
async def weather_installation(date: str, comune: str = "", provincia: str = "", cap: str = "", address: str = "", latitude: Optional[float] = None, longitude: Optional[float] = None):'''
if old_sig not in text:
    raise SystemExit('weather signature anchor not found')
text = text.replace(old_sig, new_sig, 1)

old_candidates_guard = '''    if not candidates:
        raise HTTPException(422, "Manca il Comune della sede")

    timeout = httpx.Timeout(8.0, connect=5.0)'''
new_candidates_guard = '''    if not candidates and (latitude is None or longitude is None):
        raise HTTPException(422, "Manca la località: seleziona un indirizzo suggerito")

    timeout = httpx.Timeout(8.0, connect=5.0)'''
if old_candidates_guard not in text:
    raise SystemExit('candidate guard anchor not found')
text = text.replace(old_candidates_guard, new_candidates_guard, 1)

old_geocode = '''            loc = None
            used = None
            for candidate in candidates:
                r = await client.get("https://geocoding-api.open-meteo.com/v1/search", params={
                    "name": candidate, "count": 5, "language": "it", "countryCode": "IT", "format": "json"
                })
                r.raise_for_status()
                results = r.json().get("results") or []
                if results:
                    # preferisci l'Italia; se presente, prova a far combaciare provincia/admin1 senza renderla obbligatoria
                    italy = [x for x in results if str(x.get("country_code") or "").upper() == "IT"] or results
                    loc = italy[0]
                    if provincia:
                        prov_u = provincia.upper()
                        for x in italy:
                            admin1 = str(x.get("admin1") or "").upper()
                            admin2 = str(x.get("admin2") or "").upper()
                            if prov_u in admin1 or prov_u in admin2:
                                loc = x; break
                    used = candidate
                    break
            if not loc:
                raise HTTPException(422, f"Località non trovata. Comune ricevuto: {comune or '-'}")'''
new_geocode = '''            loc = None
            used = None
            if latitude is not None and longitude is not None:
                try:
                    lat = float(latitude); lon = float(longitude)
                except (TypeError, ValueError):
                    raise HTTPException(422, "Coordinate indirizzo non valide")
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise HTTPException(422, "Coordinate indirizzo fuori intervallo")
                loc = {
                    "latitude": lat,
                    "longitude": lon,
                    "name": comune or address or "Posizione verificata",
                    "admin2": provincia,
                }
                used = "coordinate verificate"
            else:
                for candidate in candidates:
                    r = await client.get("https://geocoding-api.open-meteo.com/v1/search", params={
                        "name": candidate, "count": 5, "language": "it", "countryCode": "IT", "format": "json"
                    })
                    r.raise_for_status()
                    results = r.json().get("results") or []
                    if results:
                        italy = [x for x in results if str(x.get("country_code") or "").upper() == "IT"] or results
                        loc = italy[0]
                        if provincia:
                            prov_u = provincia.upper()
                            for x in italy:
                                admin1 = str(x.get("admin1") or "").upper()
                                admin2 = str(x.get("admin2") or "").upper()
                                if prov_u in admin1 or prov_u in admin2:
                                    loc = x; break
                        used = candidate
                        break
                if not loc:
                    raise HTTPException(422, "Località non trovata. Seleziona un indirizzo suggerito per confermare posizione e meteo.")'''
if old_geocode not in text:
    raise SystemExit('weather geocode anchor not found')
text = text.replace(old_geocode, new_geocode, 1)
p.write_text(text, encoding='utf-8')

# ---------------- InstallationWeather.jsx ----------------
p = Path('frontend/src/components/InstallationWeather.jsx')
text = p.read_text(encoding='utf-8')
old = 'export default function InstallationWeather({ date, site, address = "", comune = "", provincia = "", cap = "", compact = false, className = "" }) {'
new = 'export default function InstallationWeather({ date, site, address = "", comune = "", provincia = "", cap = "", latitude = null, longitude = null, verified = false, subject = "installazione", compact = false, className = "" }) {'
if old not in text:
    raise SystemExit('weather component signature anchor not found')
text = text.replace(old, new, 1)
text = text.replace('if (!city && !place) { setState("no-place"); return () => { active = false; }; }', 'if (!city && !place && (latitude === null || longitude === null)) { setState("no-place"); return () => { active = false; }; }', 1)
text = text.replace('const res = await axios.get(`${API}/weather-installation`, { params: { date, comune: city, provincia: province, cap: postal, address: place } });', 'const res = await axios.get(`${API}/weather-installation`, { params: { date, comune: city, provincia: province, cap: postal, address: place, latitude, longitude } });', 1)
text = text.replace('}, [date, place, city, province, postal, delta]);', '}, [date, place, city, province, postal, latitude, longitude, delta]);', 1)
text = text.replace('<b>Meteo:</b> seleziona la data dell’installazione.', '<b>Meteo:</b> seleziona la data del {subject}.', 1)
text = text.replace('<b>Meteo:</b> installazione già trascorsa.', '<b>Meteo:</b> {subject} già trascorso.', 1)
text = text.replace('Saranno mostrate automaticamente quando l’installazione entrerà nei prossimi 16 giorni.', 'Saranno mostrate automaticamente quando il {subject} entrerà nei prossimi 16 giorni.', 1)
text = text.replace('<div className={compact ? "font-bold" : "font-black text-base"}>Meteo installazione · {weatherText(weather.code)}</div>', '<div className={compact ? "font-bold" : "font-black text-base"}>{verified ? "Meteo confermato" : `Meteo ${subject}`} · {weatherText(weather.code)}</div>', 1)
p.write_text(text, encoding='utf-8')

# ---------------- RegistryPage.jsx ----------------
p = Path('frontend/src/pages/RegistryPage.jsx')
text = p.read_text(encoding='utf-8')
text = text.replace('  const [clientView, setClientView] = useState("active");', '  const [clientView, setClientView] = useState("active");\n  const [addressSearch, setAddressSearch] = useState({ query: "", loading: false, items: [], open: false, error: "" });', 1)

anchor = '''  const startEdit = (x) => {
    setEditing(x.id);
    setForm({ ...empty, ...x });
    setLookupSearch({});
    setLookupOpen({});
    setOpen(true);
  };
'''
extra = '''
  useEffect(() => {
    if (!open || resource !== "sopralluoghi") return undefined;
    const query = String(form.indirizzo_libero || "").trim();
    if (form.indirizzo_verificato || query.length < 4) {
      setAddressSearch((prev) => ({ ...prev, query, items: [], open: false, loading: false, error: "" }));
      return undefined;
    }
    const timer = setTimeout(async () => {
      setAddressSearch({ query, loading: true, items: [], open: true, error: "" });
      try {
        const { data } = await axios.get(`${API}/address-search`, { params: { q: query } });
        setAddressSearch({ query, loading: false, items: data?.items || [], open: true, error: "" });
      } catch (e) {
        setAddressSearch({ query, loading: false, items: [], open: true, error: errorText(e) });
      }
    }, 650);
    return () => clearTimeout(timer);
  }, [open, resource, form.indirizzo_libero, form.indirizzo_verificato]);

  const changeAddressField = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field.key]: value,
      indirizzo_verificato: false,
      indirizzo_latitudine: "",
      indirizzo_longitudine: "",
      comune_libero: "",
      provincia_libera: "",
      cap_libero: "",
    }));
  };

  const chooseAddress = (item) => {
    setForm((prev) => ({
      ...prev,
      indirizzo_libero: item.label || prev.indirizzo_libero,
      indirizzo_verificato: true,
      indirizzo_latitudine: item.latitude,
      indirizzo_longitudine: item.longitude,
      comune_libero: item.comune || "",
      provincia_libera: item.provincia || "",
      cap_libero: item.cap || "",
    }));
    setAddressSearch({ query: item.label || "", loading: false, items: [], open: false, error: "" });
  };
'''
if anchor not in text:
    raise SystemExit('Registry startEdit anchor not found')
text = text.replace(anchor, anchor + extra, 1)

old_plain = '''                    ) : (
                      <Input
                        className="mt-1 h-12"
                        type={f.type || "text"}
                        value={form[f.key] || ""}
                        onChange={(e) => changeField(f, e.target.value)}
                        required={f.required}
                        disabled={disabled}
                      />
                    )}'''
new_plain = '''                    ) : f.addressAutocomplete ? (
                      <div className="relative mt-1">
                        <Input
                          className={`h-12 pr-10 ${form.indirizzo_verificato ? "border-emerald-400 bg-emerald-50/40" : ""}`}
                          type="text"
                          value={form[f.key] || ""}
                          onChange={(e) => changeAddressField(f, e.target.value)}
                          onFocus={() => {
                            if (!form.indirizzo_verificato && String(form[f.key] || "").trim().length >= 4) {
                              setAddressSearch((prev) => ({ ...prev, open: true }));
                            }
                          }}
                          autoComplete="off"
                          required={f.required}
                          disabled={disabled}
                          placeholder="Inizia a scrivere via, civico e comune..."
                        />
                        <MapPin size={18} className={`absolute right-3 top-3.5 ${form.indirizzo_verificato ? "text-emerald-600" : "text-slate-400"}`}/>
                        {form.indirizzo_verificato && <div className="mt-1 text-xs font-bold text-emerald-700">✓ Indirizzo verificato: Maps e meteo useranno questa posizione esatta.</div>}
                        {!form.indirizzo_verificato && String(form[f.key] || "").trim().length >= 4 && <div className="mt-1 text-xs text-slate-500">Seleziona uno dei risultati per confermare posizione e meteo.</div>}
                        {addressSearch.open && !form.indirizzo_verificato && (
                          <div className="absolute z-[70] left-0 right-0 mt-1 rounded-lg border border-slate-200 bg-white shadow-xl max-h-64 overflow-auto">
                            {addressSearch.loading ? <div className="px-3 py-3 text-sm text-slate-500">Ricerca indirizzo…</div> : addressSearch.error ? <div className="px-3 py-3 text-sm text-amber-700">{addressSearch.error}</div> : addressSearch.items.length ? addressSearch.items.map((item, i) => (
                              <button key={`${item.latitude}-${item.longitude}-${i}`} type="button" onMouseDown={(e)=>e.preventDefault()} onClick={() => chooseAddress(item)} className="block w-full border-b border-slate-100 px-3 py-2.5 text-left hover:bg-blue-50 last:border-0">
                                <div className="flex items-start gap-2"><MapPin size={16} className="mt-0.5 shrink-0 text-[#1A456B]"/><div><div className="text-sm font-semibold text-slate-900">{item.label}</div><div className="text-[11px] text-slate-500">Posizione trovata · seleziona per confermare</div></div></div>
                              </button>
                            )) : <div className="px-3 py-3 text-sm text-slate-500">Nessun indirizzo trovato. Aggiungi anche il comune.</div>}
                          </div>
                        )}
                      </div>
                    ) : (
                      <Input
                        className="mt-1 h-12"
                        type={f.type || "text"}
                        value={form[f.key] || ""}
                        onChange={(e) => changeField(f, e.target.value)}
                        required={f.required}
                        disabled={disabled}
                      />
                    )}'''
if old_plain not in text:
    raise SystemExit('Registry plain input anchor not found')
text = text.replace(old_plain, new_plain, 1)

old_weather = '''                {mapAddress && <a
                  className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-bold text-[#1A456B] hover:bg-blue-100"
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapAddress)}`}
                  target="_blank" rel="noreferrer"
                ><MapPin size={18} weight="fill"/>Apri in Google Maps · {mapAddress}</a>}
                <InstallationWeather
                  date={form.data}
                  site={selectedSite}
                  address={freeAddress}
                  comune={selectedSite?.comune || ""}
                  provincia={selectedSite?.provincia || ""}
                  cap={selectedSite?.cap || ""}
                />'''
new_weather = '''                {mapAddress && <a
                  className={`inline-flex min-h-11 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold hover:bg-blue-100 ${form.indirizzo_verificato ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-blue-200 bg-blue-50 text-[#1A456B]"}`}
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(form.indirizzo_verificato && form.indirizzo_latitudine && form.indirizzo_longitudine ? `${form.indirizzo_latitudine},${form.indirizzo_longitudine}` : mapAddress)}`}
                  target="_blank" rel="noreferrer"
                ><MapPin size={18} weight="fill"/>{form.indirizzo_verificato ? "Posizione confermata in Google Maps" : "Apri in Google Maps"} · {mapAddress}</a>}
                <InstallationWeather
                  date={form.data}
                  site={selectedSite}
                  address={freeAddress}
                  comune={selectedSite?.comune || form.comune_libero || ""}
                  provincia={selectedSite?.provincia || form.provincia_libera || ""}
                  cap={selectedSite?.cap || form.cap_libero || ""}
                  latitude={form.indirizzo_verificato ? form.indirizzo_latitudine : null}
                  longitude={form.indirizzo_verificato ? form.indirizzo_longitudine : null}
                  verified={Boolean(form.indirizzo_verificato)}
                  subject={resource === "sopralluoghi" ? "sopralluogo" : "installazione"}
                />'''
if old_weather not in text:
    raise SystemExit('Registry weather anchor not found')
text = text.replace(old_weather, new_weather, 1)
p.write_text(text, encoding='utf-8')

# ---------------- BusinessPages.jsx ----------------
p = Path('frontend/src/pages/BusinessPages.jsx')
text = p.read_text(encoding='utf-8')
old = 'F("indirizzo_libero", "Indirizzo sopralluogo", { full: true }),' 
new = 'F("indirizzo_libero", "Indirizzo sopralluogo", { full: true, addressAutocomplete: true, help: "Scrivi via, civico e comune, poi seleziona il risultato corretto per confermare Maps e meteo." }),' 
if old not in text:
    raise SystemExit('Business address anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

Path('VERSION').write_text('R14\n', encoding='utf-8')
print('R14 patch applicata')
