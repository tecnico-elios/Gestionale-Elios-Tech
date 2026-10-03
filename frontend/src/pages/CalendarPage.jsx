import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import {
  CalendarBlank, CaretLeft, CaretRight, Plus, MapPin, Wrench, ClipboardText,
  Headset, Briefcase, UsersThree, Clock, UploadSimple, Gear, Trash, PencilSimple,
  X, Cloud, ArrowSquareOut
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import InstallationWeather from "../components/InstallationWeather";

const pad = n => String(n).padStart(2,"0");
const localIso = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
const dateKey = value => String(value || "").slice(0,10);
const timeKey = value => { try { const d=new Date(value); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; } catch { return ""; } };
const parseLocal = value => { const d = new Date(value); return Number.isNaN(d.getTime()) ? new Date() : d; };
const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d,n) => { const x=new Date(d); x.setDate(x.getDate()+n); return x; };
const startOfWeek = d => { const x=startOfDay(d); const day=(x.getDay()+6)%7; return addDays(x,-day); };
const addMonths = (d,n) => new Date(d.getFullYear(), d.getMonth()+n, 1);
const startOfMonthGrid = d => startOfWeek(new Date(d.getFullYear(), d.getMonth(), 1));
const fmtDay = d => d.toLocaleDateString("it-IT", {weekday:"short", day:"2-digit", month:"2-digit"});
const fmtMonth = d => d.toLocaleDateString("it-IT", {month:"long",year:"numeric"});
const sameDay = (a,b) => dateKey(a)===dateKey(b);
const hexToRgba = (hex, alpha=.13) => {
  const h=String(hex||"#64748b").replace("#",""); if(h.length!==6)return `rgba(100,116,139,${alpha})`;
  const n=parseInt(h,16); return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${alpha})`;
};
const iconFor = cat => cat==="Installazione"?Wrench:cat==="Sopralluogo"?ClipboardText:cat==="Assistenza"?Headset:cat==="Commerciale"?Briefcase:UsersThree;
const categoryOptions=["Attività","Riunione","Sopralluogo","Assistenza","Installazione","Formazione","Commerciale","Altro"];

function EventCard({event,onOpen,onDragStart,compact=false}){
  const Icon=iconFor(event.category); const color=event.resource_color||"#64748b";
  return <button
    type="button" draggable={!event.recurrence_instance}
    onDragStart={e=>onDragStart?.(e,event)} onClick={()=>onOpen(event)}
    className={`w-full text-left rounded-md border px-2 py-1.5 hover:shadow-sm overflow-hidden ${compact?"text-[11px]":"text-xs"}`}
    style={{borderLeft:`4px solid ${color}`,backgroundColor:hexToRgba(color,.10)}}
    title={`${event.title}${event.resource_name?` · ${event.resource_name}`:""}`}
  >
    <div className="flex items-center gap-1 font-bold text-slate-900 min-w-0"><Icon size={13}/><span className="truncate">{event.title}</span></div>
    {!event.all_day && <div className="text-slate-600 mt-0.5">{timeKey(event.start)}{event.resource_name?` · ${event.resource_name}`:""}</div>}
  </button>
}

export default function CalendarPage(){
  const {isAdmin,hasPermission}=useAuth(); const navigate=useNavigate();
  const [view,setView]=useState("week"); const [cursor,setCursor]=useState(new Date());
  const [events,setEvents]=useState([]),[resources,setResources]=useState([]),[loading,setLoading]=useState(false);
  const [selectedResources,setSelectedResources]=useState([]); const [selectedCategories,setSelectedCategories]=useState([]);
  const [detail,setDetail]=useState(null),[editor,setEditor]=useState(null),[resourceDlg,setResourceDlg]=useState(false),[importDlg,setImportDlg]=useState(false);
  const [dragging,setDragging]=useState(null);
  const canCreate=hasPermission("calendar","create")||isAdmin; const canEdit=hasPermission("calendar","edit")||isAdmin;

  const range=useMemo(()=>{
    if(view==="day"){const s=startOfDay(cursor);return [s,addDays(s,1)];}
    if(view==="week"){const s=startOfWeek(cursor);return [s,addDays(s,7)];}
    const s=startOfMonthGrid(cursor);return [s,addDays(s,42)];
  },[cursor,view]);

  const load=async()=>{setLoading(true);try{
    const {data}=await axios.get(`${API}/calendar/events`,{params:{start:localIso(range[0]),end:localIso(range[1])}});
    setEvents(data.items||[]); setResources(data.resources||[]);
  }catch(e){toast.error("Calendario non disponibile",{description:e?.response?.data?.detail||e?.message});}finally{setLoading(false)}};
  useEffect(()=>{load()},[range[0].getTime(),range[1].getTime()]); // eslint-disable-line react-hooks/exhaustive-deps

  const visible=useMemo(()=>events.filter(e=>{
    if(selectedResources.length && !(e.resource_ids||[]).some(id=>selectedResources.includes(id))) return false;
    if(selectedCategories.length && !selectedCategories.includes(e.category)) return false;
    return true;
  }),[events,selectedResources,selectedCategories]);

  const byDay=useMemo(()=>{const m={};for(const e of visible){const k=dateKey(e.start);(m[k]||(m[k]=[])).push(e)};for(const k of Object.keys(m))m[k].sort((a,b)=>String(a.start).localeCompare(String(b.start)));return m},[visible]);
  const goToday=()=>setCursor(new Date());
  const shift=dir=>setCursor(c=>view==="month"?addMonths(c,dir):addDays(c,dir*(view==="week"?7:1)));
  const heading=view==="month"?fmtMonth(cursor):view==="week"?`${fmtDay(range[0])} – ${fmtDay(addDays(range[1],-1))}`:cursor.toLocaleDateString("it-IT",{weekday:"long",day:"2-digit",month:"long",year:"numeric"});

  const newEvent=(date=new Date())=>{
    const s=new Date(date); if(s.getHours()===0)s.setHours(9,0,0,0); const e=new Date(s);e.setHours(s.getHours()+1);
    setEditor({key:null,title:"",start:localIso(s),end:localIso(e),category:"Attività",resource_ids:[],description:"",location:"",all_day:false,status:"Da confermare",priority:"Normale",meeting_link:"",reminder_minutes:30,recurrence:"none"});
  };
  const editEvent=e=>setEditor({...e,start:String(e.start).slice(0,16),end:String(e.end||e.start).slice(0,16),resource_ids:e.resource_ids||[]});
  const saveEvent=async()=>{if(!editor?.title?.trim())return toast.error("Inserisci il titolo");try{
    const payload={...editor}; delete payload.source_record; delete payload.key; delete payload.resource_name; delete payload.resource_names; delete payload.resource_color; delete payload.resource_colors;
    if (payload.recurrence === "daily") payload.rrule = "RRULE:FREQ=DAILY";
    else if (payload.recurrence === "weekly") payload.rrule = "RRULE:FREQ=WEEKLY";
    else if (payload.recurrence === "monthly") payload.rrule = "RRULE:FREQ=MONTHLY";
    else if (payload.recurrence === "none") payload.rrule = null;
    delete payload.recurrence;
    if(editor.key) await axios.put(`${API}/calendar/events/${encodeURIComponent(editor.key)}`,payload); else await axios.post(`${API}/calendar/events`,payload);
    toast.success(editor.key?"Evento aggiornato":"Evento creato");setEditor(null);setDetail(null);await load();
  }catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e?.message})}};
  const deleteEvent=async()=>{if(!editor?.key||!editor.key.startsWith("manual:"))return;try{await axios.delete(`${API}/calendar/events/${encodeURIComponent(editor.key)}`);toast.success("Evento eliminato");setEditor(null);setDetail(null);load()}catch(e){toast.error("Eliminazione non riuscita",{description:e?.response?.data?.detail||e?.message})}};

  const dropOnDate=async(date)=>{if(!dragging||!canEdit)return;const old=parseLocal(dragging.start);const target=new Date(date);if(target.getHours()===0&&target.getMinutes()===0)target.setHours(old.getHours(),old.getMinutes(),0,0);const oldEnd=parseLocal(dragging.end||dragging.start);const duration=Math.max(15,(oldEnd-old)/60000);const end=new Date(target.getTime()+duration*60000);try{
    await axios.put(`${API}/calendar/events/${encodeURIComponent(dragging.key)}`,{start:localIso(target),end:localIso(end)});setDragging(null);await load();
  }catch(e){toast.error("Spostamento non riuscito",{description:e?.response?.data?.detail||e?.message})}};

  const openSource=ev=>{
    if(ev.source_type==="installazione")navigate("/installazioni");
    else if(ev.source_type==="sopralluogo")navigate("/sopralluoghi");
    else if(ev.source_type==="assistenza")navigate("/assistenza");
    else if(ev.source_type==="custom"&&ev.module_slug)navigate(`/moduli/${ev.module_slug}`);
  };

  const days=view==="month"?Array.from({length:42},(_,i)=>addDays(range[0],i)):view==="week"?Array.from({length:7},(_,i)=>addDays(range[0],i)):[range[0]];
  const hours=Array.from({length:14},(_,i)=>7+i);

  return <div className="max-w-[1600px] mx-auto px-3 sm:px-5 py-4 space-y-4 lg:h-[calc(100vh-64px)] lg:overflow-hidden lg:flex lg:flex-col" data-testid="company-calendar-page">
    <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
      <div><h1 className="font-display text-3xl font-black text-slate-900">Calendario</h1></div>
      <div className="flex gap-2 flex-wrap">{isAdmin&&<Button variant="outline" onClick={()=>setResourceDlg(true)}><Gear size={17}/> Calendari/persona</Button>}{isAdmin&&<Button variant="outline" onClick={()=>setImportDlg(true)}><UploadSimple size={17}/> Importa calendario</Button>}{canCreate&&<Button onClick={()=>newEvent(cursor)}><Plus size={17}/> Nuovo evento</Button>}</div>
    </div>

    <div className="et-card p-3 flex flex-col xl:flex-row xl:items-center gap-3 justify-between">
      <div className="flex items-center gap-2"><Button variant="outline" size="icon" onClick={()=>shift(-1)}><CaretLeft/></Button><Button variant="outline" onClick={goToday}>Oggi</Button><Button variant="outline" size="icon" onClick={()=>shift(1)}><CaretRight/></Button><div className="ml-2 font-black text-slate-900 capitalize">{heading}</div></div>
      <div className="flex gap-1 bg-slate-100 p-1 rounded-md">{[["day","Giorno"],["week","Settimana"],["month","Mese"]].map(([k,l])=><button key={k} onClick={()=>setView(k)} className={`px-3 py-1.5 rounded text-sm font-semibold ${view===k?"bg-white shadow text-slate-900":"text-slate-600"}`}>{l}</button>)}</div>
    </div>

    <div className="grid xl:grid-cols-[220px_minmax(0,1fr)] gap-4 lg:flex-1 lg:min-h-0">
      <aside className="et-card p-3 h-fit lg:h-full lg:overflow-y-auto space-y-4">
        <div><div className="font-black text-sm mb-2">Calendari / persone</div><button className="text-xs text-blue-700 mb-2" onClick={()=>setSelectedResources([])}>Mostra tutti</button><div className="space-y-1.5">{resources.map(r=><label key={r.id} className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={selectedResources.includes(r.id)} onChange={e=>setSelectedResources(p=>e.target.checked?[...p,r.id]:p.filter(x=>x!==r.id))}/><span className="h-3 w-3 rounded-sm" style={{background:r.color||"#64748b"}}/><span className="truncate">{r.name}</span></label>)}</div></div>
        <div><div className="font-black text-sm mb-2">Tipo attività</div><button className="text-xs text-blue-700 mb-2" onClick={()=>setSelectedCategories([])}>Tutti</button><div className="space-y-1.5">{categoryOptions.map(c=><label key={c} className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={selectedCategories.includes(c)} onChange={e=>setSelectedCategories(p=>e.target.checked?[...p,c]:p.filter(x=>x!==c))}/><span>{c}</span></label>)}</div></div>
      </aside>

      <section className="et-card overflow-hidden min-w-0 lg:h-full lg:min-h-0">
        {loading&&<div className="p-8 text-center text-slate-500">Caricamento calendario…</div>}
        {!loading&&view==="month"&&<div className="grid grid-cols-7 lg:h-full lg:grid-rows-[auto_repeat(6,minmax(0,1fr))]">
          {["Lun","Mar","Mer","Gio","Ven","Sab","Dom"].map(x=><div key={x} className="p-2 text-center text-xs font-bold text-slate-500 bg-slate-50 border-b border-r">{x}</div>)}
          {days.map((d,i)=>{const k=dateKey(localIso(d));const inMonth=d.getMonth()===cursor.getMonth();return <div key={i} onDoubleClick={()=>newEvent(d)} onDragOver={e=>e.preventDefault()} onDrop={()=>dropOnDate(d)} className={`min-h-[105px] lg:min-h-0 overflow-hidden border-r border-b p-1.5 ${inMonth?"bg-white":"bg-slate-50"}`}><div className={`text-xs font-bold mb-1 ${sameDay(localIso(d),localIso(new Date()))?"inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white":inMonth?"text-slate-700":"text-slate-400"}`}>{d.getDate()}</div><div className="space-y-1">{(byDay[k]||[]).slice(0,5).map(e=><EventCard key={e.key} event={e} compact onOpen={setDetail} onDragStart={(ev,x)=>{setDragging(x);ev.dataTransfer.effectAllowed="move"}}/>)}{(byDay[k]||[]).length>5&&<div className="text-[11px] text-slate-500 px-1">+ {(byDay[k]||[]).length-5} altri</div>}</div></div>})}
        </div>}
        {!loading&&view!=="month"&&<div className="overflow-auto max-h-[76vh] lg:h-full lg:max-h-none"><div className="min-w-[900px]" style={{display:"grid",gridTemplateColumns:`70px repeat(${days.length}, minmax(130px,1fr))`}}>
          <div className="sticky top-0 bg-white z-20 border-b border-r"/>{days.map((d,i)=><div key={i} className="sticky top-0 bg-white z-20 p-2 text-center border-b border-r"><div className="text-xs uppercase text-slate-500">{d.toLocaleDateString("it-IT",{weekday:"short"})}</div><div className={`mx-auto mt-1 text-sm font-black ${sameDay(localIso(d),localIso(new Date()))?"h-7 w-7 rounded-full bg-blue-600 text-white flex items-center justify-center":""}`}>{d.getDate()}</div></div>)}
          {hours.map(h=><div key={`row-${h}`} className="contents"><div className="border-r border-b text-xs text-slate-400 text-right pr-2 pt-1 h-[72px]">{pad(h)}:00</div>{days.map((d,di)=>{const k=dateKey(localIso(d));const evs=(byDay[k]||[]).filter(e=>parseLocal(e.start).getHours()===h || (e.all_day&&h===7));return <div key={`${h}-${di}`} onDoubleClick={()=>{const x=new Date(d);x.setHours(h,0,0,0);newEvent(x)}} onDragOver={e=>e.preventDefault()} onDrop={()=>{const x=new Date(d);x.setHours(h,0,0,0);dropOnDate(x)}} className="border-r border-b p-1 min-h-[72px] hover:bg-blue-50/30"><div className="space-y-1">{evs.map(e=><EventCard key={e.key} event={e} onOpen={setDetail} onDragStart={(ev,x)=>{setDragging(x);ev.dataTransfer.effectAllowed="move"}}/>)}</div></div>})}</div>)}
        </div></div>}
      </section>
    </div>

    <Dialog open={!!detail} onOpenChange={v=>!v&&setDetail(null)}><DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>{detail?.title}</DialogTitle></DialogHeader>{detail&&<div className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-slate-50 p-3"><b>Quando</b><div className="mt-1">{parseLocal(detail.start).toLocaleString("it-IT")}{detail.end?` – ${parseLocal(detail.end).toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"})}`:""}</div></div><div className="rounded-xl bg-slate-50 p-3"><b>Partecipanti</b><div className="mt-2 flex flex-wrap gap-1.5">{(detail.resource_names||[detail.resource_name].filter(Boolean)).length?(detail.resource_names||[detail.resource_name]).filter(Boolean).map((name,i)=><span key={`${name}-${i}`} className="inline-flex items-center gap-1.5 rounded-full bg-white border border-slate-200 px-2.5 py-1 text-xs font-semibold"><span className="h-2.5 w-2.5 rounded-full" style={{background:(detail.resource_colors||[])[i]||detail.resource_color||"#64748b"}}/>{name}</span>):<span className="text-slate-400">Non assegnato</span>}</div></div></div>
      <div className="flex flex-wrap gap-2">{detail.category&&<span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold">{detail.category}</span>}{detail.status&&<span className="rounded-full bg-blue-50 text-blue-700 px-2.5 py-1 text-xs font-semibold">{detail.status}</span>}{detail.priority&&<span className="rounded-full bg-amber-50 text-amber-700 px-2.5 py-1 text-xs font-semibold">Priorità {detail.priority}</span>}</div>
      {detail.location&&<div><b className="text-sm">Luogo</b><div className="mt-1 flex items-start gap-2 text-sm"><MapPin className="mt-0.5"/>{detail.location}</div></div>}
      {detail.description&&<div><b className="text-sm">Note / descrizione</b><div className="mt-1 whitespace-pre-wrap text-sm bg-slate-50 rounded-md p-3 max-h-52 overflow-y-auto">{detail.description}</div></div>}
      {detail.meeting_link&&<div><b className="text-sm">Riunione online</b><div className="mt-1"><a href={detail.meeting_link} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">{detail.meeting_link}</a></div></div>}
      {detail.location&&<InstallationWeather date={dateKey(detail.start)} address={detail.location} compact/>}
      <div className="flex flex-wrap gap-2">{detail.location&&<Button variant="outline" onClick={()=>window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(detail.location)}`,"_blank","noopener,noreferrer")}><MapPin/> Maps</Button>}{detail.source_type!=="manual"&&<Button variant="outline" onClick={()=>openSource(detail)}><ArrowSquareOut/> Apri modulo</Button>}{canEdit&&!detail.recurrence_instance&&<Button onClick={()=>editEvent(detail)}><PencilSimple/> Modifica</Button>}</div>
    </div>}</DialogContent></Dialog>

    <EventEditor open={!!editor} event={editor} setEvent={setEditor} resources={resources} onClose={()=>setEditor(null)} onSave={saveEvent} onDelete={deleteEvent} canDelete={!!editor?.key?.startsWith("manual:")}/>
    <ResourcesDialog open={resourceDlg} onClose={()=>setResourceDlg(false)} resources={resources} onChanged={load}/>
    <ImportDialog open={importDlg} onClose={()=>setImportDlg(false)} onImported={load}/>
  </div>
}

function EventEditor({open,event,setEvent,resources,onClose,onSave,onDelete,canDelete}){
  const [resourceSearch,setResourceSearch]=useState("");
  if(!event)return null;
  const patch=(k,v)=>setEvent(p=>({...p,[k]:v}));
  const sourceLocked=event.key&&!event.key.startsWith("manual:");
  const filteredResources=resources.filter(r=>String(r.name||"").toLowerCase().includes(resourceSearch.toLowerCase()));
  const toggleResource=id=>patch("resource_ids",(event.resource_ids||[]).includes(id)?(event.resource_ids||[]).filter(x=>x!==id):[...(event.resource_ids||[]),id]);
  const recurrenceValue=event.recurrence || (String(event.rrule||"").includes("FREQ=DAILY")?"daily":String(event.rrule||"").includes("FREQ=WEEKLY")?"weekly":String(event.rrule||"").includes("FREQ=MONTHLY")?"monthly":"none");
  return <Dialog open={open} onOpenChange={v=>!v&&onClose()}><DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto"><DialogHeader><DialogTitle>{event.key?"Modifica evento":"Nuovo evento"}</DialogTitle></DialogHeader><div className="grid sm:grid-cols-2 gap-4">
    <div className="sm:col-span-2"><Label>Titolo *</Label><Input className="mt-1" value={event.title||""} onChange={e=>patch("title",e.target.value)} disabled={sourceLocked}/></div>
    <div><Label>Inizio *</Label><Input className="mt-1" type="datetime-local" value={String(event.start||"").slice(0,16)} onChange={e=>patch("start",e.target.value)}/></div><div><Label>Fine</Label><Input className="mt-1" type="datetime-local" value={String(event.end||"").slice(0,16)} onChange={e=>patch("end",e.target.value)}/></div>
    {!sourceLocked&&<>
      <div><Label>Tipo</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={event.category||"Attività"} onChange={e=>patch("category",e.target.value)}>{categoryOptions.map(x=><option key={x}>{x}</option>)}</select></div>
      <div><Label>Stato</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={event.status||"Da confermare"} onChange={e=>patch("status",e.target.value)}>{["Da confermare","Confermato","Completato","Annullato"].map(x=><option key={x}>{x}</option>)}</select></div>
      <div><Label>Priorità</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={event.priority||"Normale"} onChange={e=>patch("priority",e.target.value)}>{["Bassa","Normale","Alta","Urgente"].map(x=><option key={x}>{x}</option>)}</select></div>
      <div><Label>Ricorrenza</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={recurrenceValue} onChange={e=>patch("recurrence",e.target.value)}><option value="none">Nessuna</option><option value="daily">Giornaliera</option><option value="weekly">Settimanale</option><option value="monthly">Mensile</option></select></div>
      <div className="sm:col-span-2"><Label>Partecipanti</Label><div className="mt-1 rounded-xl border border-slate-200 p-3"><Input value={resourceSearch} onChange={e=>setResourceSearch(e.target.value)} placeholder="Cerca e aggiungi persone..."/><div className="mt-2 max-h-40 overflow-y-auto grid sm:grid-cols-2 gap-1">{filteredResources.map(r=>{const active=(event.resource_ids||[]).includes(r.id);return <button type="button" key={r.id} onClick={()=>toggleResource(r.id)} className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm border transition-colors ${active?"border-blue-200 bg-blue-50":"border-transparent hover:bg-slate-50"}`}><span className="h-3 w-3 rounded-full shrink-0" style={{background:r.color||"#64748b"}}/><span className="flex-1 truncate font-medium">{r.name}</span>{active&&<span className="text-blue-700 font-bold">✓</span>}</button>})}</div>{(event.resource_ids||[]).length>0&&<div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t">{(event.resource_ids||[]).map(id=>{const r=resources.find(x=>x.id===id);return r?<span key={id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold"><span className="h-2 w-2 rounded-full" style={{background:r.color}}/>{r.name}<button type="button" onClick={()=>toggleResource(id)}><X size={12}/></button></span>:null})}</div>}</div></div>
      <div className="sm:col-span-2"><Label>Luogo</Label><Input className="mt-1" value={event.location||""} onChange={e=>patch("location",e.target.value)} placeholder="Indirizzo o luogo"/></div>
      <div className="sm:col-span-2"><Label>Link riunione</Label><Input className="mt-1" value={event.meeting_link||""} onChange={e=>patch("meeting_link",e.target.value)} placeholder="https://meet.google.com/... oppure Teams"/></div>
      <div><Label>Promemoria</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={Number(event.reminder_minutes??30)} onChange={e=>patch("reminder_minutes",Number(e.target.value))}><option value={0}>Nessuno</option><option value={10}>10 minuti prima</option><option value={30}>30 minuti prima</option><option value={60}>1 ora prima</option><option value={1440}>1 giorno prima</option></select></div>
      <div className="flex items-end"><label className="h-10 flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={!!event.all_day} onChange={e=>patch("all_day",e.target.checked)}/> Tutto il giorno</label></div>
      <div className="sm:col-span-2"><Label>Note</Label><Textarea className="mt-1 min-h-28" value={event.description||""} onChange={e=>patch("description",e.target.value)}/></div>
    </>}
  </div><div className="flex justify-between gap-2 mt-4">{canDelete?<Button variant="outline" className="text-red-600" onClick={onDelete}><Trash/> Elimina</Button>:<span/>}<div className="flex gap-2"><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={onSave}>Salva</Button></div></div></DialogContent></Dialog>
}

