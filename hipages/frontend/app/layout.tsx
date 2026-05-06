import { AuthProvider } from "@/src/contexts/AuthContext";
import { Toaster } from "sonner";
import { Toaster as HotToaster } from "react-hot-toast";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
          <Toaster position="top-right" />
          <HotToaster position="bottom-right" />
        </AuthProvider>
      </body>
    </html>
  );
}