/**
 * DEPRECATED — this file is kept only for backward-compatibility.
 *
 * The canonical auth context lives at:
 *   src/contexts/AuthContext.tsx
 *
 * That file includes:
 *  - expected_role support for role-separated login flows
 *  - OTP / email-verification awareness
 *  - email_verified, is_verified, verification_status fields on User
 *  - fetchUser exposed on the context for manual refresh
 *  - Pydantic v2 error extraction (detail arrays)
 *
 * DO NOT add logic here. Update src/contexts/AuthContext.tsx instead.
 * Any import from this path will use the canonical context transparently.
 */
export {
  AuthProvider,
  useAuth,
  type UserRole,
  type User,
  type TradieProfile,
} from '../contexts/AuthContext'
