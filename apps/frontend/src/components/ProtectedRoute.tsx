import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, RefreshCw } from 'lucide-react';

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#07090e] flex flex-col items-center justify-center space-y-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-purple-600 to-pink-500 flex items-center justify-center shadow-2xl shadow-purple-600/40 animate-pulse">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <RefreshCw className="w-5 h-5 text-purple-300 animate-spin absolute -bottom-1 -right-1" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-white tracking-wide">CodeGuardian AI</p>
          <p className="text-xs text-purple-300/70 mt-1">Verifying cryptographic session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
