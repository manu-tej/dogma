import { cn } from "./utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("bg-surface-2 shimmer rounded-lg", className)}
      {...props}
    />
  );
}

export { Skeleton };
