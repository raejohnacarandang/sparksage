"use client";

import { SessionProvider } from "next-auth/react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-8 w-8"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
    </Button>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionProvider>
      <SidebarProvider>
        <AppSidebar />
        <main className="flex-1 min-w-0">
          <header className="flex h-12 sm:h-14 items-center gap-2 border-b px-3 sm:px-4">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-5 sm:h-6" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground truncate">
              SparkSage Dashboard
            </span>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </header>
          <div className="p-3 sm:p-6">{children}</div>
        </main>
      </SidebarProvider>
    </SessionProvider>
  );
}