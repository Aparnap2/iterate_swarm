import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
        secondary: 'bg-slate-700/50 text-slate-300 border border-slate-600/50',
        success: 'bg-green-500/20 text-green-400 border border-green-500/30',
        warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
        destructive: 'bg-red-500/20 text-red-400 border border-red-500/30',
        outline: 'border border-slate-600 text-slate-400',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline';

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