function ResourcesDialog({open,onClose,resources,onChanged}){
  const [name,setName]=useState(""),[color,setColor]=useState("#64748b");
  const add=async()=>{if(!name.trim())return;try{await axios.post(`${API}/calendar/resources`,{name,color});setName("");toast.success("Calendario creato");await onChanged()}catch(e){toast.error("Creazione non riuscita",{description:e?.response?.data?.detail||e?.message})}};
  const remove=async r=>{try{await axios.delete(`${API}/calendar/resources/${r.id}`);toast.success("Calendario disattivato");await onChanged()}catch(e){toast.error("Operazione non riuscita")}};
  return <Dialog open={open} onOpenChange={v=>!v&&onClose()}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Calendari / persone</DialogTitle></DialogHeader><div className="space-y-2 max-h-72 overflow-y-auto">{resources.map(r=><div key={r.id} className="flex items-center gap-3 border rounded-md p-2"><span className="h-5 w-5 rounded" style={{background:r.color}}/><div className="flex-1"><div className="font-semibold">{r.name}</div><div className="text-xs text-slate-500">{"Calendario aziendale"}</div></div><Button variant="ghost" size="icon" className="text-red-600" onClick={()=>remove(r)}><Trash/></Button></div>)}</div><div className="border-t pt-3"><div className="font-bold mb-2">Nuovo calendario/persona</div><div className="flex gap-2"><Input value={name} onChange={e=>setName(e.target.value)} placeholder="Es. Matteo"/><input type="color" value={color} onChange={e=>setColor(e.target.value)} className="h-10 w-12 border rounded"/><Button onClick={add}><Plus/></Button></div></div></DialogContent></Dialog>
}

