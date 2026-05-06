"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import api from "./api"
import { saveToken, removeToken, getToken } from "./auth"

export type UserRole = 'homeowner' | 'tradie'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  avatar?: string
  createdAt: string
  full_name?: string
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
  login: (email: string, password: string) => Promise<User | undefined>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  updateUser: (data: Partial<User>) => void
}

interface RegisterData {
  email: string
  password: string
  name: string
  role: UserRole
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

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

      // If tradie, optionally fetch tradie profile
      if (mappedUser.role === 'tradie') {
        try {
          const profileRes = await api.get(`/tradies/profile/me`)
          setTradieProfile(profileRes.data)
        } catch {
          // Ignore if profile fetch fails - tradie profile may not exist yet
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

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    try {
      const loginRes = await api.post("/auth/login", { email, password })
      const token = loginRes.data.access_token
      saveToken(token)
      const user = await fetchUser()
      return user
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Invalid email or password')
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
        role: data.role
      })
      // After register, auto login
      await login(data.email, data.password)
    } catch (error: any) {
      setIsLoading(false)
      throw new Error(error.response?.data?.detail || 'Registration failed')
    }
  }, [login])

  const logout = useCallback(() => {
    const nextPath = user?.role === 'tradie' ? '/tradie/login' : '/login'
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
    <AuthContext.Provider
      value={{
        user,
        tradieProfile,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        updateUser,
      }}
    >
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
