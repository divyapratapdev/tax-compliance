import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { listClients } from "@/lib/api";

const ClientContext = createContext({ clients: [], selected: "all", setSelected: () => {} });

export const ClientProvider = ({ children }) => {
  const [clients, setClients] = useState([]);
  const [selected, setSelected] = useState("all");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await listClients();
      setClients(data.clients || []);
    } catch (e) {
      // intentional silent — UI shows fallback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <ClientContext.Provider value={{ clients, selected, setSelected, loading, refresh }}>
      {children}
    </ClientContext.Provider>
  );
};

export const useClients = () => useContext(ClientContext);
