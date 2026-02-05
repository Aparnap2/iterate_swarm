'use client';

import { useState, useTransition } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  GitBranch,
  Activity,
  ChevronLeft,
  ChevronRight,
  Server,
  MessageSquare,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/debug', icon: LayoutDashboard },
  { name: 'Kafka Browser', href: '/debug/kafka', icon: MessageSquare },
  { name: 'Workflows', href: '/debug/workflows', icon: GitBranch },
  { name: 'Traces', href: '/debug/traces', icon: Activity },
];

export function DebugSidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isPending, startTransition] = useTransition();

  const toggleSidebar = () => {
    startTransition(() => {
      setIsCollapsed(!isCollapsed);
    });
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-slate-950 border-r border-slate-800 transition-all duration-300 ease-in-out',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Header */}
      <div className="flex h-16 items-center justify-between border-b border-slate-800 px-4">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <Server className="h-6 w-6 text-emerald-500" />
            <span className="text-lg font-bold text-white">LiteDebug</span>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="mt-6 px-3 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/debug' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/20'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              )}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!isCollapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {!isCollapsed && (
        <div className="absolute bottom-4 left-0 right-0 px-4">
          <div className="rounded-lg bg-slate-900/50 p-3 text-xs text-slate-500">
            <p className="font-medium text-slate-400">IterateSwarm</p>
            <p className="mt-1">Debug Console v1.0</p>
          </div>
        </div>
      )}
    </aside>
  );
}

export function DebugLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-950">
      <DebugSidebar />
      <main
        className={cn(
          'min-h-screen transition-all duration-300 ease-in-out',
          // Sidebar width + margin
          'ml-16 w-[calc(100%-4rem)]'
        )}
      >
        {children}
      </main>
    </div>
  );
}
