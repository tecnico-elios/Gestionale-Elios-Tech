import { API } from "./apiBase";
import { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";


const FeaturesContext = createContext({ commesse_enabled: true, reload: () => {} });

export function FeaturesProvider({ children }) {
  const [features, setFeatures] = useState({ commesse_enabled: true });
  const reload = () => {
    axios.get(`${API}/features`).then(({ data }) => setFeatures(data)).catch(() => {});
  };
  useEffect(() => { reload(); }, []);
  return <FeaturesContext.Provider value={{ ...features, reload }}>{children}</FeaturesContext.Provider>;
}

export function useFeatures() { return useContext(FeaturesContext); }