function ImportDialog({open,onClose,onImported}){
  const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[result,setResult]=useState(null);
  const run=async()=>{if(!file)return toast.error("Seleziona lo ZIP o un file .ics");setBusy(true);setResult(null);try{const fd=new FormData();fd.append("file",file);const {data}=await axios.post(`${API}/calendar/import/google-ics`,fd,{headers:{"Content-Type":"multipart/form-data"}});setResult(data);toast.success("Importazione completata");await onImported()}catch(e){toast.error("Importazione non riuscita",{description:e?.response?.data?.detail||e?.message})}finally{setBusy(false)}};
  const relink=async()=>{try{const {data}=await axios.post(`${API}/calendar/relink`);toast.success(`${data.linked} eventi collegati ai clienti`);onImported()}catch(e){toast.error("Collegamento clienti non riuscito")}};
  return <Dialog open={open} onOpenChange={v=>!v&&onClose()}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Importa calendario</DialogTitle></DialogHeader><p className="text-sm text-slate-600">Carica un archivio ZIP con calendari oppure un singolo file .ics. L'importazione è ripetibile e non duplica gli eventi già importati.</p><Input type="file" accept=".zip,.ics,text/calendar,application/zip" onChange={e=>setFile(e.target.files?.[0]||null)}/><div className="flex gap-2"><Button onClick={run} disabled={busy}>{busy?"Importazione…":"Importa"}</Button><Button variant="outline" onClick={relink}>Ricollega ai clienti</Button></div>{result&&<div className="rounded-md bg-emerald-50 border border-emerald-200 p-3 text-sm"><b>Importazione completata</b><div className="mt-1">Calendari: {result.calendars} · letti: {result.parsed} · nuovi: {result.imported} · aggiornati: {result.updated} · clienti collegati: {result.linked_clients}</div></div>}</DialogContent></Dialog>
}
