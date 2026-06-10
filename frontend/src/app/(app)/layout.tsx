import { ShellLayout } from "@/components/shell/shell-layout";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ShellLayout>{children}</ShellLayout>;
}
