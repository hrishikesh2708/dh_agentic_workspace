import * as React from "react";
import { cn } from "@/lib/utils";

export interface DropdownProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {}

const Dropdown = React.forwardRef<HTMLSelectElement, DropdownProps>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-[var(--radius)] border border-[var(--input)] bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Dropdown.displayName = "Dropdown";

export { Dropdown };
