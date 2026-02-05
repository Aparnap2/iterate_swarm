'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  className?: string;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-white placeholder:text-slate-500',
          'focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'transition-all duration-200',
          className
        )}
        ref={ref}
        {...props}
      >
        {children}
      </select>
    );
  }
);
Select.displayName = 'Select';

export { Select };
