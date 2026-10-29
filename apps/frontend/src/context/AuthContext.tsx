import React, { createContext, useContext, useEffect, useState } from 'react';
import { LoginRequest, RegisterRequest, UserProfile } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('codeguardian_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore authenticated session on initial mount
  useEffect(() => {
    let isMounted = true;

    const restoreSession = async () => {
      const storedToken = localStorage.getItem('codeguardian_token');
      if (!storedToken) {
        if (isMounted) {
          setUser(null);
          setToken(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        const profile = await api.getMe();
        if (isMounted) {
          setUser(profile);
          setToken(storedToken);
        }
      } catch (err) {
        // Token expired or invalid
        localStorage.removeItem('codeguardian_token');
        if (isMounted) {
          setUser(null);
          setToken(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    restoreSession();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const res = await api.login(credentials);
      localStorage.setItem('codeguardian_token', res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterRequest) => {
    setIsLoading(true);
    try {
      const res = await api.register(payload);
      localStorage.setItem('codeguardian_token', res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('codeguardian_token');
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
