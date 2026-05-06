# Frontend Product Requirements Document (PRD)

## 1. Executive Summary
This document serves as the comprehensive guide for frontend developers to build the web application for our platform. It aligns exactly with our existing FastAPI backend architecture, defining the necessary features, state management, routing, UI/UX guidelines, and strict security protocols required for a production-ready system. 

The application serves two primary user roles:
1. **Homeowners**: Can browse tradies, post jobs, upload job photos (max 5), send inquiries, and leave reviews.
2. **Tradies**: Have a dedicated workspace ("Tradie Hub") to manage their public profile, view/quote on leads, manage job compliance documents, and configure lead matching preferences.

## 2. Design & Styling Guidelines
The frontend must feel premium, modern, and trustworthy.

*   **Global Background Color:** `#FFEBCC` (Soft sunlit cream). This should be used as the primary background color for pages.
*   **Icons & Accent Color:** `#8C3F1F` (Warm terracotta/brown). All icons, active states, and primary accents should use this color.
*   **Typography:** Modern sans-serif (e.g., Inter, Roboto) for high legibility.
*   **Components:** Leverage a robust component library (e.g., Shadcn UI, MUI, or TailwindCSS-based custom components) tailored to match the provided color scheme.
*   **Dashboard Aesthetic:** The Tradie Hub must strictly follow the provided UI snapshots (Dark teal/green containers for nested forms, pill-shaped tabs, modern switch toggles). *Note: The dark teal background in the Tradie Hub screenshots contrasts the global cream background—ensure the Tradie Dashboard operates as a distinct modular layout while respecting global branding rules where applicable.*

## 3. Strong Authentication, Authorization & Security
The frontend must rigorously enforce security matching the backend auth logic (`auth.py`).

*   **JWT Token Management:** 
    *   Store access tokens securely.
    *   Implement automatic Axios/Fetch interceptors to attach `Authorization: Bearer <token>` to all protected API calls.
    *   Handle 401 Unauthorized responses by seamlessly redirecting users to the login page and clearing local session state.
*   **Role-Based Access Control (RBAC):**
    *   Implement Frontend Route Guards (e.g., Higher-Order Components or middleware). 
    *   `/tradie/*` routes MUST solely be accessible to users with `role === 'tradie'`.
    *   `/homeowner/*` routes MUST solely be accessible to users with `role === 'homeowner'`.
*   **Input Sanitization:** All forms must validate inputs to prevent XSS (Cross-Site Scripting).
*   **CSRF Protection:** Utilize anti-CSRF measures if integrating with session-based backend configurations.

## 4. Tradie Hub (Dashboard) Exactly as Requested
The Tradie Dashboard requires precise implementation to match the backend models and the visual snapshots.

### 4.1. Sidebar Navigation
*   **Links:** Dashboard, Leads, Jobs, Earnings, Docs, Quotes, Preferences, Profile.
*   **Logout:** Fixed at the bottom of the sidebar.
*   **Active State:** Highlighted with `#8C3F1F` or the specific brand indicator color.

### 4.2. My Profile Page (`/tradie/profile`)
This page maps to the `TradieProfileUpdate` schema and `uploads.py` router.
*   **Header:** "My Profile - Edit your public tradie profile" + [Save] Button.
*   **Avatar/Photo Upload:**
    *   Includes a prominent Avatar placeholder.
    *   **Portfolio / "Still Photos" Feature:** Implement a gallery uploader that allows tradies to upload **up to 5 portfolio images**. The UI must enforce a strict UI restriction blocking uploads once 5 images are reached (matching backend limits seen in `job_photos`).
*   **Basic Info Form:**
    *   Business Name (Text input)
    *   Drop-down for primary trade selection.
    *   Bio textarea ("tell homeowners about yourself...").
*   **Location & Rates Form:**
    *   Suburb & State (Text inputs, integrates with backend Mapbox geocoding).
    *   Years Experience (Number input).
    *   Hourly Rate ($) (Number input).
    *   Licence Number (Text input).
    *   **Available for Work Toggle:** Important switch mapped to `is_available` boolean.

