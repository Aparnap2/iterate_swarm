import * as React from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[80px] w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-white placeholder:text-slate-500',
          'focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'transition-all duration-200 resize-none',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = 'Textarea';

export { Textarea };
