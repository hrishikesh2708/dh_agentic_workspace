import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: React.ReactNode;
}

export function StatCard({ label, value, hint, icon }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-[var(--muted-foreground)]">
          {label}
        </CardTitle>
        {icon ? (
          <span className="text-[var(--muted-foreground)]">{icon}</span>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold">{value}</div>
        {hint ? <CardDescription className="mt-1">{hint}</CardDescription> : null}
      </CardContent>
    </Card>
  );
}