### 4.3. Lead Preferences Page (`/tradie/preferences`)
This page controls the tradie's matching engine criteria.
*   **Header:** "Lead Preferences - Control which leads you receive" + [Save] Button.
*   **Job Categories:** Multi-select pill components (Plumbing, Electrical, Carpentry, Painting, Roofing, Landscaping, HVAC, Tiling, Concreting, General).
*   **Location & Budget:**
    *   Max Distance (km) (Number input, e.g., 30).
    *   Min Budget ($) (Number input, e.g., 0).
    *   Preferred Suburbs (Input field with "Add" button to create an array of suburbs).
*   **Notifications:** Toggles mapped strictly to backend booleans:
    *   Email notifications
    *   SMS notifications
    *   Auto-decline leads outside preferences

### 4.4. Docs & Compliance Page (`/tradie/docs`)
Maps directly to `compliance.py` and `swms.py` endpoints.
*   **Header:** "Docs & Compliance - Manage your licences, SWMS & insurance" + [+ Upload Document] Button.
*   **Status Cards:** 5 visual cards showing verification status ("Not uploaded", "Pending", "Verified"):
    1.  Licence
    2.  SWMS
    3.  Insurance
    4.  White Card
    5.  ABN
*   **Empty State/List View:** Below the cards, show "No documents uploaded yet" or a list of uploaded docs with options to preview or delete securely.

## 5. Additional Key Application Features

### 5.1. Browse Page (Homeowners looking for Tradies)
*   **Search & Filter:** Categories, Suburb, State, Availability (using `GET /api/v1/tradies/`).
*   **Listings:** Card UI displaying Tradie Business Name, Avatar, Avg Rating, Review Count, and verification badge.

### 5.2. Public Tradie Profile (Homeowner View)
*   Shows tradie bio, category tags, public gallery.
*   **Contact Form:** Mapped to `POST /api/v1/tradies/{id}/inquiry` triggering backend Websockets, emails, and SMS to the tradie.

### 5.3. Job Board & Leads Management
*   **Homeowners:** Can post jobs. IMPORTANT: Homeowners can upload **up to 5 photos per job** to visually describe the issue (must hit `/api/v1/uploads/presign` then `/api/v1/uploads/confirm`). UI must restrict to 5.
*   **Tradies:** See Lead notifications on their dashboard. Lead cards must vividly highlight "Urgent" or "High Value" (>$1000) tags as returned by `GET /api/v1/tradies/dashboard/me`.

## 6. AI Assistant Integration
The platform includes an intelligent AI Assistant powered by an agentic backend. The frontend must implement a dedicated Chat UI (e.g., a persistent floating widget in the bottom right corner or a dedicated `/ai-chat` view) available to authenticated users.
*   **Endpoints to Integrate (`/api/v1/ai/*`):**
    *   `POST /chat`: Send user message and an optional `session_id`. Render the AI's markdown response. The UI must handle a loading state ("AI is thinking...") gracefully.
    *   `GET /history/{session_id}`: Load past messages when restoring a session.
    *   `GET /sessions`: Provide a sidebar or dropdown of recent chat threads, allowing users to jump back into an old conversation.
    *   `DELETE /history/{session_id}`: Allow the user to quickly clear the active conversation.
*   **UI/UX Guidelines:** The chat interface should support Markdown, syntax highlighting (if applicable), and auto-scroll to the newest message.

## 7. API Integration Strategy
*   **Client Factory:** Use Axios with a pre-configured `baseURL`.
*   **Uploads:** Implement multi-step upload flow:
    1. Request Pre-signed S3/Cloudflare URL from backend.
    2. PUT file directly to S3 (Frontend to Cloud).
    3. POST confirmation string to backend to finalize database entry.
*   **WebSockets:** Implement reconnecting WebSocket client to listen for real-time `new_inquiry` notifications.

## 8. Next Steps for Developer
1. Scaffold application (e.g., Next.js App Router, React + Vite).
2. Setup global CSS variables for `#FFEBCC` and `#8C3F1F`.
3. Build the Auth Provider Context.
4. Construct the Tradie Hub layout mapping to section 4 of this PRD.
5. Integrate presigned URL uploaders with file limits explicitly at 5.
6. Integrate the AI Assistant Chat widget across the authenticated layout.
