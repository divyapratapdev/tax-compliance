import React, { createContext, useContext, useState, useEffect } from "react";
import { getProfile, login as apiLogin, register as apiRegister } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("taxpilot_token");
    if (token) {
      getProfile()
        .then((data) => setUser(data))
        .catch((err) => {
          if (err?.response?.status === 401) {
            localStorage.removeItem("taxpilot_token");
            setUser(null);
          }
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (credentials) => {
    const data = await apiLogin(credentials);
    localStorage.setItem("taxpilot_token", data.access_token);
    const profile = await getProfile();
    setUser(profile);
  };

  const register = async (details) => {
    await apiRegister(details);
    // After registration, log them in automatically
    await login({ email: details.email, password: details.password });
  };

  const logout = () => {
    localStorage.removeItem("taxpilot_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, setUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
