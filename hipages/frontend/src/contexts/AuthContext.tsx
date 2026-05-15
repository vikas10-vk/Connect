"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import api from "../lib/api"
import { saveToken, removeToken, getToken } from "../lib/auth"

export type UserRole = 'homeowner' | 'tradie' | 'admin'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  avatar?: string
  createdAt: string
  full_name?: string
  email_verified?: boolean
  is_verified?: boolean
}

export interface TradieProfile {
  id: string
  userId: string
  businessName: string
  bio: string
  categories: string[]
  isVerified: boolean
  isAvailable: boolean
  rating: number
  reviewCount: number
  credits: number
  responseRate: number
  // Mirrors backend VERIFICATION_STATUS_CHOICES exactly — "verified" not "approved"
  verification_status: 'pending_review' | 'in_review' | 'verified' | 'rejected' | 'suspended' | 'needs_documents'
  solo_or_team?: 'solo' | 'team'
  team_size?: string | null
  phone?: string | null
  location: {
    suburb: string
    state: string
    lat?: number
    lng?: number
  }
}

interface AuthContextType {
  user: User | null
  tradieProfile: TradieProfile | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string, expectedRole?: UserRole) => Promise<User | undefined>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  updateUser: (data: Partial<User>) => void
  fetchUser: () => Promise<any>
}

interface RegisterData {
  email: string
  password: string
  name: string
  role: UserRole
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// ── Extract a readable message from FastAPI / Pydantic error responses ────────
// Pydantic 422 errors: detail is an array [{msg, loc, type}, ...]
// Other FastAPI errors: detail is a plain string
function extractErrorMessage(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // Strip Pydantic v2's "Value error, " prefix if present
    return detail[0]?.msg?.replace(/^Value error,\s*/i, '') || fallback
  }
  return fallback
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tradieProfile, setTradieProfile] = useState<TradieProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const fetchUser = useCallback(async () => {
    try {
      if (!getToken()) {
        setIsLoading(false)
        return
      }
      const userRes = await api.get("/auth/me")
      const backendUser = userRes.data

      const mappedUser: User = {
        ...backendUser,
        name: backendUser.full_name || backendUser.name || 'User',
      }
      setUser(mappedUser)

      if (mappedUser.role === 'tradie') {
        try {
          const profileRes = await api.get(`/tradies/profile/me`)
          setTradieProfile(profileRes.data)
        } catch {
          // Profile may not exist yet — ignore
        }
      }
      return mappedUser
    } catch {
      removeToken()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  const login = useCallback(async (email: string, password: string, expectedRole?: UserRole) => {
    setIsLoading(true)
    try {
      const loginRes = await api.post("/auth/login", { email, password, expected_role: expectedRole })
      const token = loginRes.data.access_token
      saveToken(token)
      const user = await fetchUser()
      return user
    } catch (error: any) {
      throw new Error(extractErrorMessage(error, 'Invalid email or password'))
    } finally {
      setIsLoading(false)
    }
  }, [fetchUser])

  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true)
    try {
      await api.post("/auth/register", {
        email: data.email,
        password: data.password,
        full_name: data.name,
        role: data.role,
      })
      // Backend sends OTP on register — log user in so context is populated,
      // then caller redirects to /verify-email.
      await login(data.email, data.password, data.role)
    } catch (error: any) {
      setIsLoading(false)
      throw new Error(extractErrorMessage(error, 'Registration failed. Please try again.'))
    }
  }, [login])

  const logout = useCallback(() => {
    const nextPath = user?.role === 'tradie' ? '/tradie/login' : '/login'
    // Admin gets sent to /login — no separate admin login page exposed
    setUser(null)
    setTradieProfile(null)
    removeToken()
    router.push(nextPath)
  }, [router, user?.role])

  const updateUser = useCallback((data: Partial<User>) => {
    setUser(prev => {
      if (!prev) return null
      return { ...prev, ...data }
    })
  }, [])

  return (
    <AuthContext.Provider value={{
      user, tradieProfile, isLoading,
      isAuthenticated: !!user,
      login, register, logout, updateUser, fetchUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
